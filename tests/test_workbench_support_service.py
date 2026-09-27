from __future__ import annotations

import sys

import pytest

from drosophila_pd.workbench import CandidateSpec, CapabilityDescriptor, StudySpec, WorkbenchService, WorkbenchStore
from drosophila_pd.workbench.adapters import CommandBackendAdapter
from drosophila_pd.workbench.selection import SelectionPolicy
from drosophila_pd.workbench.support import MappingRecord
from drosophila_pd.workbench.service import _neural_inventory_errors


def _service(tmp_path):
    script = tmp_path / "fixture.py"
    script.write_text("pass\n", encoding="utf-8")
    adapter = CommandBackendAdapter(
        name="fixture",
        descriptor=CapabilityDescriptor(
            name="fixture",
            display_name="fixture",
            ready=True,
            supported_assays=("sensory_mn9",),
            supported_interventions=("none", "activation"),
        ),
        repo_root=tmp_path,
        interpreter=sys.executable,
        command_factory=lambda _study, _config, _artifact: (sys.executable, "-c", "pass"),
        script_path=script,
    )
    return WorkbenchService(
        store=WorkbenchStore(tmp_path / "state.sqlite3"),
        artifact_root=tmp_path / "artifacts",
        adapters={"fixture": adapter},
    )


def _study():
    return StudySpec(
        name="support gated study",
        hypothesis="activation changes MN9",
        falsifiable_prediction="MN9 rate changes",
        assay="sensory_mn9",
        primary_metric="mn9_rate",
        backend="fixture",
        candidates=(
            CandidateSpec("control", "No input", intervention={"type": "none"}),
            CandidateSpec(
                "sugar",
                "Sugar neurons",
                target="sugar_grns",
                intervention={"type": "activation"},
                metadata={"mapping_id": "sugar-v1"},
            ),
        ),
        run_plan={
            "backend_requirements": {
                "dataset_id": "flywire-630",
                "id_namespace": "flywire_root_id",
                "input_ids": [],
            }
        },
        metadata={"workflow_contract": "support-gated-1", "dataset_id": "flywire-630", "id_namespace": "flywire_root_id", "context": {"sex": "female"}},
    )


def _mapping():
    return MappingRecord(
        mapping_id="sugar-v1",
        biological_target="sugar_grns",
        backend="fixture",
        id_namespace="flywire_root_id",
        dataset_id="flywire-630",
        intervention_type="activation",
        target_ids=("123", "456"),
        sources=({"citation": "paper", "locator": "Figure 2"},),
        review_status="COMPUTATIONALLY_REVIEWED",
        context={"sex": "female"},
        reviewer="curator",
        reviewed_at="2026-09-01T00:00:00Z",
    )


def test_gated_study_cannot_be_submitted_until_mapping_is_reviewed_and_frozen(tmp_path):
    service = _service(tmp_path)
    study = _study()
    service.create_study(study)
    with pytest.raises(ValueError, match="support_assessment_requires_researcher_approval"):
        service.submit_job(study.study_id, {"candidate_id": "sugar"})

    service.register_mapping_record(_mapping())
    assessment = service.assess_support(study.study_id)
    assert assessment["run_allowed"] is True
    assert service.get_support_assessment(study.study_id)["assessment_hash"] == assessment["assessment_hash"]

    with pytest.raises(ValueError, match="reviewer is required"):
        service.approve_support_assessment(study.study_id, reviewer=None)

    approval = service.approve_support_assessment(study.study_id, reviewer="principal investigator")
    assert approval["status"] == "FROZEN_FOR_COMPUTATIONAL_RUN"
    assert approval["assessment_hash"] == assessment["assessment_hash"]

    job = service.submit_job(study.study_id, {"candidate_id": "sugar"})
    assert job.status.value == "PENDING"
    assert job.config["input_ids"] == ["123", "456"]
    assert job.config["mapping_id"] == "sugar-v1"
    assert job.config["mapping_record_hash"] == _mapping().record_hash


def test_creating_research_study_immediately_persists_support_assessment(tmp_path):
    service = _service(tmp_path)
    study = _study()

    created = service.create_research_study(study)

    assert created.metadata["workflow_contract"] == "support-gated-1"
    assessment = service.get_support_assessment(created.study_id)
    assert assessment is not None
    assert assessment["study_configuration_hash"] == created.configuration_hash
    assert assessment["status"] == "MAPPING_REQUIRED"
    assert assessment["capability"]["ready"] is True


def test_research_creation_runs_backend_preflight_without_starting_simulation(tmp_path):
    service = _service(tmp_path)
    service.register_mapping_record(_mapping())
    adapter = service.adapters["fixture"]
    calls = []

    def fail_validation(study, config):
        calls.append((study.study_id, config["candidate_id"]))
        return ("declared readout is unavailable",) if config["candidate_id"] == "sugar" else ()

    adapter.validate = fail_validation
    created = service.create_research_study(_study())

    assessment = service.get_support_assessment(created.study_id)
    assert len(calls) == 2
    assert assessment["backend_preflight"]["status"] == "FAILED"
    assert assessment["status"] == "OUT_OF_SCOPE"
    assert assessment["run_allowed"] is False
    assert assessment["candidate_assessments"]["sugar"]["priority_eligible"] is False


def test_gated_jobs_reject_ids_or_backends_that_differ_from_reviewed_support(tmp_path):
    service = _service(tmp_path)
    study = _study()
    service.create_study(study)
    mapping = _mapping()
    service.register_mapping_record(mapping)
    service.assess_support(study.study_id)
    service.approve_support_assessment(study.study_id, reviewer="PI")

    with pytest.raises(ValueError, match="require a declared candidate_id"):
        service.submit_job(study.study_id, {})
    with pytest.raises(ValueError, match="not declared in the frozen StudySpec"):
        service.submit_job(study.study_id, {"candidate_id": "undeclared"})
    with pytest.raises(ValueError, match="differ from reviewed mapping"):
        service.submit_job(study.study_id, {"candidate_id": "sugar", "input_ids": ["999"]})
    with pytest.raises(ValueError, match="dataset_id differs from the frozen StudySpec"):
        service.submit_job(study.study_id, {"candidate_id": "sugar", "dataset_id": "flywire-elsewhere"})
    with pytest.raises(ValueError, match="readout_ids must be declared in the frozen StudySpec"):
        service.submit_job(study.study_id, {"candidate_id": "sugar", "readout_ids": ["999"]})
    with pytest.raises(ValueError, match="cannot override the frozen study backend"):
        service.submit_job(study.study_id, {"candidate_id": "sugar"}, backend="other")


def test_lif_id_inventory_preflight_rejects_ids_absent_from_declared_dataset(tmp_path):
    inventory = tmp_path / "completeness.csv"
    inventory.write_text("root_id,complete\n123,true\n777,true\n", encoding="utf-8")

    errors = _neural_inventory_errors(
        {
            "completeness": str(inventory),
            "input_ids": ["123", "456"],
            "readout_ids": ["777"],
        }
    )

    assert errors == ["neuron_id_not_in_declared_dataset:456"]


def test_unreviewed_or_missing_mapping_cannot_be_approved(tmp_path):
    service = _service(tmp_path)
    study = _study()
    service.create_study(study)
    assessment = service.assess_support(study.study_id)
    assert assessment["status"] == "MAPPING_REQUIRED"
    with pytest.raises(ValueError, match="support_assessment_not_run_allowed"):
        service.approve_support_assessment(study.study_id, reviewer="PI")

    pending = MappingRecord(
        **{
            **_mapping().__dict__,
            "review_status": "PENDING_SCIENTIFIC_REVIEW",
            "reviewer": None,
            "reviewed_at": None,
        }
    )
    service.register_mapping_record(pending)
    assessment = service.assess_support(study.study_id)
    assert assessment["status"] == "MAPPING_REVIEW_REQUIRED"
    with pytest.raises(ValueError, match="support_assessment_not_run_allowed"):
        service.approve_support_assessment(study.study_id, reviewer="PI")


def test_mapping_records_are_immutable_and_duplicate_registration_is_idempotent(tmp_path):
    service = _service(tmp_path)
    mapping = _mapping()

    assert service.register_mapping_record(mapping)["record_hash"] == mapping.record_hash
    assert service.register_mapping_record(mapping)["record_hash"] == mapping.record_hash
    assert service.list_mapping_records()["sugar-v1"]["record_hash"] == mapping.record_hash
    with pytest.raises(ValueError, match="mapping_id is immutable"):
        service.register_mapping_record(MappingRecord(**{**mapping.__dict__, "version": "2"}))


def test_selection_report_is_persisted_with_support_and_policy_hashes(tmp_path):
    service = _service(tmp_path)
    study = _study()
    service.create_study(study)
    service.register_mapping_record(_mapping())
    assessment = service.assess_support(study.study_id)
    service.approve_support_assessment(study.study_id, reviewer="PI")
    policy = SelectionPolicy(
        assay=study.assay,
        primary_metric=study.primary_metric,
        budget_k=2,
        study_id=study.study_id,
        control_candidate_id="control",
    )

    result = service.select_study(study.study_id, policy)

    assert result["support_assessment_hash"] == assessment["assessment_hash"]
    assert result["status"] == "INCOMPLETE_COLLECTION"
    assert result["selected"] == []
    persisted = service.artifact_root / study.study_id / "selection_report.json"
    assert persisted.is_file()


def test_intake_preview_persists_the_auditable_draft_path(tmp_path):
    class Provider:
        provider_id = "fixture"

        def extract(self, _text, *, source_uri=None):
            return {"hypothesis": "h", "falsifiable_prediction": "p", "assay": "a", "primary_metric": "m"}

    service = WorkbenchService(
        store=WorkbenchStore(tmp_path / "state.sqlite3"),
        artifact_root=tmp_path / "artifacts",
        adapters={},
        intake_provider=Provider(),
    )

    draft = service.preview_intake("protocol text", source_uri="https://example.org/protocol")

    import json

    persisted = json.loads(__import__("pathlib").Path(draft["artifact_path"]).read_text(encoding="utf-8"))
    assert persisted["draft_id"] == draft["draft_id"]
    assert persisted["artifact_path"] == draft["artifact_path"]
    assert persisted["study_created"] is False
    assert persisted["mapping_created"] is False


def test_selection_requires_current_frozen_support_assessment(tmp_path):
    service = _service(tmp_path)
    study = _study()
    service.create_study(study)
    policy = SelectionPolicy("sensory_mn9", "mn9_rate", 1, study_id=study.study_id, control_candidate_id="control")

    with pytest.raises(ValueError, match="support_assessment_requires_researcher_approval"):
        service.select_study(study.study_id, policy)
