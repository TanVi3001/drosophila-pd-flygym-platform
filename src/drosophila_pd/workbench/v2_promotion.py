"""Human-attested handoff from a stored AI draft to a support-gated StudySpec."""

from __future__ import annotations

from typing import Any, Mapping

from .models import CapabilityDescriptor, StudySpec, stable_hash, utc_timestamp
from .study_spec_draft import DRAFT_SCHEMA
from .support import MappingRecord, assess_study_support


def prepare_reviewed_study(
    *,
    draft: Mapping[str, Any],
    draft_sha256: str,
    reviewer: str,
    review_decision: str,
    evaluation_split: str,
    study_payload: Mapping[str, Any],
    capability: CapabilityDescriptor,
    mappings: Mapping[str, MappingRecord],
) -> StudySpec:
    """Validate a complete human-supplied design; never fill execution fields with AI."""
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise ValueError("draft reviewer is required")
    if review_decision != "APPROVED":
        raise ValueError("explicit draft review_decision=APPROVED is required")
    if not isinstance(evaluation_split, str) or evaluation_split not in {"development", "synthetic_fixture"}:
        raise ValueError("promotion permits development or synthetic_fixture only; held-out is locked")
    if (draft.get("schema_version") != DRAFT_SCHEMA
            or draft.get("workflow_mode") != "DRAFT_ONLY"
            or draft.get("status") != "DRAFT_REQUIRES_RESEARCHER_REVIEW"
            or not draft.get("retrieved_evidence_ids")):
        raise ValueError("promotion requires an evidence-backed V2 draft with the current schema")
    for flag in ("approved", "study_created", "mapping_created", "job_created", "graph_used", "simulation_started"):
        if draft.get(flag) is not False:
            raise ValueError(f"draft invariant violated: {flag}")
    if not isinstance(study_payload, Mapping):
        raise ValueError("reviewed study must be an object")
    required = {
        "study_id", "name", "hypothesis", "falsifiable_prediction", "assay",
        "primary_metric", "backend", "candidates", "controls", "run_plan", "metadata",
    }
    allowed = required | {"sources", "created_at"}
    if required - set(study_payload) or set(study_payload) - allowed:
        raise ValueError("reviewed study keys mismatch; provide all required fields explicitly")
    for field in ("study_id", "name", "hypothesis", "falsifiable_prediction", "assay", "primary_metric", "backend"):
        if not isinstance(study_payload[field], str) or not study_payload[field].strip():
            raise ValueError(f"reviewed study {field} must be non-empty text")
    if not isinstance(study_payload["metadata"], Mapping):
        raise ValueError("reviewed study metadata must be an object")
    metadata = dict(study_payload["metadata"])
    if "ai_draft_lineage" in metadata or "workflow_contract" in metadata:
        raise ValueError("reviewed study cannot supply reserved promotion metadata")
    if metadata.get("evaluation_split", evaluation_split) != evaluation_split:
        raise ValueError("reviewed study evaluation_split conflicts with the promotion request")
    if not isinstance(metadata.get("primary_metric_unit"), str) or not metadata["primary_metric_unit"].strip():
        raise ValueError("human-confirmed metadata.primary_metric_unit is required")
    metric = study_payload["primary_metric"].casefold()
    if (metric == "mn9_rate" or metric.endswith("_hz")) and metadata["primary_metric_unit"].strip().casefold() not in {"hz", "hertz"}:
        raise ValueError("reviewed metric/unit mismatch: this metric identifier requires Hz")
    if not isinstance(study_payload["run_plan"], Mapping) or not study_payload["run_plan"]:
        raise ValueError("an explicit non-empty human run_plan is required")
    if not isinstance(study_payload["candidates"], list) or not study_payload["candidates"]:
        raise ValueError("human-specified candidates are required")
    for candidate in study_payload["candidates"]:
        if (not isinstance(candidate, Mapping)
                or not isinstance(candidate.get("intervention"), Mapping)
                or not isinstance(candidate["intervention"].get("type"), str)
                or not candidate["intervention"]["type"].strip()):
            raise ValueError("each human candidate requires an explicit intervention.type")
        if set(candidate) - {"candidate_id", "label", "target", "intervention", "expected_direction", "sources", "metadata"}:
            raise ValueError("human candidate contains unsupported fields")
        for field in ("candidate_id", "label"):
            if not isinstance(candidate.get(field), str) or not candidate[field].strip():
                raise ValueError(f"human candidate requires non-empty {field}")
        if candidate["intervention"]["type"] != candidate["intervention"]["type"].strip():
            raise ValueError("intervention.type must be a canonical identifier without whitespace")
        if not isinstance(candidate.get("metadata", {}), Mapping):
            raise ValueError("human candidate metadata must be an object")
        mapping_id = candidate.get("metadata", {}).get("mapping_id")
        if mapping_id is not None and (not isinstance(mapping_id, str) or mapping_id != mapping_id.strip()):
            raise ValueError("selected mapping_id must be an exact registry identifier")
    if (not isinstance(study_payload["controls"], list)
            or any(not isinstance(control, Mapping) or not isinstance(control.get("candidate_id"), str)
                   for control in study_payload["controls"])):
        raise ValueError("controls must be a list with explicit candidate_id values")
    study = StudySpec.from_dict(study_payload)
    control_ids = {item.candidate_id for item in study.candidates if item.intervention["type"] == "none"}
    if not control_ids or not study.controls:
        raise ValueError("an explicit control candidate and controls declaration are required")
    declared_controls = {item.get("candidate_id") for item in study.controls}
    if declared_controls != control_ids:
        raise ValueError("controls must identify exactly the declared no-intervention candidates")
    assessment = assess_study_support(study, capability, mappings)
    if not assessment["run_allowed"]:
        reasons = sorted({
            reason for item in assessment["candidate_assessments"].values()
            for reason in item["reasons"]
        })
        raise ValueError("reviewed_study_support_blocked: " + "; ".join(reasons or [assessment["status"]]))
    selected = {
        item.metadata["mapping_id"]: mappings[item.metadata["mapping_id"]].record_hash
        for item in study.candidates if item.intervention["type"] != "none"
    }
    reviewed_fields = {
        "title": study.name, "hypothesis": study.hypothesis,
        "falsifiable_prediction": study.falsifiable_prediction,
        "assay": study.assay, "primary_metric": study.primary_metric,
        "primary_metric_unit": metadata["primary_metric_unit"],
        "context": metadata.get("context", {}),
    }
    proposed = draft.get("proposed_fields", {})
    lineage = {
        "schema_version": "workbench-v2-draft-promotion-1",
        "draft_id": draft["draft_id"],
        "draft_sha256": draft_sha256,
        "research_question_sha256": draft.get("research_question_sha256"),
        "evidence_corpus_sha256": draft.get("corpus_sha256"),
        "prompt_template_sha256": draft.get("prompt_sha256"),
        "draft_provider_id": draft.get("provider_id"),
        "retrieved_evidence_ids": list(draft["retrieved_evidence_ids"]),
        "draft_field_citations": draft.get("field_citations", {}),
        "reviewer": reviewer.strip(),
        "reviewer_identity_basis": "CALLER_ATTESTATION_LOCAL_API_NOT_AUTHENTICATED",
        "review_decision": review_decision,
        "reviewed_at": utc_timestamp(),
        "evaluation_split": evaluation_split,
        "reviewed_study_payload_sha256": stable_hash(study_payload),
        "edited_or_completed_fields": sorted(
            field for field, value in reviewed_fields.items() if proposed.get(field) != value
        ),
        "selected_mapping_hashes": selected,
        "run_approval_granted": False,
    }
    metadata["ai_draft_lineage"] = lineage
    metadata["workflow_contract"] = "support-gated-1"
    payload = study.as_dict(include_identity=False)
    payload.update(study_id=study.study_id, created_at=study.created_at, metadata=metadata)
    return StudySpec.from_dict(payload)
