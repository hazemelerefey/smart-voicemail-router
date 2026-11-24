"""The test-once guard: the frozen test split of a model is evaluated one time per dataset version.

The rule: for one model and one dataset version, the test split is scored exactly once,
so that nobody can score several checkpoints and keep the best one.

How it works:
- A log file in the repository (for example runs/test_evaluations.json) lists every test
  evaluation that was claimed: the model, the dataset version, the run id, the time, the
  SHA-256 of the test file, and (for documentation only) the SHA-256 of the checkpoint.
- claim_test_evaluation() writes a new entry BEFORE any test label is read, and refuses if
  an entry for the same (model, dataset version) already exists. The refusal does not look
  at the checkpoint: a different checkpoint of the same model does not get a second try.
- It returns an EvaluationClaim. The harness takes that object for the test split and
  consumes one use of it for every scoring call. One evaluation of a model has one scoring
  call per seed, so the claim is created with uses = the number of seeds; when the uses are
  gone the claim cannot score the test split any more.
- A new dataset version (for example after the audit corrections) allows one new evaluation.
- If a claimed evaluation fails for a technical reason, the claim stays in the log. Releasing
  it is a manual, visible change of the log that the Training Lead has to approve.

The model name is normalized before it is compared: lower case, the part after the last "/",
only letters and digits. So "MARBERTv2" and "UBC-NLP/MARBERTv2" are the same model.

This module uses only the standard library. It never reads the content of the test labels.
"""
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

LOG_SCHEMA_VERSION = 1
ENTRY_KEYS = (
    "model", "model_key", "dataset_version", "run_id", "claimed_utc",
    "uses", "test_file_sha256", "checkpoint_sha256",
)

_RUN_ID = re.compile(r"^[A-Za-z0-9_-]+$")
_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")


class GuardError(ValueError):
    """The guard cannot be used or the log is invalid."""


class AlreadyEvaluatedError(GuardError):
    """The test split of this model and dataset version was already claimed."""


def normalize_model_name(name):
    """'UBC-NLP/MARBERTv2' and 'MARBERTv2' both give 'marbertv2'."""
    if not isinstance(name, str) or not name.strip():
        raise GuardError("model must be a non-empty string")
    key = re.sub(r"[^a-z0-9]", "", name.strip().rsplit("/", 1)[-1].lower())
    if not key:
        raise GuardError(f"model name {name!r} has no letters or digits")
    return key


def file_sha256(path):
    path = Path(path)
    if not path.is_file():
        raise GuardError(f"file not found: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class EvaluationClaim:
    """The right to score the test split for one evaluation. Created only by claim_test_evaluation."""

    def __init__(self, model_key, dataset_version, run_id, log_path, uses=1):
        self.model_key = model_key
        self.dataset_version = dataset_version
        self.run_id = run_id
        self.log_path = str(log_path)
        self.uses = uses
        self._remaining = uses

    @property
    def remaining(self):
        return self._remaining

    @property
    def consumed(self):
        return self._remaining == 0

    def consume(self):
        """Use one scoring call. Raises when all the uses of this claim are gone."""
        if self._remaining == 0:
            raise GuardError(
                f"the claim of run {self.run_id!r} has no uses left ({self.uses} were allowed): "
                f"the test split is scored once per evaluation"
            )
        self._remaining -= 1


def _empty_log():
    return {"schema_version": LOG_SCHEMA_VERSION, "entries": []}


def read_log(log_path):
    """Read and check the log. A missing file is an empty log. A damaged file is an error."""
    path = Path(log_path)
    if not path.exists():
        return _empty_log()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GuardError(f"the test evaluation log is not valid JSON: {path} ({exc})")
    if not isinstance(data, dict) or set(data) != {"schema_version", "entries"}:
        raise GuardError(f"the test evaluation log must have exactly 'schema_version' and 'entries': {path}")
    if data["schema_version"] != LOG_SCHEMA_VERSION:
        raise GuardError(f"unsupported log schema_version {data['schema_version']!r}")
    if not isinstance(data["entries"], list):
        raise GuardError("the log 'entries' must be a list")
    for i, entry in enumerate(data["entries"]):
        if not isinstance(entry, dict) or set(entry) != set(ENTRY_KEYS):
            raise GuardError(f"log entry {i} must have exactly the keys {list(ENTRY_KEYS)}")
    return data


def _write_log_atomically(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".once_guard_", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        os.replace(tmp_name, path)
    except BaseException:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise


def is_claimed(log_path, model, dataset_version):
    key = normalize_model_name(model)
    return any(
        e["model_key"] == key and e["dataset_version"] == dataset_version
        for e in read_log(log_path)["entries"]
    )


def claim_test_evaluation(
    log_path,
    *,
    model,
    dataset_version,
    run_id,
    uses=1,
    test_csv_path=None,
    checkpoint_sha256=None,
    now_utc=None,
):
    """Record the claim and return an EvaluationClaim, or raise AlreadyEvaluatedError.

    `uses` is the number of scoring calls this one evaluation needs (one per seed).
    """
    key = normalize_model_name(model)
    if not isinstance(dataset_version, str) or not dataset_version.strip():
        raise GuardError("dataset_version must be a non-empty string")
    if not isinstance(run_id, str) or not _RUN_ID.match(run_id):
        raise GuardError(f"run_id must be letters, digits, '-' or '_', got {run_id!r}")
    if not isinstance(uses, int) or isinstance(uses, bool) or uses < 1:
        raise GuardError(f"uses must be a whole number, 1 or more, got {uses!r}")
    if checkpoint_sha256 is not None and (
        not isinstance(checkpoint_sha256, str) or not _SHA256.match(checkpoint_sha256)
    ):
        raise GuardError("checkpoint_sha256 must be a 64-character hex string or None")
    test_hash = file_sha256(test_csv_path) if test_csv_path is not None else None

    data = read_log(log_path)
    for entry in data["entries"]:
        if entry["model_key"] == key and entry["dataset_version"] == dataset_version:
            raise AlreadyEvaluatedError(
                f"the test split was already evaluated for model {entry['model']!r} on dataset "
                f"version {dataset_version!r} (run {entry['run_id']!r}, {entry['claimed_utc']}); "
                f"a second evaluation of the same model needs a new dataset version"
            )

    data["entries"].append({
        "model": model,
        "model_key": key,
        "dataset_version": dataset_version,
        "run_id": run_id,
        "claimed_utc": now_utc or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "uses": uses,
        "test_file_sha256": test_hash,
        "checkpoint_sha256": checkpoint_sha256,
    })
    _write_log_atomically(log_path, data)
    return EvaluationClaim(key, dataset_version, run_id, log_path, uses)