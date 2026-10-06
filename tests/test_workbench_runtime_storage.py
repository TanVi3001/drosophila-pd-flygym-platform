from __future__ import annotations

import hashlib
import sqlite3

import pytest

from drosophila_pd.workbench.runtime_storage import create_sqlite_backup, restore_sqlite_backup


def _make_database(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE notes (id INTEGER PRIMARY KEY, text TEXT NOT NULL)")
        connection.execute("INSERT INTO notes(text) VALUES (?)", ("preserve me",))


def test_sqlite_backup_and_restore_preserve_data_and_report_integrity(tmp_path):
    source = tmp_path / "source.sqlite3"
    backup = tmp_path / "backups" / "snapshot.sqlite3"
    restored = tmp_path / "restore" / "restored.sqlite3"
    _make_database(source)
    original_bytes = source.read_bytes()

    backup_report = create_sqlite_backup(source, backup)
    assert backup_report["integrity_check"] == "ok"
    assert backup_report["sha256"] == hashlib.sha256(backup.read_bytes()).hexdigest()
    assert source.read_bytes() == original_bytes

    restore_report = restore_sqlite_backup(backup, restored, expected_sha256=backup_report["sha256"])
    assert restore_report["integrity_check"] == "ok"
    with sqlite3.connect(restored) as connection:
        assert connection.execute("SELECT text FROM notes").fetchone() == ("preserve me",)


def test_sqlite_restore_checks_hash_and_never_overwrites(tmp_path):
    source = tmp_path / "source.sqlite3"
    backup = tmp_path / "backup.sqlite3"
    restored = tmp_path / "restored.sqlite3"
    _make_database(source)
    report = create_sqlite_backup(source, backup)

    with pytest.raises(ValueError, match="does not match"):
        restore_sqlite_backup(backup, restored, expected_sha256="0" * 64)
    restore_sqlite_backup(backup, restored, expected_sha256=report["sha256"])
    existing_bytes = restored.read_bytes()
    with pytest.raises(FileExistsError):
        restore_sqlite_backup(backup, restored, expected_sha256=report["sha256"])
    assert restored.read_bytes() == existing_bytes

    with pytest.raises(FileExistsError):
        create_sqlite_backup(source, backup)


def test_sqlite_backup_requires_existing_source(tmp_path):
    with pytest.raises(FileNotFoundError):
        create_sqlite_backup(tmp_path / "missing.sqlite3", tmp_path / "backup.sqlite3")
