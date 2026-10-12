from __future__ import annotations

import pytest

from drosophila_pd.ai_v2.contracts import AIStudySpec
from drosophila_pd.ai_v2.mapping_resolution import (
    MappingRequest,
    bind_mapping_to_draft,
    resolve_mapping,
    select_mapping,
)
from drosophila_pd.workbench.models import CandidateSpec, StudySpec
from drosophila_pd.workbench.support import MappingRecord


def _record(**overrides):
    data = {
        "mapping_id": "target-map-v1",
        "version": "1",
        "biological_target": "Sugar sensory neurons",
        "backend": "fixture",
        "id_namespace": "fixture_id",
        "dataset_id": "fixture_connectome",
        "intervention_type": "activation",
        "target_ids": ("ID_FROM_REGISTRY_1", "ID_FROM_REGISTRY_2"),
        "readout_ids": ("REVIEWED_READOUT_1",),
        "sources": ({"citation": "fixture source", "locator": "fixture section"},),
        "review_status": "COMPUTATIONALLY_REVIEWED",
        "context": {"stimulus": "sugar"},
        "reviewer": "reviewer-1",
        "reviewed_at": "2026-10-01T00:00:00Z",
        "limitations": ("Fixture mapping for contract tests only.",),
    }
    data.update(overrides)
    return MappingRecord(**data)


def _request(**overrides):
    data = {
        "biological_target": " sugar   sensory neurons ",
        "backend": "fixture",
        "id_namespace": "fixture_id",
        "dataset_id": "fixture_connectome",
        "intervention_type": "activation",
        "context": {"stimulus": "sugar"},
    }
    data.update(overrides)
    return MappingRequest(**data)


def _draft(*, candidate_metadata=None, provenance=None, run_plan=None):
    study = StudySpec(
        name="Draft only",
        hypothesis="A proposed response changes",
        falsifiable_prediction="The declared metric changes",
        assay="synthetic_demo",
        primary_metric="metrics.response",
        backend="fixture",
        candidates=(
            CandidateSpec("control", "Control", intervention={"type": "none"}),
            CandidateSpec(
                "condition", "Condition", target="Sugar sensory neurons",
                intervention={"type": "activation"}, metadata=candidate_metadata or {},
            ),
        ),
        run_plan=run_plan or {"backend_requirements": {"dataset_id": "fixture_connectome", "id_namespace": "fixture_id"}},
        metadata={"dataset_id": "fixture_connectome", "id_namespace": "fixture_id"},
    )
    return AIStudySpec(study, ("EVIDENCE_CHUNK_1",), provenance=provenance)


def test_exact_match_only_and_always_requires_human_selection():
    record = _record()
    result = resolve_mapping(_request(), [record])

    assert result.status == "HUMAN_SELECTION_REQUIRED"
    assert result.requires_human_selection is True
    assert result.ambiguous is False
    assert result.options[0].mapping_id == record.mapping_id
    assert "target_ids" not in result.as_dict()["options"][0]
    assert resolve_mapping(_request(biological_target="Sugar sensory neurons-like"), [record]).status == "NOT_FOUND"


def test_ambiguous_match_requires_explicit_id_version_and_hash():
    first = _record()
    second = _record(mapping_id="target-map-v2", version="2", target_ids=("ID_OTHER",))
    result = resolve_mapping(_request(), [first, second])

    assert result.status == "HUMAN_SELECTION_REQUIRED"
    assert result.ambiguous is True
    with pytest.raises(ValueError, match="was not offered"):
        select_mapping(result, [first, second], mapping_id="invented", version="1", record_hash=first.record_hash)
    with pytest.raises(ValueError, match="stale or mismatched"):
        select_mapping(result, [first, second], mapping_id=first.mapping_id, version="2", record_hash=first.record_hash)
    selected = select_mapping(
        result, [first, second], mapping_id=second.mapping_id,
        version=second.version, record_hash=second.record_hash,
    )
    assert selected.target_ids == ("ID_OTHER",)


def test_unreviewed_and_incompatible_mapping_records_fail_closed():
    pending = _record(review_status="PENDING_SCIENTIFIC_REVIEW", reviewer=None, reviewed_at=None)
    assert resolve_mapping(_request(), [pending]).status == "REVIEW_REQUIRED"
    assert resolve_mapping(_request(dataset_id="other"), [_record()]).status == "INCOMPATIBLE"
    rejected = _record(review_status="REJECTED", reviewer=None, reviewed_at=None)
    assert resolve_mapping(_request(), [rejected]).status == "INCOMPATIBLE"
    no_readout = _record(readout_ids=())
    unresolved = resolve_mapping(_request(), [no_readout])
    assert unresolved.status == "INCOMPATIBLE"
    assert unresolved.incompatible[0]["reason"] == "reviewed_readout_ids_missing"


def test_binding_pins_mapping_but_never_inserts_registry_ids_into_ai_draft():
    record = _record()
    resolution = resolve_mapping(_request(), [record])
    option = resolution.options[0]
    binding = select_mapping(
        resolution, [record], mapping_id=option.mapping_id,
        version=option.version, record_hash=option.record_hash,
    )
    original = _draft(provenance={"provider_id": "fixture", "prompt_version": "p1"})
    bound = bind_mapping_to_draft(original, candidate_id="condition", binding=binding)
    candidate = next(row for row in bound.study.candidates if row.candidate_id == "condition")

    assert bound.approval_status == "DRAFT"
    assert bound.provenance == original.provenance
    assert candidate.metadata["mapping_id"] == record.mapping_id
    assert candidate.metadata["mapping_version"] == record.version
    assert candidate.metadata["mapping_record_hash"] == record.record_hash
    assert bound.study.run_plan["backend_requirements"]["readout_ids"] == ["REVIEWED_READOUT_1"]
    assert "target_ids" not in candidate.metadata
    assert not {"input_ids", "readout_ids"} & set(candidate.intervention)
    assert bound.study.configuration_hash != original.study.configuration_hash


def test_binding_rejects_llm_authored_ids_and_wrong_candidate_context():
    record = _record()
    result = resolve_mapping(_request(), [record])
    binding = select_mapping(
        result, [record], mapping_id=record.mapping_id,
        version=record.version, record_hash=record.record_hash,
    )
    with pytest.raises(ValueError, match="contains IDs"):
        bind_mapping_to_draft(_draft(candidate_metadata={"target_ids": ["hallucinated"]}), candidate_id="condition", binding=binding)
    with pytest.raises(ValueError, match="dataset metadata conflict"):
        wrong = _draft()
        wrong_study = StudySpec.from_dict({**wrong.study.as_dict(), "metadata": {"dataset_id": "other", "id_namespace": "fixture_id"}})
        bind_mapping_to_draft(AIStudySpec(wrong_study, wrong.evidence_ids), candidate_id="condition", binding=binding)
    with pytest.raises(ValueError, match="model IDs in its run plan"):
        bind_mapping_to_draft(
            _draft(run_plan={"backend_requirements": {
                "dataset_id": "fixture_connectome", "id_namespace": "fixture_id",
                "readout_ids": ["AI_INVENTED_READOUT"],
            }}),
            candidate_id="condition", binding=binding,
        )
