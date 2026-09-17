"""SQLite persistence for studies, jobs, and audit events."""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from .models import JobRecord, StudySpec, jsonable, utc_timestamp


class WorkbenchStore:
    """Small thread-safe SQLite store used by both CLI and local API.

    The database stores complete JSON payloads as well as indexed identity and
    status columns.  This keeps the schema stable while making the common job
    listing queries straightforward.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def _initialize(self) -> None:
        with self._lock, self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS studies (
                    study_id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    study_id TEXT NOT NULL REFERENCES studies(study_id),
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    submitted_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS jobs_status_idx ON jobs(status, submitted_at);
                CREATE INDEX IF NOT EXISTS jobs_study_idx ON jobs(study_id, submitted_at);
                CREATE TABLE IF NOT EXISTS events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS events_entity_idx ON events(entity_type, entity_id, event_id);
                CREATE TABLE IF NOT EXISTS reviews (
                    study_id TEXT PRIMARY KEY REFERENCES studies(study_id),
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )

    def create_study(self, study: StudySpec) -> StudySpec:
        payload = json.dumps(jsonable(study.as_dict()), sort_keys=True)
        now = utc_timestamp()
        with self._lock, self._connect() as connection:
            try:
                connection.execute(
                    "INSERT INTO studies(study_id, payload_json, created_at, updated_at) VALUES (?, ?, ?, ?)",
                    (study.study_id, payload, study.created_at, now),
                )
            except sqlite3.IntegrityError as error:
                raise ValueError(f"study already exists: {study.study_id}") from error
            self._record_event(connection, "study", study.study_id, "created", study.as_dict())
        return study

    def get_study(self, study_id: str) -> StudySpec:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM studies WHERE study_id = ?", (study_id,)
            ).fetchone()
        if row is None:
            raise KeyError(f"unknown study_id: {study_id}")
        return StudySpec.from_dict(json.loads(row["payload_json"]))

    def list_studies(self) -> list[StudySpec]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT payload_json FROM studies ORDER BY created_at, study_id"
            ).fetchall()
        return [StudySpec.from_dict(json.loads(row["payload_json"])) for row in rows]

    def create_job(self, job: JobRecord) -> JobRecord:
        payload = json.dumps(jsonable(job.as_dict()), sort_keys=True)
        with self._lock, self._connect() as connection:
            try:
                connection.execute(
                    "INSERT INTO jobs(job_id, study_id, status, payload_json, submitted_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (job.job_id, job.study_id, job.status.value, payload, job.submitted_at, utc_timestamp()),
                )
            except sqlite3.IntegrityError as error:
                raise ValueError(f"job already exists or study is unknown: {job.job_id}") from error
            self._record_event(connection, "job", job.job_id, "submitted", job.as_dict())
        return job

    def get_job(self, job_id: str) -> JobRecord:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
        if row is None:
            raise KeyError(f"unknown job_id: {job_id}")
        return JobRecord.from_dict(json.loads(row["payload_json"]))

    def update_job(self, job: JobRecord, *, event: str | None = None) -> JobRecord:
        payload = json.dumps(jsonable(job.as_dict()), sort_keys=True)
        now = utc_timestamp()
        with self._lock, self._connect() as connection:
            result = connection.execute(
                "UPDATE jobs SET status = ?, payload_json = ?, updated_at = ? WHERE job_id = ?",
                (job.status.value, payload, now, job.job_id),
            )
            if result.rowcount != 1:
                raise KeyError(f"unknown job_id: {job.job_id}")
            if event:
                self._record_event(connection, "job", job.job_id, event, job.as_dict())
        return job

    def claim_job(self, job: JobRecord, *, event: str = "started") -> JobRecord:
        """Atomically move one pending job to RUNNING.

        The conditional status predicate is important when the API server and
        CLI worker point at the same SQLite database from separate processes.
        """

        payload = json.dumps(jsonable(job.as_dict()), sort_keys=True)
        now = utc_timestamp()
        with self._lock, self._connect() as connection:
            result = connection.execute(
                "UPDATE jobs SET status = ?, payload_json = ?, updated_at = ? "
                "WHERE job_id = ? AND status = 'PENDING'",
                (job.status.value, payload, now, job.job_id),
            )
            if result.rowcount != 1:
                raise ValueError(f"job is no longer pending: {job.job_id}")
            self._record_event(connection, "job", job.job_id, event, job.as_dict())
        return job

    def list_jobs(self, *, study_id: str | None = None) -> list[JobRecord]:
        query = "SELECT payload_json FROM jobs"
        parameters: tuple[Any, ...] = ()
        if study_id is not None:
            query += " WHERE study_id = ?"
            parameters = (study_id,)
        query += " ORDER BY submitted_at, job_id"
        with self._lock, self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [JobRecord.from_dict(json.loads(row["payload_json"])) for row in rows]

    def next_pending_job(self) -> JobRecord | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM jobs WHERE status = 'PENDING' ORDER BY submitted_at, job_id LIMIT 1"
            ).fetchone()
        return None if row is None else JobRecord.from_dict(json.loads(row["payload_json"]))

    def events(self, entity_type: str, entity_id: str) -> list[dict[str, Any]]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT timestamp, entity_type, entity_id, event_type, payload_json "
                "FROM events WHERE entity_type = ? AND entity_id = ? ORDER BY event_id",
                (entity_type, entity_id),
            ).fetchall()
        return [
            {
                "timestamp": row["timestamp"],
                "entity_type": row["entity_type"],
                "entity_id": row["entity_id"],
                "event_type": row["event_type"],
                "payload": json.loads(row["payload_json"]),
            }
            for row in rows
        ]

    def set_review(self, study_id: str, review: dict[str, Any]) -> dict[str, Any]:
        payload = json.dumps(jsonable(review), sort_keys=True)
        now = utc_timestamp()
        with self._lock, self._connect() as connection:
            if connection.execute(
                "SELECT 1 FROM studies WHERE study_id = ?", (study_id,)
            ).fetchone() is None:
                raise KeyError(f"unknown study_id: {study_id}")
            connection.execute(
                "INSERT INTO reviews(study_id, payload_json, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(study_id) DO UPDATE SET payload_json = excluded.payload_json, updated_at = excluded.updated_at",
                (study_id, payload, now),
            )
            self._record_event(connection, "study", study_id, "review_updated", review)
        return dict(review)

    def get_review(self, study_id: str) -> dict[str, Any] | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM reviews WHERE study_id = ?", (study_id,)
            ).fetchone()
        if row is None:
            return None
        return dict(json.loads(row["payload_json"]))

    @staticmethod
    def _record_event(
        connection: sqlite3.Connection,
        entity_type: str,
        entity_id: str,
        event_type: str,
        payload: Any,
    ) -> None:
        connection.execute(
            "INSERT INTO events(timestamp, entity_type, entity_id, event_type, payload_json) VALUES (?, ?, ?, ?, ?)",
            (utc_timestamp(), entity_type, entity_id, event_type, json.dumps(jsonable(payload), sort_keys=True)),
        )


__all__ = ["WorkbenchStore"]
