"""Exact, review-aware resolution of AI draft targets to Workbench mappings.

This module deliberately does not perform fuzzy matching and never creates IDs.
The AI may propose a biological target name; only an explicit human choice can
bind that draft to an immutable, already-reviewed mapping record.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from drosophila_pd.workbench.models import CandidateSpec, StudySpec, stable_hash
from drosophila_pd.workbench.support import MappingRecord

from .contracts import AIStudySpec


REVIEWED_STATES = frozenset({"COMPUTATIONALLY_REVIEWED", "BIOLOGY_REVIEWED"})
_ID_KEYS = frozenset({
    "id", "ids", "neuron_id", "neuron_ids", "root_id", "root_ids",
    "target_id", "target_ids", "input_id", "input_ids", "readout_id",
    "readout_ids", "silence_ids", "mapping_id", "mapping_version",
    "mapping_record_hash",
})


def normalize_target(value: str) -> str:
    """Normalize whitespace and case only; this is not fuzzy/alias matching."""

    if not isinstance(value, str) or not value.strip():
        raise ValueError("biological_target is required")
    return " ".join(value.split()).casefold()


@dataclass(frozen=True)
class MappingRequest:
    biological_target: str
    backend: str
    dataset_id: str
    id_namespace: str
    intervention_type: str
    context: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        normalize_target(self.biological_target)
        for name in ("backend", "dataset_id", "id_namespace", "intervention_type"):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"{name} is required for mapping resolution")
        object.__setattr__(self, "context", dict(self.context))


@dataclass(frozen=True)
class MappingOption:
    mapping_id: str
    version: str
    record_hash: str
    review_status: str
    reviewer: str | None
    reviewed_at: str | None
    sources: tuple[Mapping[str, Any], ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "mapping_id": self.mapping_id,
            "version": self.version,
            "record_hash": self.record_hash,
            "review_status": self.review_status,
            "reviewer": self.reviewer,
            "reviewed_at": self.reviewed_at,
            "sources": [dict(item) for item in self.sources],
        }


@dataclass(frozen=True)
class MappingResolution:
    status: str
    request: MappingRequest
    options: tuple[MappingOption, ...] = ()
    pending_review_count: int = 0
    incompatible: tuple[Mapping[str, str], ...] = ()
    requires_human_selection: bool = False

    @property
    def ambiguous(self) -> bool:
        return len(self.options) > 1

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "ai-v2-mapping-resolution-1",
            "status": self.status,
            "request": {
                "biological_target": self.request.biological_target,
                "backend": self.request.backend,
                "dataset_id": self.request.dataset_id,
                "id_namespace": self.request.id_namespace,
                "intervention_type": self.request.intervention_type,
                "context": dict(self.request.context),
            },
            "options": [item.as_dict() for item in self.options],
            "pending_review_count": self.pending_review_count,
            "incompatible": [dict(item) for item in self.incompatible],
            "ambiguous": self.ambiguous,
            "requires_human_selection": self.requires_human_selection,
            "scientific_scope": "Registry resolution is not biological validation or approval.",
        }


@dataclass(frozen=True)
class MappingBinding:
    """Human-selected mapping reference; target IDs are registry-derived only."""

    mapping_id: str
    version: str
    record_hash: str
    biological_target: str
    backend: str
    dataset_id: str
    id_namespace: str
    intervention_type: str
    target_ids: tuple[str, ...]
    readout_ids: tuple[str, ...]
    sources: tuple[Mapping[str, Any], ...]
    review_status: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "mapping_id": self.mapping_id,
            "version": self.version,
            "record_hash": self.record_hash,
            "biological_target": self.biological_target,
            "backend": self.backend,
            "dataset_id": self.dataset_id,
            "id_namespace": self.id_namespace,
            "intervention_type": self.intervention_type,
            "target_ids": list(self.target_ids),
            "readout_ids": list(self.readout_ids),
            "sources": [dict(item) for item in self.sources],
            "review_status": self.review_status,
        }


def resolve_mapping(
    request: MappingRequest,
    records: Iterable[MappingRecord | Mapping[str, Any]],
) -> MappingResolution:
    """Find exact-name, context-compatible reviewed registry records.

    The result is always a menu for a human; even one exact match is not bound
    implicitly. Pending or rejected records are never returned as selectable.
    """

    parsed = _records(records)
    exact = [
        record for record in parsed
        if normalize_target(record.biological_target) == normalize_target(request.biological_target)
    ]
    if not exact:
        return MappingResolution("NOT_FOUND", request)

    compatible_reviewed: list[MappingRecord] = []
    pending_count = 0
    incompatible: list[Mapping[str, str]] = []
    for record in exact:
        mismatches = _contract_mismatches(request, record)
        if mismatches:
            incompatible.append({"mapping_id": record.mapping_id, "reason": ",".join(mismatches)})
            continue
        if record.review_status == "PENDING_SCIENTIFIC_REVIEW":
            pending_count += 1
        elif record.review_status in REVIEWED_STATES:
            if record.readout_ids:
                compatible_reviewed.append(record)
            else:
                incompatible.append({"mapping_id": record.mapping_id, "reason": "reviewed_readout_ids_missing"})
        else:
            incompatible.append({"mapping_id": record.mapping_id, "reason": "mapping_rejected"})

    if compatible_reviewed:
        options = tuple(
            MappingOption(
                mapping_id=record.mapping_id,
                version=record.version,
                record_hash=record.record_hash,
                review_status=record.review_status,
                reviewer=record.reviewer,
                reviewed_at=record.reviewed_at,
                sources=record.sources,
            )
            for record in sorted(compatible_reviewed, key=lambda row: (row.mapping_id, row.version))
        )
        return MappingResolution(
            "HUMAN_SELECTION_REQUIRED", request, options, pending_count,
            tuple(incompatible), requires_human_selection=True,
        )
    if pending_count:
        return MappingResolution("REVIEW_REQUIRED", request, pending_review_count=pending_count,
                                 incompatible=tuple(incompatible))
    return MappingResolution("INCOMPATIBLE", request, incompatible=tuple(incompatible))


def select_mapping(
    resolution: MappingResolution,
    records: Iterable[MappingRecord | Mapping[str, Any]],
    *,
    mapping_id: str,
    version: str,
    record_hash: str,
) -> MappingBinding:
    """Bind only the exact human-selected ID/version/hash from this resolution."""

    if resolution.status != "HUMAN_SELECTION_REQUIRED":
        raise ValueError("mapping resolution is not selectable")
    option = next((item for item in resolution.options if item.mapping_id == mapping_id), None)
    if option is None:
        raise ValueError("selected mapping_id was not offered by this resolution")
    if option.version != str(version) or option.record_hash != str(record_hash):
        raise ValueError("selected mapping version/hash is stale or mismatched")
    record = next((item for item in _records(records) if item.mapping_id == mapping_id), None)
    if record is None or record.version != str(version) or record.record_hash != str(record_hash):
        raise ValueError("selected mapping no longer matches the registry record")
    if record.review_status not in REVIEWED_STATES:
        raise ValueError("selected mapping is not reviewed")
    mismatches = _contract_mismatches(resolution.request, record)
    if mismatches:
        raise ValueError("selected mapping no longer matches request: " + ", ".join(mismatches))
    return MappingBinding(
        mapping_id=record.mapping_id,
        version=record.version,
        record_hash=record.record_hash,
        biological_target=record.biological_target,
        backend=record.backend,
        dataset_id=record.dataset_id,
        id_namespace=record.id_namespace,
        intervention_type=record.intervention_type,
        target_ids=record.target_ids,
        readout_ids=record.readout_ids,
        sources=record.sources,
        review_status=record.review_status,
    )


def bind_mapping_to_draft(
    draft: AIStudySpec,
    *,
    candidate_id: str,
    binding: MappingBinding,
) -> AIStudySpec:
    """Return a new DRAFT pinned to a mapping; do not self-approve or run it."""

    if not isinstance(draft, AIStudySpec) or draft.approval_status != "DRAFT":
        raise ValueError("only an AIStudySpec in DRAFT state can receive a mapping binding")
    if not binding.readout_ids:
        raise ValueError("selected reviewed mapping has no readout IDs")
    study = draft.study
    if study.backend != binding.backend:
        raise ValueError("mapping backend differs from draft StudySpec")
    dataset_id, id_namespace = _study_dataset_namespace(study)
    if dataset_id != binding.dataset_id or id_namespace != binding.id_namespace:
        raise ValueError("mapping dataset/namespace differs from draft StudySpec")
    candidate = next((item for item in study.candidates if item.candidate_id == candidate_id), None)
    if candidate is None:
        raise ValueError("candidate_id is not present in the draft StudySpec")
    if normalize_target(candidate.target or "") != normalize_target(binding.biological_target):
        raise ValueError("draft target differs from the selected mapping target")
    intervention_type = str(candidate.intervention.get("type", "none")).strip() or "none"
    if intervention_type == "none" or intervention_type != binding.intervention_type:
        raise ValueError("draft intervention differs from the selected mapping")
    if _contains_id_or_mapping_claim(candidate.intervention) or _contains_id_or_mapping_claim(candidate.metadata):
        raise ValueError("AI draft contains IDs or a self-authored mapping reference")
    if _contains_id_or_mapping_claim(study.run_plan):
        raise ValueError("AI draft contains model IDs in its run plan; use reviewed registry values")

    run_plan = dict(study.run_plan)
    requirements = dict(run_plan.get("backend_requirements", {}))
    declared_readouts = requirements.get("readout_ids")
    if declared_readouts is not None and tuple(str(item) for item in declared_readouts) != binding.readout_ids:
        raise ValueError("draft readout IDs differ from the selected reviewed mapping")
    requirements["dataset_id"] = binding.dataset_id
    requirements["id_namespace"] = binding.id_namespace
    requirements["readout_ids"] = list(binding.readout_ids)
    run_plan["backend_requirements"] = requirements

    metadata = dict(candidate.metadata)
    metadata.update({
        "mapping_id": binding.mapping_id,
        "mapping_version": binding.version,
        "mapping_record_hash": binding.record_hash,
    })
    sources = _unique_dicts((*candidate.sources, *binding.sources))
    bound_candidate = CandidateSpec(
        candidate_id=candidate.candidate_id,
        label=candidate.label,
        target=candidate.target,
        intervention=dict(candidate.intervention),
        expected_direction=candidate.expected_direction,
        sources=sources,
        metadata=metadata,
    )
    candidates = tuple(bound_candidate if item.candidate_id == candidate_id else item for item in study.candidates)
    bound_study = StudySpec(
        name=study.name,
        hypothesis=study.hypothesis,
        falsifiable_prediction=study.falsifiable_prediction,
        assay=study.assay,
        primary_metric=study.primary_metric,
        candidates=candidates,
        controls=study.controls,
        sources=study.sources,
        run_plan=run_plan,
        backend=study.backend,
        study_id=study.study_id,
        created_at=study.created_at,
        metadata=study.metadata,
    )
    return AIStudySpec(
        bound_study,
        draft.evidence_ids,
        approval_status="DRAFT",
        provenance=draft.provenance,
    )


def _records(values: Iterable[MappingRecord | Mapping[str, Any]]) -> tuple[MappingRecord, ...]:
    parsed: dict[str, MappingRecord] = {}
    for value in values:
        record = value if isinstance(value, MappingRecord) else MappingRecord.from_dict(value)
        prior = parsed.get(record.mapping_id)
        if prior is not None and prior.record_hash != record.record_hash:
            raise ValueError(f"conflicting registry records share mapping_id: {record.mapping_id}")
        parsed[record.mapping_id] = record
    return tuple(parsed[key] for key in sorted(parsed))


def _contract_mismatches(request: MappingRequest, record: MappingRecord) -> list[str]:
    mismatches = []
    for field_name in ("backend", "dataset_id", "id_namespace", "intervention_type"):
        if str(getattr(record, field_name)) != str(getattr(request, field_name)):
            mismatches.append(f"{field_name}_mismatch")
    for key, expected in request.context.items():
        if key not in record.context:
            mismatches.append(f"context_unspecified:{key}")
        elif record.context[key] != expected:
            mismatches.append(f"context_mismatch:{key}")
    return mismatches


def _study_dataset_namespace(study: StudySpec) -> tuple[str, str]:
    requirements = study.run_plan.get("backend_requirements", {})
    if not isinstance(requirements, Mapping):
        requirements = {}
    dataset_id = study.metadata.get("dataset_id") or requirements.get("dataset_id")
    namespace = study.metadata.get("id_namespace") or requirements.get("id_namespace")
    if not dataset_id or not namespace:
        raise ValueError("draft StudySpec must declare dataset_id and id_namespace")
    if study.metadata.get("dataset_id") and requirements.get("dataset_id") and study.metadata["dataset_id"] != requirements["dataset_id"]:
        raise ValueError("StudySpec dataset metadata conflict")
    if study.metadata.get("id_namespace") and requirements.get("id_namespace") and study.metadata["id_namespace"] != requirements["id_namespace"]:
        raise ValueError("StudySpec namespace metadata conflict")
    return str(dataset_id), str(namespace)


def _contains_id_or_mapping_claim(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(str(key).strip().casefold() in _ID_KEYS or _contains_id_or_mapping_claim(item)
                   for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return any(_contains_id_or_mapping_claim(item) for item in value)
    return False


def _unique_dicts(values: Iterable[Mapping[str, Any]]) -> tuple[Mapping[str, Any], ...]:
    unique: dict[str, Mapping[str, Any]] = {}
    for value in values:
        row = dict(value)
        unique[stable_hash(row)] = row
    return tuple(unique[key] for key in sorted(unique))


__all__ = [
    "MappingBinding", "MappingOption", "MappingRequest", "MappingResolution",
    "bind_mapping_to_draft", "normalize_target", "resolve_mapping", "select_mapping",
]
