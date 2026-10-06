from __future__ import annotations

import json
import sys

import pytest

from drosophila_pd.workbench import CandidateSpec, CapabilityDescriptor, StudySpec
from drosophila_pd.workbench.adapters import CommandBackendAdapter
from drosophila_pd.workbench.service import WorkbenchService
from drosophila_pd.workbench.store import WorkbenchStore
from drosophila_pd.workbench.models import stable_hash
from drosophila_pd.workbench.support import MappingRecord
from drosophila_pd.workbench.v2_automation import WorkbenchV2Automation


def _service(tmp_path, *, command: str = "pass") -> WorkbenchService:
    script = tmp_path / "fixture.py"
    script.write_text("pass\n", encoding="utf-8")
    adapter = CommandBackendAdapter(
        name="fixture",
        descriptor=CapabilityDescriptor(
            name="fixture",
            display_name="Fixture backend",
            ready=True,
            supported_assays=("sensory_mn9",),
            supported_interventions=("none", "activation"),
        ),
        repo_root=tmp_path,
        interpreter=sys.executable,
        command_factory=lambda _study, _config, _artifact: (sys.executable, "-c", command),
        script_path=script,
    )
    return WorkbenchService(
        store=WorkbenchStore(tmp_path / "state.sqlite3"),
        artifact_root=tmp_path / "artifacts",
        adapters={"fixture": adapter},
    )


def _study(study_id: str = "a03-fixture-study") -> StudySpec:
    return StudySpec(
        study_id=study_id,
        name="Synthetic A03 contract test",
        hypothesis="a declared input changes the declared readout",
        falsifiable_prediction="the MN9 readout differs from control",
        assay="sensory_mn9",
        primary_metric="mn9_rate",
        backend="fixture",
        candidates=(
            CandidateSpec("control", "No input", intervention={"type": "none"}),
            CandidateSpec(
                "candidate-a",
                "Fixture target",
                target="fixture-target",
                intervention={"type": "activation"},
                metadata={"mapping_id": "fixture-map-v1"},
            ),
        ),
        run_plan={
            "backend_requirements": {
                "dataset_id": "fixture-dataset-v1",
                "id_namespace": "fixture-root-id",
                "input_ids": [],
            },
        },
        metadata={
            "workflow_contract": "support-gated-1",
            "dataset_id": "fixture-dataset-v1",
            "id_namespace": "fixture-root-id",
            "context": {"assay": "synthetic-test-only"},
        },
    )


def _mapping() -> MappingRecord:
    return MappingRecord(
        mapping_id="fixture-map-v1",
        biological_target="fixture-target",
        backend="fixture",
        id_namespace="fixture-root-id",
        dataset_id="fixture-dataset-v1",
        intervention_type="activation",
        target_ids=("fixture-id-001",),
        sources=({"citation": "Synthetic test fixture", "locator": "not biological evidence"},),
        review_status="COMPUTATIONALLY_REVIEWED",
        context={"assay": "synthetic-test-only"},
        reviewer="synthetic-test-only",
        reviewed_at="2026-10-06T00:00:00Z",
    )


def _automation(tmp_path, *, command: str = "pass") -> tuple[WorkbenchService, WorkbenchV2Automation, StudySpec]:
    service = _service(tmp_path, command=command)
    service.register_mapping_record(_mapping())
    study = service.create_research_study(_study())
    runtime = WorkbenchV2Automation(service, output_root=tmp_path / "external" / "ai_v2" / "outputs" / "automation")
    return service, runtime, study


def test_v2_automation_workflow_requires_human_approval_and_emits_hashed_report(tmp_path):
    service, runtime, study = _automation(tmp_path)

    status = runtime.status(study.study_id)
    assert status["workflow_state"] == "HUMAN_APPROVAL_REQUIRED"
    assert "submit_screening" not in status["allowed_tools"]
    assert status["tool_policy"]["automatic_retries"] == 0
    with pytest.raises(ValueError, match="support_assessment_requires_researcher_approval"):
        runtime.submit(study.study_id, seeds=[101])

    approval = runtime.approve(study.study_id, reviewer="A03 synthetic reviewer")
    assert approval["status"] == "FROZEN_FOR_COMPUTATIONAL_RUN"
    submitted = runtime.submit(
        study.study_id,
        seeds=[101],
        base_config={"private-test-marker": "DO_NOT_WRITE_TO_AUDIT"},
    )
    assert submitted["submitted_job_count"] == 2
    result = runtime.run(study.study_id, timeout_s=10)
    assert result["status"] == "COMPLETED"
    assert result["completed_job_count"] == 2

    report = runtime.report(study.study_id)
    assert report["model_provider"] == "NOT_USED_FOR_WORKFLOW_EXECUTION_OR_METRIC_CALCULATION"
    assert report["retrieval_used_for_execution"] is False
    assert report["support_assessment_sha256"]
    assert report["human_approval_sha256"]
    assert len(report["results"]) == 2
    assert len(report["run_manifest_hashes"]) == 2
    assert report["report_sha256"]
    report_path = (
        tmp_path / "external/ai_v2/outputs/automation/reports"
        / study.study_id / f"{report['report_id']}.json"
    )
    assert report_path.is_file()
    saved_report = json.loads(report_path.read_text(encoding="utf-8"))
    saved_digest = saved_report.pop("report_sha256")
    assert stable_hash(saved_report) == saved_digest
    audit = runtime.verify_audit_chain()
    assert audit["status"] == "VALID"
    assert audit["event_count"] >= 8
    assert "DO_NOT_WRITE_TO_AUDIT" not in runtime.audit_path.read_text(encoding="utf-8")
    assert service.get_support_assessment(study.study_id)["run_allowed"] is True


def test_reassessment_invalidates_previous_human_approval_and_blocks_submission(tmp_path):
    _service_instance, runtime, study = _automation(tmp_path)
    runtime.approve(study.study_id, reviewer="A03 synthetic reviewer")
    runtime.assess(study.study_id)

    status = runtime.status(study.study_id)
    assert status["workflow_state"] == "HUMAN_APPROVAL_REQUIRED"
    assert status["human_approval"]["valid"] is False
    with pytest.raises(ValueError, match="support_assessment_requires_researcher_approval"):
        runtime.submit(study.study_id, seeds=[101])


def test_workflow_run_timeout_cancels_job_without_automatic_retry(tmp_path):
    service, runtime, study = _automation(tmp_path, command="import time; time.sleep(20)")
    runtime.approve(study.study_id, reviewer="A03 synthetic reviewer")
    submission = runtime.submit(study.study_id, seeds=[202], candidate_ids=["candidate-a"])

    result = runtime.run(study.study_id, timeout_s=0.1)

    assert result["status"] == "TIMED_OUT"
    assert result["automatic_retries"] == 0
    assert result["jobs"][0]["status"] in {"CANCELLED", "RUNNING"}
    if result["jobs"][0]["status"] == "CANCELLED":
        resumed = runtime.resume(study.study_id, job_ids=[submission["job_ids"][0]])
        assert resumed["jobs"][0]["status"] == "PENDING"
    events = [json.loads(line) for line in runtime.audit_path.read_text(encoding="utf-8").splitlines()]
    assert any(event["event_type"] == "JOB_TIMEOUT_REQUESTED" for event in events)
    assert runtime.verify_audit_chain()["status"] == "VALID"


def test_failed_run_is_reported_and_retried_only_after_explicit_resume(tmp_path):
    service, runtime, study = _automation(tmp_path, command="import sys; sys.exit(3)")
    runtime.approve(study.study_id, reviewer="A03 synthetic reviewer")
    submission = runtime.submit(study.study_id, seeds=[303], candidate_ids=["candidate-a"])

    first = runtime.run(study.study_id, timeout_s=10)
    assert first["status"] == "PARTIAL"
    assert first["jobs"][0]["status"] == "FAILED"
    assert first["automatic_retries"] == 0
    assert service.get_job(submission["job_ids"][0]).attempt == 1

    runtime.resume(study.study_id, job_ids=[submission["job_ids"][0]])
    second = runtime.run(study.study_id, timeout_s=10)
    assert second["status"] == "PARTIAL"
    assert service.get_job(submission["job_ids"][0]).attempt == 2


def test_v2_automation_api_is_opt_in_and_exposes_only_fixed_workflow_routes(tmp_path):
    pytest.importorskip("fastapi")
    from fastapi import HTTPException
    from fastapi.routing import APIRoute

    from drosophila_pd.workbench.api import create_app

    service, runtime, study = _automation(tmp_path)
    app = create_app(service, workflow_automation=runtime)
    paths = {route.path for route in app.routes if isinstance(route, APIRoute)}
    assert "/v2/workflows/{study_id}" in paths
    assert "/v2/workflows/{study_id}/approve" in paths
    assert "/v2/workflows/{study_id}/screening/run" in paths
    assert "/v2/workflows/{study_id}/report" in paths
    endpoint = next(route.endpoint for route in app.routes if getattr(route, "path", None) == "/v2/workflows/{study_id}")
    assert endpoint(study.study_id)["workflow_state"] == "HUMAN_APPROVAL_REQUIRED"

    disabled = create_app(service)
    disabled_endpoint = next(
        route.endpoint for route in disabled.routes
        if getattr(route, "path", None) == "/v2/workflows/{study_id}"
    )
    with pytest.raises(HTTPException) as blocked:
        disabled_endpoint(study.study_id)
    assert blocked.value.status_code == 503


def test_audit_chain_detects_edits(tmp_path):
    _service_instance, runtime, study = _automation(tmp_path)
    runtime.status(study.study_id)
    runtime._event("TEST_EVENT", study.study_id, {"fixture": True})
    lines = runtime.audit_path.read_text(encoding="utf-8").splitlines()
    event = json.loads(lines[0])
    event["details"]["fixture"] = "tampered"
    lines[0] = json.dumps(event)
    runtime.audit_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="checksum mismatch"):
        runtime.verify_audit_chain()
