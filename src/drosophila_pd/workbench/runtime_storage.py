"""Explicit, no-overwrite SQLite backup/restore helpers for runtime storage."""

from __future__ import annotations

import hashlib
import os
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path
from typing import Any


def create_sqlite_backup(source: str | Path, destination: str | Path) -> dict[str, Any]:
    """Create a consistent SQLite backup without modifying the source DB.

    The destination must not already exist. SQLite's online backup API is used
    so a live WAL database is copied consistently; publication is no-overwrite.
    """

    source_path = Path(source).expanduser().resolve(strict=True)
    destination_path = Path(destination).expanduser().resolve()
    if source_path == destination_path:
        raise ValueError("backup destination must differ from source")
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    if destination_path.exists():
        raise FileExistsError(destination_path)
    temporary = _temporary_path(destination_path.parent, ".sqlite-backup-")
    try:
        source_uri = source_path.as_uri() + "?mode=ro"
        with closing(sqlite3.connect(source_uri, uri=True)) as source_db:
            with closing(sqlite3.connect(temporary)) as backup_db:
                source_db.backup(backup_db)
        _require_integrity(temporary)
        checksum = _sha256(temporary)
        _publish_no_overwrite(temporary, destination_path)
        return {
            "source": source_path.as_posix(),
            "backup": destination_path.as_posix(),
            "sha256": checksum,
            "integrity_check": "ok",
            "bytes": destination_path.stat().st_size,
        }
    finally:
        _unlink_if_present(temporary)


def restore_sqlite_backup(
    backup: str | Path,
    destination: str | Path,
    *,
    expected_sha256: str,
) -> dict[str, Any]:
    """Restore a verified backup to a new path; never overwrite existing data."""

    backup_path = Path(backup).expanduser().resolve(strict=True)
    destination_path = Path(destination).expanduser().resolve()
    if backup_path == destination_path:
        raise ValueError("restore destination must differ from backup")
    if not isinstance(expected_sha256, str) or len(expected_sha256) != 64:
        raise ValueError("expected_sha256 must be a 64-character SHA-256 hex digest")
    actual_hash = _sha256(backup_path)
    if actual_hash.lower() != expected_sha256.lower():
        raise ValueError("backup SHA-256 does not match expected_sha256")
    _require_integrity(backup_path)
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    if destination_path.exists():
        raise FileExistsError(destination_path)
    temporary = _temporary_path(destination_path.parent, ".sqlite-restore-")
    try:
        with closing(sqlite3.connect(backup_path)) as backup_db:
            with closing(sqlite3.connect(temporary)) as restored_db:
                backup_db.backup(restored_db)
        _require_integrity(temporary)
        restored_hash = _sha256(temporary)
        _publish_no_overwrite(temporary, destination_path)
        return {
            "backup": backup_path.as_posix(),
            "destination": destination_path.as_posix(),
            "backup_sha256": actual_hash,
            "restored_sha256": restored_hash,
            "integrity_check": "ok",
            "bytes": destination_path.stat().st_size,
        }
    finally:
        _unlink_if_present(temporary)


def _temporary_path(directory: Path, prefix: str) -> Path:
    descriptor, name = tempfile.mkstemp(prefix=prefix, suffix=".tmp", dir=directory)
    os.close(descriptor)
    return Path(name)


def _publish_no_overwrite(temporary: Path, destination: Path) -> None:
    try:
        os.link(temporary, destination)
    except FileExistsError:
        raise
    except OSError as error:
        raise OSError(f"could not atomically publish SQLite file: {type(error).__name__}") from error
    temporary.unlink()


def _require_integrity(path: Path) -> None:
    with closing(sqlite3.connect(path)) as connection:
        result = connection.execute("PRAGMA integrity_check").fetchone()
    if result is None or result[0] != "ok":
        raise ValueError(f"SQLite integrity check failed: {path}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _unlink_if_present(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass


__all__ = ["create_sqlite_backup", "restore_sqlite_backup"]
