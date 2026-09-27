"""Evidence-linked checks that keep backend support separate from biology claims."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .models import CapabilityDescriptor, StudySpec, stable_hash


MAPPING_REVIEW_STATES = {
    "PENDING_SCIENTIFIC_REVIEW",
    "COMPUTATIONALLY_REVIEWED",
    "BIOLOGY_REVIEWED",
    "REJECTED",
}


@dataclass(frozen=True)
class MappingRecord:
    """Versionable record tying a biological target to a declared model operation."""

    mapping_id: str
    biological_target: str
    backend: str
    id_namespace: str
    dataset_id: str
    intervention_type: str
    target_ids: tuple[str, ...]
    sources: tuple[Mapping[str, Any], ...]
    review_status: str = "PENDING_SCIENTIFIC_REVIEW"
    context: Mapping[str, Any] = field(default_factory=dict)
    reviewer: str | None = None
    reviewed_at: str | None = None
    limitations: tuple[str, ...] = ()
    version: str = "1"

    def __post_init__(self) -> None:
        for name in (
            "mapping_id",
            "biological_target",
            "backend",
            "id_namespace",
            "dataset_id",
            "intervention_type",
            "version",
        ):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"{name} is required")
        ids = tuple(str(value).strip() for value in self.target_ids)
        if not ids or any(not value for value in ids):
            raise ValueError("target_ids must contain non-empty identifiers")
        if len(ids) != len(set(ids)):
            raise ValueError("target_ids must be unique")
        object.__setattr__(self, "target_ids", ids)
        sources = tuple(dict(item) for item in self.sources)
        if not sources or any(not (item.get("citation") or item.get("locator")) for item in sources):
            raise ValueError("each mapping source requires a citation or locator")
        object.__setattr__(self, "sources", sources)
        state = str(self.review_status).strip().upper()
        if state not in MAPPING_REVIEW_STATES:
            raise ValueError(f"unsupported review_status: {state}")
        object.__setattr__(self, "review_status", state)
        if state in {"COMPUTATIONALLY_REVIEWED", "BIOLOGY_REVIEWED"}:
            if not (self.reviewer and self.reviewer.strip() and self.reviewed_at and self.reviewed_at.strip()):
                raise ValueError("a reviewed mapping requires reviewer and reviewed_at")
        object.__setattr__(self, "context", dict(self.context))
        object.__setattr__(self, "limitations", tuple(str(item) for item in self.limitations))

    @property
    def record_hash(self) -> str:
        return stable_hash(self._payload())

    def as_dict(self) -> dict[str, Any]:
        payload = self._payload()
        payload["record_hash"] = self.record_hash
        return payload

    def _payload(self) -> dict[str, Any]:
        return {
            "mapping_id": self.mapping_id,
            "version": self.version,
            "biological_target": self.biological_target,
            "backend": self.backend,
            "id_namespace": self.id_namespace,
            "dataset_id": self.dataset_id,
            "intervention_type": self.intervention_type,
            "target_ids": list(self.target_ids),
            "sources": [dict(item) for item in self.sources],
            "review_status": self.review_status,
            "context": dict(self.context),
            "reviewer": self.reviewer,
            "reviewed_at": self.reviewed_at,
            "limitations": list(self.limitations),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "MappingRecord":
        record = cls(
            mapping_id=str(value["mapping_id"]),
            version=str(value.get("version", "1")),
            biological_target=str(value["biological_target"]),
            backend=str(value["backend"]),
            id_namespace=str(value["id_namespace"]),
            dataset_id=str(value["dataset_id"]),
            intervention_type=str(value["intervention_type"]),
            target_ids=tuple(str(item) for item in value.get("target_ids", ())),
            sources=tuple(dict(item) for item in value.get("sources", ())),
            review_status=str(value.get("review_status", "PENDING_SCIENTIFIC_REVIEW")),
            context=dict(value.get("context", {})),
            reviewer=None if value.get("reviewer") is None else str(value["reviewer"]),
            reviewed_at=None if value.get("reviewed_at") is None else str(value["reviewed_at"]),
            limitations=tuple(str(item) for item in value.get("limitations", ())),
        )
        declared_hash = value.get("record_hash")
        if declared_hash is not None and str(declared_hash) != record.record_hash:
            raise ValueError("mapping record_hash does not match its contents")
        return record


def assess_study_support(
    study: StudySpec,
    capability: CapabilityDescriptor,
    mappings: Mapping[str, MappingRecord],
    *,
    required_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Assess declared candidates without inventing missing biology or IDs."""

    study_context = dict(required_context or study.metadata.get("context", {}))
    requirements = study.run_plan.get("backend_requirements", {})
    if not isinstance(requirements, Mapping):
        requirements = {}
    metadata_dataset = study.metadata.get("dataset_id")
    requirements_dataset = requirements.get("dataset_id")
    declared_dataset = metadata_dataset or requirements_dataset
    metadata_namespace = study.metadata.get("id_namespace")
    requirements_namespace = requirements.get("id_namespace")
    declared_namespace = metadata_namespace or requirements_namespace
    study_contract_reasons: list[str] = []
    if metadata_dataset and requirements_dataset and str(metadata_dataset) != str(requirements_dataset):
        study_contract_reasons.append("study_dataset_metadata_conflict")
    if metadata_namespace and requirements_namespace and str(metadata_namespace) != str(requirements_namespace):
        study_contract_reasons.append("study_namespace_metadata_conflict")
    candidate_assessments: dict[str, dict[str, Any]] = {}
    for candidate in study.candidates:
        intervention_type = str(candidate.intervention.get("type", "none")).strip() or "none"
        reasons: list[str] = list(study_contract_reasons)
        mapping: MappingRecord | None = None
        if not capability.ready:
            reasons.append("backend_not_ready")
        if study.assay not in capability.supported_assays:
            reasons.append(f"unsupported_assay:{study.assay}")
        if intervention_type not in capability.supported_interventions:
            reasons.append(f"unsupported_intervention:{intervention_type}")

        if intervention_type == "none":
            status = "SUPPORTED_CONTROL" if not reasons else "OUT_OF_SCOPE"
            priority_eligible = False
        else:
            mapping_id = str(candidate.metadata.get("mapping_id", "")).strip()
            mapping = mappings.get(mapping_id)
            if not mapping_id or mapping is None:
                reasons.append("mapping_record_missing")
                status = "MAPPING_REQUIRED"
                priority_eligible = False
            else:
                if mapping.backend != capability.name:
                    reasons.append(f"mapping_backend_mismatch:{mapping.backend}")
                if mapping.intervention_type != intervention_type:
                    reasons.append(f"mapping_intervention_mismatch:{mapping.intervention_type}")
                if candidate.target and candidate.target != mapping.biological_target:
                    reasons.append(f"mapping_target_mismatch:{mapping.biological_target}")
                if not declared_dataset:
                    reasons.append("mapping_dataset_unspecified")
                elif str(declared_dataset) != mapping.dataset_id:
                    reasons.append(f"mapping_dataset_mismatch:{mapping.dataset_id}")
                if not declared_namespace:
                    reasons.append("mapping_namespace_unspecified")
                elif str(declared_namespace) != mapping.id_namespace:
                    reasons.append(f"mapping_namespace_mismatch:{mapping.id_namespace}")
                for key, expected in study_context.items():
                    if key not in mapping.context:
                        reasons.append(f"context_unspecified:{key}")
                    elif mapping.context[key] != expected:
                        reasons.append(f"context_mismatch:{key}")
                if mapping.review_status == "REJECTED":
                    reasons.append("mapping_rejected")
                if mapping.review_status == "PENDING_SCIENTIFIC_REVIEW":
                    reasons.append("mapping_review_required")
                if not reasons:
                    status = "SUPPORTED_BIOLOGICALLY" if mapping.review_status == "BIOLOGY_REVIEWED" else "SUPPORTED_COMPUTATIONALLY"
                    priority_eligible = True
                elif "mapping_review_required" in reasons:
                    status = "MAPPING_REVIEW_REQUIRED"
                    priority_eligible = False
                else:
                    status = "OUT_OF_SCOPE"
                    priority_eligible = False

        if reasons and status == "SUPPORTED_CONTROL":
            status = "OUT_OF_SCOPE"
        candidate_assessments[candidate.candidate_id] = {
            "candidate_id": candidate.candidate_id,
            "status": status,
            "run_allowed": status in {"SUPPORTED_CONTROL", "SUPPORTED_COMPUTATIONALLY", "SUPPORTED_BIOLOGICALLY"},
            "priority_eligible": priority_eligible,
            "mapping_id": None if mapping is None else mapping.mapping_id,
            "mapping_hash": None if mapping is None else mapping.record_hash,
            "mapping_review_status": None if mapping is None else mapping.review_status,
            "dataset_id": None if mapping is None else mapping.dataset_id,
            "id_namespace": None if mapping is None else mapping.id_namespace,
            "target_ids": [] if mapping is None else list(mapping.target_ids),
            "source_evidence": [] if mapping is None else [dict(item) for item in mapping.sources],
            "limitations": [] if mapping is None else list(mapping.limitations),
            "reasons": sorted(set(reasons)),
        }

    non_controls = [
        item for item in candidate_assessments.values() if item["status"] != "SUPPORTED_CONTROL"
    ]
    run_allowed = capability.ready and bool(non_controls) and all(item["run_allowed"] for item in candidate_assessments.values())
    if not capability.ready or any(item["status"] == "OUT_OF_SCOPE" for item in non_controls):
        status = "OUT_OF_SCOPE"
    elif any(item["status"] == "MAPPING_REQUIRED" for item in non_controls):
        status = "MAPPING_REQUIRED"
    elif any(item["status"] == "MAPPING_REVIEW_REQUIRED" for item in non_controls):
        status = "MAPPING_REVIEW_REQUIRED"
    elif run_allowed:
        status = "READY_FOR_COMPUTATIONAL_REVIEW"
    else:
        status = "MAPPING_REQUIRED"

    result = {
        "schema_version": "study-support-assessment-1",
        "study_id": study.study_id,
        "study_configuration_hash": study.configuration_hash,
        "backend": capability.name,
        "assay": study.assay,
        "status": status,
        "run_allowed": run_allowed,
        "capability": capability.as_dict(),
        "requires_researcher_approval": True,
        "candidate_assessments": candidate_assessments,
        "scientific_scope": "Capability and mapping provenance review; computational support does not establish biological validity.",
    }
    result["assessment_hash"] = stable_hash(result)
    return result


__all__ = ["MappingRecord", "MAPPING_REVIEW_STATES", "assess_study_support"]
