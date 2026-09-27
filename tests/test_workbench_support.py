from __future__ import annotations

from drosophila_pd.workbench.models import CandidateSpec, CapabilityDescriptor, StudySpec
from drosophila_pd.workbench.support import MappingRecord, assess_study_support


def _study(*, candidate_metadata=None, candidate_intervention="activation", assay="sensory_mn9", backend="lif_2024"):
    return StudySpec(
        name="sensory screen",
        hypothesis="input changes the neural readout",
        falsifiable_prediction="MN9 differs from control",
        assay=assay,
        primary_metric="mn9_rate",
        backend=backend,
        candidates=(
            CandidateSpec("control", "No input", intervention={"type": "none"}),
            CandidateSpec(
                "sugar",
                "Sugar GRNs",
                target="sugar_grns",
                intervention={"type": candidate_intervention},
                metadata=candidate_metadata or {"mapping_id": "sugar-v1"},
            ),
        ),
        metadata={"dataset_id": "flywire-630", "id_namespace": "flywire_root_id"},
    )


def _mapping(**overrides):
    values = {
        "mapping_id": "sugar-v1",
        "biological_target": "sugar_grns",
        "backend": "lif_2024",
        "id_namespace": "flywire_root_id",
        "dataset_id": "flywire-630",
        "intervention_type": "activation",
        "target_ids": ("123", "456"),
        "sources": ({"citation": "paper", "locator": "figure 2"},),
        "review_status": "COMPUTATIONALLY_REVIEWED",
        "context": {"sex": "female", "stimulus": "sugar"},
        "reviewer": "curator",
        "reviewed_at": "2026-09-01T00:00:00Z",
    }
    values.update(overrides)
    return MappingRecord(**values)


def _capability(**overrides):
    values = {
        "name": "lif_2024",
        "display_name": "LIF",
        "ready": True,
        "supported_assays": ("sensory_mn9",),
        "supported_interventions": ("none", "activation"),
    }
    values.update(overrides)
    return CapabilityDescriptor(**values)


def test_support_assessment_allows_only_reviewed_supported_mapping():
    result = assess_study_support(_study(), _capability(), {"sugar-v1": _mapping()})

    assert result["status"] == "READY_FOR_COMPUTATIONAL_REVIEW"
    assert result["run_allowed"] is True
    assert result["candidate_assessments"]["sugar"]["status"] == "SUPPORTED_COMPUTATIONALLY"
    assert result["candidate_assessments"]["sugar"]["priority_eligible"] is True
    assert result["candidate_assessments"]["control"]["status"] == "SUPPORTED_CONTROL"


def test_missing_mapping_is_unassessable_and_never_priority_eligible():
    result = assess_study_support(_study(), _capability(), {})

    sugar = result["candidate_assessments"]["sugar"]
    assert sugar["status"] == "MAPPING_REQUIRED"
    assert sugar["priority_eligible"] is False
    assert result["run_allowed"] is False


def test_pending_mapping_review_may_not_enter_priority_list():
    mapping = _mapping(review_status="PENDING_SCIENTIFIC_REVIEW", reviewer=None, reviewed_at=None)
    result = assess_study_support(_study(), _capability(), {"sugar-v1": mapping})

    sugar = result["candidate_assessments"]["sugar"]
    assert sugar["status"] == "MAPPING_REVIEW_REQUIRED"
    assert sugar["priority_eligible"] is False


def test_assessment_rejects_mismatched_assay_intervention_dataset_and_context():
    capability = _capability(supported_assays=("locomotion",))
    mapping = _mapping(
        dataset_id="flywire-783",
        id_namespace="flywire-root-id-v2",
        intervention_type="outgoing_synapse_block",
    )
    result = assess_study_support(
        _study(assay="sensory_mn9", candidate_intervention="outgoing_synapse_block"),
        capability,
        {"sugar-v1": mapping},
        required_context={"sex": "male", "stimulus": "sugar"},
    )

    sugar = result["candidate_assessments"]["sugar"]
    assert sugar["status"] == "OUT_OF_SCOPE"
    assert set(sugar["reasons"]) >= {
        "unsupported_assay:sensory_mn9",
        "unsupported_intervention:outgoing_synapse_block",
        "mapping_dataset_mismatch:flywire-783",
        "mapping_namespace_mismatch:flywire-root-id-v2",
        "context_mismatch:sex",
    }
    assert sugar["priority_eligible"] is False


def test_mapping_requires_source_ids_namespace_and_review_identity():
    for change in (
        {"target_ids": ()},
        {"sources": ()},
        {"id_namespace": ""},
        {"review_status": "COMPUTATIONALLY_REVIEWED", "reviewer": None},
    ):
        try:
            _mapping(**change)
        except ValueError:
            continue
        raise AssertionError(f"invalid mapping accepted: {change}")


def test_mapping_record_round_trip_preserves_provenance():
    mapping = _mapping()
    restored = MappingRecord.from_dict(mapping.as_dict())

    assert restored.as_dict() == mapping.as_dict()
    assert restored.record_hash == mapping.record_hash
