"""SVR Production Backup, Verification, and Restore CLI (PRD NFR15, D8).

Supports both PostgreSQL (pg_dump / psql) and local SQLite (atomic online
sqlite3.Connection.backup API). Archives are packed with a SHA-256 manifest,
encrypted at rest using Fernet (AES-128-CBC + HMAC-SHA256), and paired with
an outer SHA-256 checksum file.

Recovery Objectives (PRD NFR15):
  - Backup schedule: every 24 hours (automated cron / orchestrator job)
  - RPO (Recovery Point Objective): <= 24 hours
  - RTO (Recovery Time Objective): <= 4 hours
  - Restore verification cadence: automated verify on every backup + quarterly drill
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import logging
import os
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from cryptography.fernet import Fernet, InvalidToken

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [svr-backup] %(message)s",
)
logger = logging.getLogger("svr.backup_restore")

RPO_MAX_HOURS = 24
RTO_MAX_HOURS = 4
HASH_CHUNK_BYTES = 1024 * 1024


def sha256_file(path: Path) -> str:
    """Compute hex SHA-256 digest of a file in streaming chunks."""
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(HASH_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    """Compute hex SHA-256 digest of an in-memory byte buffer."""
    return hashlib.sha256(data).hexdigest()


def detect_db_kind(db_url: str) -> str:
    """Determine database engine ('sqlite' or 'postgresql') from URL or path."""
    lowered = db_url.strip().lower()
    if lowered.startswith(("postgresql://", "postgresql+psycopg://", "postgres://")):
        return "postgresql"
    if lowered.startswith("sqlite:///") or lowered.endswith((".db", ".sqlite", ".sqlite3")):
        return "sqlite"
    raise ValueError(
        f"Unsupported database target '{db_url}'. Use sqlite:///path/to/svr.db or postgresql://..."
    )


def normalize_postgres_url(db_url: str) -> str:
    """Convert SQLAlchemy postgresql+psycopg:// URL to libpq postgresql:// URL."""
    if db_url.startswith("postgresql+psycopg://"):
        return "postgresql://" + db_url[len("postgresql+psycopg://") :]
    return db_url


def resolve_sqlite_path(db_url: str) -> Path:
    """Extract filesystem path from a sqlite:/// URL or direct file path."""
    if db_url.startswith("sqlite:///"):
        raw_path = db_url[len("sqlite:///") :]
        return Path(raw_path).resolve()
    return Path(db_url).resolve()


def resolve_fernet(encryption_key: str | None) -> Fernet:
    """Load Fernet cipher from explicit argument or SVR_ENCRYPTION_KEY env var."""
    key = (encryption_key or os.environ.get("SVR_ENCRYPTION_KEY", "")).strip()
    if not key:
        raise ValueError(
            "Encryption key required. Pass --encryption-key or set SVR_ENCRYPTION_KEY."
        )
    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, TypeError) as exc:
        raise ValueError(
            "Invalid Fernet key format. Generate one with: "
            "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        ) from exc


def _check_sqlite_integrity(db_path: Path) -> str:
    """Run SQLite PRAGMA integrity_check and return result string."""
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute("PRAGMA integrity_check;").fetchone()
        result = str(row[0]) if row else "unknown"
        if result.lower() != "ok":
            raise RuntimeError(f"SQLite integrity check failed for {db_path}: {result}")
        return result
    finally:
        conn.close()


def _snapshot_sqlite(src_path: Path, dst_path: Path) -> str:
    """Atomically snapshot a live SQLite database using the online backup API."""
    if not src_path.is_file():
        raise FileNotFoundError(f"Source SQLite database not found: {src_path}")
    src_conn = sqlite3.connect(f"file:{src_path.as_posix()}?mode=ro", uri=True)
    dst_conn = sqlite3.connect(str(dst_path))
    try:
        src_conn.backup(dst_conn, pages=256)
        dst_conn.commit()
    finally:
        dst_conn.close()
        src_conn.close()
    return _check_sqlite_integrity(dst_path)


def _dump_postgres(pg_url: str, dst_path: Path, pg_dump_bin: str) -> None:
    """Create a consistent logical SQL dump via pg_dump."""
    libpq_url = normalize_postgres_url(pg_url)
    cmd = [
        pg_dump_bin,
        "--no-owner",
        "--no-privileges",
        "--format=plain",
        "--file",
        str(dst_path),
        libpq_url,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"pg_dump failed (exit {proc.returncode}): {proc.stderr.strip()}")
    if not dst_path.is_file() or dst_path.stat().st_size == 0:
        raise RuntimeError("pg_dump produced an empty dump file.")


def _restore_postgres(pg_url: str, sql_path: Path, psql_bin: str) -> None:
    """Restore a logical SQL dump via psql with ON_ERROR_STOP enabled."""
    libpq_url = normalize_postgres_url(pg_url)
    cmd = [
        psql_bin,
        "-v",
        "ON_ERROR_STOP=1",
        "--dbname",
        libpq_url,
        "--file",
        str(sql_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"psql restore failed (exit {proc.returncode}): {proc.stderr.strip()}")


def _safe_tar_extract(tar: tarfile.TarFile, dest_dir: Path) -> None:
    """Extract tar members safely, rejecting path traversal or absolute paths."""
    resolved_dest = dest_dir.resolve()
    for member in tar.getmembers():
        if member.issym() or member.islnk():
            raise ValueError(f"Refusing to extract link member from backup archive: {member.name}")
        target_path = (resolved_dest / member.name).resolve()
        if not str(target_path).startswith(str(resolved_dest)):
            raise ValueError(f"Path traversal detected in backup archive member: {member.name}")
    tar.extractall(path=resolved_dest)


def create_backup(
    *,
    db_url: str,
    output_dir: Path,
    encryption_key: str | None = None,
    storage_dir: Path | None = None,
    pg_dump_bin: str = "pg_dump",
) -> dict[str, Any]:
    """Create an encrypted, SHA-256 verified backup bundle."""
    fernet = resolve_fernet(encryption_key)
    db_kind = detect_db_kind(db_url)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    bundle_stem = f"svr-backup-{db_kind}-{timestamp}"
    archive_path = output_dir / f"{bundle_stem}.tar.gz.enc"
    checksum_path = output_dir / f"{bundle_stem}.tar.gz.enc.sha256"

    with tempfile.TemporaryDirectory(prefix="svr_backup_") as tmp_str:
        staging = Path(tmp_str)
        manifest_files: list[dict[str, Any]] = []
        extra_meta: dict[str, Any] = {}

        if db_kind == "sqlite":
            src_db = resolve_sqlite_path(db_url)
            snap_name = "database.sqlite3"
            snap_path = staging / snap_name
            integrity = _snapshot_sqlite(src_db, snap_path)
            manifest_files.append(
                {
                    "path": snap_name,
                    "sha256": sha256_file(snap_path),
                    "size_bytes": snap_path.stat().st_size,
                    "role": "database",
                }
            )
            extra_meta["sqlite_integrity_check"] = integrity
        else:
            dump_name = "database.sql"
            dump_path = staging / dump_name
            _dump_postgres(db_url, dump_path, pg_dump_bin)
            parsed = urlparse(normalize_postgres_url(db_url))
            manifest_files.append(
                {
                    "path": dump_name,
                    "sha256": sha256_file(dump_path),
                    "size_bytes": dump_path.stat().st_size,
                    "role": "database",
                }
            )
            extra_meta["postgres_database"] = parsed.path.lstrip("/")

        if storage_dir is not None and storage_dir.is_dir():
            storage_root = staging / "storage"
            for item in sorted(storage_dir.rglob("*")):
                if item.is_file():
                    rel = item.relative_to(storage_dir).as_posix()
                    dst_item = storage_root / rel
                    dst_item.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, dst_item)
                    manifest_files.append(
                        {
                            "path": f"storage/{rel}",
                            "sha256": sha256_file(dst_item),
                            "size_bytes": dst_item.stat().st_size,
                            "role": "audio_storage",
                        }
                    )

        manifest: dict[str, Any] = {
            "schema_version": 1,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "db_kind": db_kind,
            "rpo_hours": RPO_MAX_HOURS,
            "rto_hours": RTO_MAX_HOURS,
            "encryption": "fernet-aes128-cbc-hmac-sha256",
            "files": manifest_files,
            **extra_meta,
        }
        manifest_path = staging / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w:gz") as tar:
            tar.add(manifest_path, arcname="manifest.json")
            for entry in manifest_files:
                file_path = staging / entry["path"]
                tar.add(file_path, arcname=entry["path"])

        raw_tar_bytes = tar_buffer.getvalue()
        encrypted_bytes = fernet.encrypt(raw_tar_bytes)
        archive_path.write_bytes(encrypted_bytes)

        archive_sha256 = sha256_bytes(encrypted_bytes)
        checksum_path.write_text(
            f"{archive_sha256}  {archive_path.name}\n",
            encoding="utf-8",
        )

    logger.info(
        "Backup created: %s (%d bytes, sha256=%s)",
        archive_path,
        archive_path.stat().st_size,
        archive_sha256[:16],
    )
    return {
        "status": "ok",
        "action": "backup",
        "db_kind": db_kind,
        "archive_path": str(archive_path),
        "checksum_path": str(checksum_path),
        "archive_sha256": archive_sha256,
        "archive_size_bytes": archive_path.stat().st_size,
        "file_count": len(manifest_files),
        "rpo_hours": RPO_MAX_HOURS,
        "rto_hours": RTO_MAX_HOURS,
    }


def verify_backup(
    *,
    archive_path: Path,
    encryption_key: str | None = None,
    checksum_path: Path | None = None,
) -> dict[str, Any]:
    """Verify outer SHA-256, Fernet authentication, inner manifest hashes, and DB integrity."""
    fernet = resolve_fernet(encryption_key)
    if not archive_path.is_file():
        raise FileNotFoundError(f"Backup archive not found: {archive_path}")

    sidecar = checksum_path or Path(f"{archive_path}.sha256")
    actual_outer_sha = sha256_file(archive_path)
    if sidecar.is_file():
        expected_line = sidecar.read_text(encoding="utf-8").strip()
        expected_sha = expected_line.split()[0] if expected_line else ""
        if actual_outer_sha != expected_sha:
            raise RuntimeError(
                f"Outer SHA-256 mismatch: expected {expected_sha}, got {actual_outer_sha}"
            )
    else:
        raise FileNotFoundError(f"Checksum sidecar missing: {sidecar}")

    try:
        decrypted_bytes = fernet.decrypt(archive_path.read_bytes())
    except InvalidToken as exc:
        raise RuntimeError(
            "Fernet decryption or HMAC verification failed: invalid key or tampered archive."
        ) from exc

    with tempfile.TemporaryDirectory(prefix="svr_verify_") as tmp_str:
        extract_dir = Path(tmp_str)
        with tarfile.open(fileobj=io.BytesIO(decrypted_bytes), mode="r:gz") as tar:
            _safe_tar_extract(tar, extract_dir)

        manifest_path = extract_dir / "manifest.json"
        if not manifest_path.is_file():
            raise RuntimeError("Backup archive is missing manifest.json.")

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        verified_files: list[str] = []
        for entry in manifest.get("files", []):
            rel = entry["path"]
            target = extract_dir / rel
            if not target.is_file():
                raise RuntimeError(f"Manifest member missing from archive: {rel}")
            actual_size = target.stat().st_size
            if actual_size != int(entry["size_bytes"]):
                raise RuntimeError(
                    f"Size mismatch for {rel}: expected {entry['size_bytes']}, got {actual_size}"
                )
            actual_hash = sha256_file(target)
            if actual_hash != entry["sha256"]:
                raise RuntimeError(
                    f"SHA-256 mismatch for {rel}: expected {entry['sha256']}, got {actual_hash}"
                )
            verified_files.append(rel)

        db_kind = manifest.get("db_kind")
        sqlite_check = None
        if db_kind == "sqlite":
            db_file = extract_dir / "database.sqlite3"
            sqlite_check = _check_sqlite_integrity(db_file)

    logger.info(
        "Backup verified cleanly: %s (%d files, db_kind=%s)",
        archive_path.name,
        len(verified_files),
        db_kind,
    )
    return {
        "status": "ok",
        "action": "verify",
        "archive_path": str(archive_path),
        "archive_sha256": actual_outer_sha,
        "db_kind": db_kind,
        "created_utc": manifest.get("created_utc"),
        "verified_files": verified_files,
        "sqlite_integrity_check": sqlite_check,
        "rpo_hours": manifest.get("rpo_hours", RPO_MAX_HOURS),
        "rto_hours": manifest.get("rto_hours", RTO_MAX_HOURS),
    }


def restore_backup(
    *,
    archive_path: Path,
    target_db_url: str,
    encryption_key: str | None = None,
    checksum_path: Path | None = None,
    restore_storage_dir: Path | None = None,
    psql_bin: str = "psql",
) -> dict[str, Any]:
    """Verify and restore an encrypted backup bundle into PostgreSQL or SQLite."""
    verify_report = verify_backup(
        archive_path=archive_path,
        encryption_key=encryption_key,
        checksum_path=checksum_path,
    )
    fernet = resolve_fernet(encryption_key)
    target_kind = detect_db_kind(target_db_url)
    if verify_report["db_kind"] != target_kind:
        raise ValueError(
            f"Backup engine ({verify_report['db_kind']}) does not match target ({target_kind})."
        )

    decrypted_bytes = fernet.decrypt(archive_path.read_bytes())
    restored_storage_files = 0

    with tempfile.TemporaryDirectory(prefix="svr_restore_") as tmp_str:
        extract_dir = Path(tmp_str)
        with tarfile.open(fileobj=io.BytesIO(decrypted_bytes), mode="r:gz") as tar:
            _safe_tar_extract(tar, extract_dir)

        if target_kind == "sqlite":
            src_db = extract_dir / "database.sqlite3"
            dst_db = resolve_sqlite_path(target_db_url)
            dst_db.parent.mkdir(parents=True, exist_ok=True)

            # Write into a sibling temp file, validate integrity, then atomically replace.
            tmp_target = dst_db.with_suffix(dst_db.suffix + ".restoring")
            shutil.copy2(src_db, tmp_target)
            _check_sqlite_integrity(tmp_target)
            for sidecar_suffix in ("-wal", "-shm"):
                sidecar_path = Path(f"{dst_db}{sidecar_suffix}")
                if sidecar_path.exists():
                    sidecar_path.unlink()
            os.replace(tmp_target, dst_db)
            integrity = _check_sqlite_integrity(dst_db)
        else:
            sql_file = extract_dir / "database.sql"
            _restore_postgres(target_db_url, sql_file, psql_bin)
            integrity = "psql_restored"

        storage_src = extract_dir / "storage"
        if restore_storage_dir is not None and storage_src.is_dir():
            restore_storage_dir.mkdir(parents=True, exist_ok=True)
            for item in sorted(storage_src.rglob("*")):
                if item.is_file():
                    rel = item.relative_to(storage_src)
                    dst_item = restore_storage_dir / rel
                    dst_item.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, dst_item)
                    restored_storage_files += 1

    logger.info("Restore completed cleanly for %s target.", target_kind)
    return {
        "status": "ok",
        "action": "restore",
        "db_kind": target_kind,
        "archive_path": str(archive_path),
        "target_db": target_db_url if target_kind == "sqlite" else "postgresql://***",
        "integrity": integrity,
        "restored_storage_files": restored_storage_files,
        "rpo_hours": RPO_MAX_HOURS,
        "rto_hours": RTO_MAX_HOURS,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "SVR encrypted backup, SHA-256 verification, and restore tool "
            "(PostgreSQL and SQLite; RPO <= 24h, RTO <= 4h per PRD NFR15)."
        )
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--backup", action="store_true", help="Create an encrypted verified backup")
    mode.add_argument("--verify", action="store_true", help="Verify archive SHA-256 and integrity")
    mode.add_argument("--restore", action="store_true", help="Verify and restore a backup archive")

    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL", ""),
        help="Database URL (sqlite:///... or postgresql://...). Defaults to DATABASE_URL env var.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("backups"),
        help="Output directory for --backup bundles (default: ./backups).",
    )
    parser.add_argument(
        "--archive",
        type=Path,
        help="Path to encrypted .tar.gz.enc backup archive for --verify or --restore.",
    )
    parser.add_argument(
        "--checksum",
        type=Path,
        default=None,
        help="Optional explicit .sha256 sidecar path (defaults to <archive>.sha256).",
    )
    parser.add_argument(
        "--storage-dir",
        type=Path,
        default=None,
        help="Optional encrypted voicemail storage directory to include or restore.",
    )
    parser.add_argument(
        "--encryption-key",
        default=None,
        help="Fernet key (defaults to SVR_ENCRYPTION_KEY env var).",
    )
    parser.add_argument("--pg-dump-bin", default="pg_dump", help="Path to pg_dump executable.")
    parser.add_argument("--psql-bin", default="psql", help="Path to psql executable.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.backup:
            if not args.database_url:
                parser.error("--database-url or DATABASE_URL is required for --backup")
            report = create_backup(
                db_url=args.database_url,
                output_dir=args.output_dir,
                encryption_key=args.encryption_key,
                storage_dir=args.storage_dir,
                pg_dump_bin=args.pg_dump_bin,
            )
        elif args.verify:
            if not args.archive:
                parser.error("--archive is required for --verify")
            report = verify_backup(
                archive_path=args.archive,
                encryption_key=args.encryption_key,
                checksum_path=args.checksum,
            )
        else:
            if not args.archive or not args.database_url:
                parser.error("--archive and --database-url are required for --restore")
            report = restore_backup(
                archive_path=args.archive,
                target_db_url=args.database_url,
                encryption_key=args.encryption_key,
                checksum_path=args.checksum,
                restore_storage_dir=args.storage_dir,
                psql_bin=args.psql_bin,
            )
    except (ValueError, FileNotFoundError, RuntimeError, OSError, sqlite3.Error) as exc:
        logger.error("Operation failed: %s", exc)
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2), file=sys.stderr)
        return 1

    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
