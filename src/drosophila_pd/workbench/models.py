"""Small, explicit data contracts for Fly Research Workbench v0.1.

The workbench models describe a study and its computational provenance.  They
do not make biological claims and deliberately keep uncertainty and scope
visible in serialized output.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Mapping


WORKBENCH_SCOPE = (
    "Local computational research orchestration for supported Drosophila "
    "backends; simulation output is not biological validation."
)


def utc_timestamp() -> str:
    return datetime.now(UTC).isoformat()


def jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, Enum):
        return value.value
    if hasattr(value, "as_dict") and callable(value.as_dict):
        return jsonable(value.as_dict())
    if isinstance(value, Mapping):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [jsonable(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"value is not JSON-compatible: {type(value).__name__}")


def stable_hash(value: Any) -> str:
    payload = json.dumps(jsonable(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CandidateSpec:
    """One candidate intervention or target in a study."""

    candidate_id: str
    label: str
    target: str | None = None
    intervention: Mapping[str, Any] = field(default_factory=dict)
    expected_direction: str | None = None
    sources: tuple[Mapping[str, Any], ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.candidate_id.strip() or not self.label.strip():
            raise ValueError("candidate_id and label are required")
        object.__setattr__(self, "sources", tuple(dict(item) for item in self.sources))

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "label": self.label,
            "target": self.target,
            "intervention": jsonable(self.intervention),
            "expected_direction": self.expected_direction,
            "sources": jsonable(self.sources),
            "metadata": jsonable(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CandidateSpec":
        return cls(
            candidate_id=str(data["candidate_id"]),
            label=str(data.get("label", data["candidate_id"])),
            target=None if data.get("target") is None else str(data["target"]),
            intervention=dict(data.get("intervention", {})),
            expected_direction=(
                None if data.get("expected_direction") is None else str(data["expected_direction"])
            ),
            sources=tuple(dict(item) for item in data.get("sources", ())),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class StudySpec:
    """The minimum auditable specification for a workbench study."""

    name: str
    hypothesis: str
    falsifiable_prediction: str
    assay: str
    primary_metric: str
    candidates: tuple[CandidateSpec, ...]
    controls: tuple[Mapping[str, Any], ...] = ()
    sources: tuple[Mapping[str, Any], ...] = ()
    run_plan: Mapping[str, Any] = field(default_factory=dict)
    backend: str = "flygym_healthy"
    study_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=utc_timestamp)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        required = {
            "name": self.name,
            "hypothesis": self.hypothesis,
            "falsifiable_prediction": self.falsifiable_prediction,
            "assay": self.assay,
            "primary_metric": self.primary_metric,
            "backend": self.backend,
        }
        missing = [key for key, value in required.items() if not str(value).strip()]
        if missing:
            raise ValueError(f"study fields are required: {', '.join(missing)}")
        if not self.candidates:
            raise ValueError("at least one candidate is required")
        candidate_ids = [item.candidate_id for item in self.candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("candidate_id values must be unique")
        object.__setattr__(self, "candidates", tuple(
            item if isinstance(item, CandidateSpec) else CandidateSpec.from_dict(item)
            for item in self.candidates
        ))
        object.__setattr__(self, "controls", tuple(dict(item) for item in self.controls))
        object.__setattr__(self, "sources", tuple(dict(item) for item in self.sources))

    @property
    def configuration_hash(self) -> str:
        return stable_hash(self.as_dict(include_identity=False))

    def as_dict(self, *, include_identity: bool = True) -> dict[str, Any]:
        payload = {
            "name": self.name,
            "hypothesis": self.hypothesis,
            "falsifiable_prediction": self.falsifiable_prediction,
            "assay": self.assay,
            "primary_metric": self.primary_metric,
            "candidates": [item.as_dict() for item in self.candidates],
            "controls": jsonable(self.controls),
            "sources": jsonable(self.sources),
            "run_plan": jsonable(self.run_plan),
            "backend": self.backend,
            "metadata": jsonable(self.metadata),
        }
        if include_identity:
            payload.update(
                {
                    "study_id": self.study_id,
                    "created_at": self.created_at,
                    "configuration_hash": self.configuration_hash,
                    "scientific_scope": WORKBENCH_SCOPE,
                }
            )
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "StudySpec":
        return cls(
            name=str(data["name"]),
            hypothesis=str(data["hypothesis"]),
            falsifiable_prediction=str(data["falsifiable_prediction"]),
            assay=str(data["assay"]),
            primary_metric=str(data["primary_metric"]),
            candidates=tuple(CandidateSpec.from_dict(item) for item in data.get("candidates", ())),
            controls=tuple(dict(item) for item in data.get("controls", ())),
            sources=tuple(dict(item) for item in data.get("sources", ())),
            run_plan=dict(data.get("run_plan", {})),
            backend=str(data.get("backend", "flygym_healthy")),
            study_id=str(data.get("study_id", uuid.uuid4())),
            created_at=str(data.get("created_at", utc_timestamp())),
            metadata=dict(data.get("metadata", {})),
        )


class JobStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class JobRecord:
    """Persisted unit of work submitted to one backend adapter."""

    job_id: str
    study_id: str
    backend: str
    config: Mapping[str, Any] = field(default_factory=dict)
    status: JobStatus = JobStatus.PENDING
    attempt: int = 0
    run_id: str | None = None
    artifact_dir: str | None = None
    manifest_path: str | None = None
    submitted_at: str = field(default_factory=utc_timestamp)
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        if not self.job_id.strip() or not self.study_id.strip() or not self.backend.strip():
            raise ValueError("job_id, study_id, and backend are required")
        if isinstance(self.status, str):
            self.status = JobStatus(self.status)

    def as_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "study_id": self.study_id,
            "backend": self.backend,
            "config": jsonable(self.config),
            "status": self.status.value,
            "attempt": self.attempt,
            "run_id": self.run_id,
            "artifact_dir": self.artifact_dir,
            "manifest_path": self.manifest_path,
            "submitted_at": self.submitted_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "error": self.error,
            "scientific_scope": WORKBENCH_SCOPE,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "JobRecord":
        return cls(
            job_id=str(data["job_id"]),
            study_id=str(data["study_id"]),
            backend=str(data["backend"]),
            config=dict(data.get("config", {})),
            status=JobStatus(str(data.get("status", JobStatus.PENDING.value))),
            attempt=int(data.get("attempt", 0)),
            run_id=data.get("run_id"),
            artifact_dir=data.get("artifact_dir"),
            manifest_path=data.get("manifest_path"),
            submitted_at=str(data.get("submitted_at", utc_timestamp())),
            started_at=data.get("started_at"),
            finished_at=data.get("finished_at"),
            error=data.get("error"),
        )


@dataclass(frozen=True)
class CapabilityDescriptor:
    name: str
    display_name: str
    ready: bool
    supported_assays: tuple[str, ...] = ()
    supported_interventions: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    requirements: tuple[str, ...] = ()
    supports_explicit_seed: bool = False
    supports_parameter_overrides: bool = False
    supports_timed_stimulus: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "ready": self.ready,
            "supported_assays": list(self.supported_assays),
            "supported_interventions": list(self.supported_interventions),
            "limitations": list(self.limitations),
            "requirements": list(self.requirements),
            "supports_explicit_seed": self.supports_explicit_seed,
            "supports_parameter_overrides": self.supports_parameter_overrides,
            "supports_timed_stimulus": self.supports_timed_stimulus,
            "scientific_scope": WORKBENCH_SCOPE,
        }


@dataclass(frozen=True)
class RunManifest:
    """Immutable-at-write provenance for one backend process attempt."""

    run_id: str
    job_id: str
    study_id: str
    backend: str
    status: JobStatus
    attempt: int
    configuration_hash: str
    command: tuple[str, ...]
    interpreter: str
    repo_root: str
    started_at: str
    finished_at: str
    exit_code: int | None
    artifact_hashes: Mapping[str, str] = field(default_factory=dict)
    provenance: Mapping[str, Any] = field(default_factory=dict)
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "manifest_version": 1,
            "run_id": self.run_id,
            "job_id": self.job_id,
            "study_id": self.study_id,
            "backend": self.backend,
            "status": self.status.value,
            "attempt": self.attempt,
            "configuration_hash": self.configuration_hash,
            "command": list(self.command),
            "interpreter": self.interpreter,
            "repo_root": self.repo_root,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "exit_code": self.exit_code,
            "artifact_hashes": dict(sorted(self.artifact_hashes.items())),
            "provenance": jsonable(self.provenance),
            "error": self.error,
            "scientific_scope": WORKBENCH_SCOPE,
        }


@dataclass(frozen=True)
class DecisionReport:
    """Conservative report that separates outputs from interpretation."""

    study_id: str
    generated_at: str
    status: str
    results: tuple[Mapping[str, Any], ...]
    uncertainty: Mapping[str, Any]
    limitations: tuple[str, ...]
    recommendations: tuple[str, ...]
    ranking_eligible: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "report_version": 1,
            "study_id": self.study_id,
            "generated_at": self.generated_at,
            "status": self.status,
            "results": jsonable(self.results),
            "uncertainty": jsonable(self.uncertainty),
            "limitations": list(self.limitations),
            "recommendations": list(self.recommendations),
            "ranking_eligible": self.ranking_eligible,
            "scientific_scope": WORKBENCH_SCOPE,
        }


__all__ = [
    "CandidateSpec",
    "CapabilityDescriptor",
    "DecisionReport",
    "JobRecord",
    "JobStatus",
    "RunManifest",
    "StudySpec",
    "WORKBENCH_SCOPE",
    "jsonable",
    "stable_hash",
    "utc_timestamp",
]
