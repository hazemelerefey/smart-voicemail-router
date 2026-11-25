"""SHA-256 test-once evaluation guard (PRD AI9, WF5).

Logs every test evaluation claim to ``runs/test_evaluations.json`` BEFORE any
test split file is opened, records checkpoint SHA-256 provenance, and refuses
repeat test evaluations for the same model and dataset version.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping

LEDGER_SCHEMA_VERSION = 1


class TestOnceGuardError(RuntimeError):
    """Raised when a test evaluation violates the test-once policy or ledger integrity."""

    __test__ = False


@dataclass(frozen=True)
class GuardClaim:
    """Immutable claim recorded in the test evaluation ledger before reading test labels."""

    claim_id: str
    model_version: str
    dataset_version: str
    checkpoint_sha256: str
    split: str
    actor: str
    claimed_at_utc: str
    status: str = "claimed"
    dataset_sha256: str | None = None
    completed_at_utc: str | None = None
    result_summary: dict | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def compute_file_sha256(path: Path) -> str:
    """Return the hex SHA-256 digest of a file without loading it all into RAM."""
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"Cannot hash missing file: {file_path}")
    hasher = hashlib.sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_checkpoint_set_sha256(paths: Mapping[str, Path] | Iterable[Path]) -> str:
    """Compute a deterministic combined SHA-256 digest over checkpoint weight files."""
    hasher = hashlib.sha256()
    if isinstance(paths, Mapping):
        ordered = [(str(k), Path(v)) for k, v in sorted(paths.items())]
    else:
        ordered = [(str(Path(p).name), Path(p)) for p in sorted(Path(p) for p in paths)]
    if not ordered:
        raise TestOnceGuardError("At least one checkpoint file path is required for provenance hashing.")
    for label, p in ordered:
        file_hash = compute_file_sha256(p)
        hasher.update(label.encode("utf-8"))
        hasher.update(b":")
        hasher.update(file_hash.encode("ascii"))
        hasher.update(b"\n")
    return hasher.hexdigest()


class _LedgerFileLock:
    """Simple cross-platform exclusive lockfile around ledger read-modify-write."""

    def __init__(self, ledger_path: Path, timeout_s: float = 10.0) -> None:
        self.lock_path = ledger_path.parent / f".{ledger_path.name}.lock"
        self.timeout_s = timeout_s
        self._fd: int | None = None

    def __enter__(self) -> _LedgerFileLock:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self.timeout_s
        while True:
            try:
                self._fd = os.open(
                    str(self.lock_path),
                    os.O_CREAT | os.O_EXCL | os.O_RDWR,
                )
                os.write(self._fd, f"{os.getpid()}\n".encode("ascii"))
                return self
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise TestOnceGuardError(
                        f"Timed out waiting for test-once guard lock: {self.lock_path}"
                    )
                time.sleep(0.05)

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
        if self.lock_path.exists():
            self.lock_path.unlink()


def _empty_ledger() -> dict:
    return {
        "schema_version": LEDGER_SCHEMA_VERSION,
        "policy": "Each (model_version, dataset_version) may evaluate the test split at most once.",
        "claims": [],
    }


def load_test_ledger(ledger_path: Path) -> dict:
    """Load and validate the test evaluation ledger JSON."""
    path = Path(ledger_path)
    if not path.exists():
        return _empty_ledger()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TestOnceGuardError(f"Test evaluation ledger is unreadable or invalid JSON: {path} ({exc})") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("claims"), list):
        raise TestOnceGuardError(f"Test evaluation ledger has invalid structure: {path}")
    return payload


def _atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
    serialized = json.dumps(payload, indent=2, sort_keys=False) + "\n"
    with tmp_path.open("w", encoding="utf-8") as handle:
        handle.write(serialized)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp_path, path)


def claim_test_evaluation(
    ledger_path: Path,
    *,
    model_version: str,
    dataset_version: str,
    checkpoint_sha256: str,
    actor: str = "system",
) -> GuardClaim:
    """Log a durable test evaluation claim BEFORE opening any test file.

    Refuses repeat runs when an existing claim already matches either
    ``(model_version, dataset_version)`` or ``(checkpoint_sha256, dataset_version)``.
    """
    model_clean = str(model_version or "").strip()
    dataset_clean = str(dataset_version or "").strip()
    ckpt_clean = str(checkpoint_sha256 or "").strip().lower()
    actor_clean = str(actor or "system").strip() or "system"

    if not model_clean:
        raise TestOnceGuardError("model_version must be a non-empty string.")
    if not dataset_clean:
        raise TestOnceGuardError("dataset_version must be a non-empty string.")
    if not ckpt_clean:
        raise TestOnceGuardError("checkpoint_sha256 must be a non-empty SHA-256 string.")

    path = Path(ledger_path)
    with _LedgerFileLock(path):
        ledger = load_test_ledger(path)
        for existing in ledger["claims"]:
            if not isinstance(existing, dict):
                continue
            same_dataset = existing.get("dataset_version") == dataset_clean
            same_model = existing.get("model_version") == model_clean
            same_ckpt = (
                bool(existing.get("checkpoint_sha256"))
                and str(existing.get("checkpoint_sha256")).lower() == ckpt_clean
            )
            if same_dataset and (same_model or same_ckpt):
                raise TestOnceGuardError(
                    "Refusing repeat test evaluation: claim "
                    f"{existing.get('claim_id')} already exists for "
                    f"model={existing.get('model_version')!r}, "
                    f"dataset_version={dataset_clean!r}, "
                    f"checkpoint_sha256={existing.get('checkpoint_sha256')!r} "
                    f"(status={existing.get('status')!r}, claimed_at={existing.get('claimed_at_utc')!r})."
                )

        now_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")
        digest_seed = f"{model_clean}|{dataset_clean}|{ckpt_clean}|{now_utc}|{uuid.uuid4().hex}"
        claim_id = f"test-claim-{hashlib.sha256(digest_seed.encode('utf-8')).hexdigest()[:16]}"
        claim = GuardClaim(
            claim_id=claim_id,
            model_version=model_clean,
            dataset_version=dataset_clean,
            checkpoint_sha256=ckpt_clean,
            split="test",
            actor=actor_clean,
            claimed_at_utc=now_utc,
            status="claimed",
        )
        ledger["claims"].append(claim.to_dict())
        _atomic_write_json(path, ledger)
        return claim


def record_test_dataset_sha256(ledger_path: Path, claim_id: str, dataset_sha256: str) -> dict:
    """Attach the SHA-256 hash of the test file bytes to an already-logged claim."""
    path = Path(ledger_path)
    with _LedgerFileLock(path):
        ledger = load_test_ledger(path)
        for item in ledger["claims"]:
            if isinstance(item, dict) and item.get("claim_id") == claim_id:
                item["dataset_sha256"] = dataset_sha256
                _atomic_write_json(path, ledger)
                return dict(item)
    raise TestOnceGuardError(f"Unknown test guard claim_id: {claim_id}")


def finalize_test_claim(
    ledger_path: Path,
    claim_id: str,
    *,
    status: str,
    result_summary: dict | None = None,
) -> dict:
    """Mark an existing test claim as completed or failed without ever erasing it."""
    if status not in ("completed", "failed"):
        raise TestOnceGuardError(f"Final claim status must be 'completed' or 'failed', got {status!r}")
    path = Path(ledger_path)
    with _LedgerFileLock(path):
        ledger = load_test_ledger(path)
        for item in ledger["claims"]:
            if isinstance(item, dict) and item.get("claim_id") == claim_id:
                item["status"] = status
                item["completed_at_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
                if result_summary is not None:
                    item["result_summary"] = result_summary
                _atomic_write_json(path, ledger)
                return dict(item)
    raise TestOnceGuardError(f"Unknown test guard claim_id: {claim_id}")


def guarded_read_test_file(
    ledger_path: Path,
    test_file: Path,
    *,
    model_version: str,
    dataset_version: str,
    checkpoint_sha256: str,
    actor: str = "system",
) -> tuple[GuardClaim, bytes, str]:
    """Enforce test-once discipline: log the claim FIRST, then open and read the test file."""
    claim = claim_test_evaluation(
        ledger_path,
        model_version=model_version,
        dataset_version=dataset_version,
        checkpoint_sha256=checkpoint_sha256,
        actor=actor,
    )
    target = Path(test_file)
    try:
        raw_bytes = target.read_bytes()
    except OSError as exc:
        finalize_test_claim(
            ledger_path,
            claim.claim_id,
            status="failed",
            result_summary={"error": f"Failed to read test file: {exc}"},
        )
        raise

    dataset_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    record_test_dataset_sha256(ledger_path, claim.claim_id, dataset_sha256)
    updated_claim = GuardClaim(
        claim_id=claim.claim_id,
        model_version=claim.model_version,
        dataset_version=claim.dataset_version,
        checkpoint_sha256=claim.checkpoint_sha256,
        split=claim.split,
        actor=claim.actor,
        claimed_at_utc=claim.claimed_at_utc,
        status=claim.status,
        dataset_sha256=dataset_sha256,
        completed_at_utc=claim.completed_at_utc,
        result_summary=claim.result_summary,
    )
    return updated_claim, raw_bytes, dataset_sha256
