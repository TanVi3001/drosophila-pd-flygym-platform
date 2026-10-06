"""Isolated runtime paths and graph-free draft intake for Workbench V2.

V2 storage is opt-in and must live outside the source checkout. This module
does not create directories until an explicit ``prepare`` or draft operation.
"""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .intake import IntakeProvider, create_intake_draft


class V2RuntimeUnavailableError(RuntimeError):
    """Raised when the V2 draft endpoint cannot serve a request."""


class V2RuntimeDisabledError(V2RuntimeUnavailableError):
    """Raised when a caller invokes an opt-in V2 path while V2 is disabled."""


class V2IntakeProviderUnavailableError(V2RuntimeUnavailableError):
    """Raised when V2 is enabled but no V2-only provider was configured."""


def _within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def paths_overlap(first: str | Path, second: str | Path) -> bool:
    """Return whether either resolved path is equal to or nested in the other."""

    left = Path(first).expanduser().resolve()
    right = Path(second).expanduser().resolve()
    return _within(left, right) or _within(right, left)


def validate_external_path(path: str | Path, *, repository_root: str | Path, label: str) -> Path:
    """Validate one explicit absolute path that must be outside the checkout."""

    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        raise ValueError(f"{label} must be an absolute path when V2 is enabled")
    resolved = candidate.resolve()
    repository = Path(repository_root).expanduser().resolve()
    if paths_overlap(resolved, repository):
        raise ValueError(f"{label} must be outside and non-overlapping with the repository")
    return resolved


@dataclass(frozen=True)
class RuntimeLayout:
    """Repository-external V1/V2 runtime layout; paths are not created here."""

    root: Path

    @classmethod
    def from_root(cls, root: str | Path, *, repository_root: str | Path) -> "RuntimeLayout":
        validated = validate_external_path(root, repository_root=repository_root, label="V2 runtime root")
        return cls(root=validated)

    @property
    def v1_database(self) -> Path:
        return self.root / "workbench" / "state" / "workbench.sqlite3"

    @property
    def v1_artifacts(self) -> Path:
        return self.root / "workbench" / "artifacts"

    @property
    def database_backups(self) -> Path:
        return self.root / "backups" / "workbench_database"

    @property
    def v2_root(self) -> Path:
        return self.root / "ai_v2"

    @property
    def v2_config(self) -> Path:
        return self.v2_root / "config"

    @property
    def v2_corpus(self) -> Path:
        return self.v2_root / "corpus"

    @property
    def v2_prompts(self) -> Path:
        return self.v2_root / "prompts"

    @property
    def v2_cache(self) -> Path:
        return self.v2_root / "cache"

    @property
    def v2_outputs(self) -> Path:
        return self.v2_root / "outputs"

    def prepare(self) -> None:
        """Create the declared external directory tree after explicit opt-in."""

        self.root.mkdir(parents=True, exist_ok=True)
        root = self.root.resolve()
        directories = (
            self.v1_database.parent,
            self.v1_artifacts,
            self.database_backups,
            self.v2_config,
            self.v2_corpus,
            self.v2_prompts,
            self.v2_cache,
            self.v2_outputs,
        )
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            if not _within(directory.resolve(), root):
                raise ValueError(f"runtime directory escapes configured root: {directory}")


def v2_enabled_from_env(value: str | None = None) -> bool:
    """Parse the explicit V2 enable flag; absent/unknown values stay disabled."""

    raw = os.environ.get("FLY_WORKBENCH_V2_ENABLED", "") if value is None else value
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def validate_external_workbench_paths(
    *,
    db_path: str | Path,
    artifact_path: str | Path,
    repository_root: str | Path,
) -> tuple[Path, Path]:
    """Validate explicit V1 storage paths for an opted-in external runtime."""

    database = validate_external_path(db_path, repository_root=repository_root, label="--db")
    artifacts = validate_external_path(artifact_path, repository_root=repository_root, label="--artifacts")
    if paths_overlap(database, artifacts):
        raise ValueError("--db and --artifacts must not overlap")
    return database, artifacts


class WorkbenchV2DraftRuntime:
    """Persist sanitized, researcher-reviewable drafts without graph execution."""

    def __init__(self, *, provider: IntakeProvider | None, output_root: str | Path) -> None:
        self.provider = provider
        self.output_root = Path(output_root).expanduser().resolve()

    def preview(self, protocol_text: str, *, source_uri: str | None = None) -> dict[str, Any]:
        if self.provider is None:
            raise V2IntakeProviderUnavailableError("V2 protocol intake provider is not configured")
        draft = create_intake_draft(
            protocol_text,
            self.provider,
            source_uri=source_uri,
            prompt_version="workbench-v2-draft-a01",
        )
        draft_id = f"v2-intake-{uuid.uuid4().hex}"
        draft.update(
            {
                "draft_id": draft_id,
                "workflow_mode": "DRAFT_ONLY",
                "retrieval_mode": "NOT_CONFIGURED_IN_A01",
                "graph_used": False,
                "simulation_started": False,
                "approval_granted": False,
            }
        )
        self.output_root.mkdir(parents=True, exist_ok=True)
        resolved_root = self.output_root.resolve()
        target = resolved_root / f"{draft_id}.json"
        draft["artifact_path"] = target.as_posix()
        _write_new_json(target, draft)
        return draft


def _write_new_json(target: Path, value: dict[str, Any]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(prefix=".draft-", suffix=".tmp", dir=target.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, target)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


__all__ = [
    "RuntimeLayout",
    "V2RuntimeDisabledError",
    "V2IntakeProviderUnavailableError",
    "V2RuntimeUnavailableError",
    "WorkbenchV2DraftRuntime",
    "paths_overlap",
    "validate_external_path",
    "validate_external_workbench_paths",
    "v2_enabled_from_env",
]
