from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

from drosophila_pd.workbench.models import stable_hash
from drosophila_pd.workbench.support import MappingRecord


_SPEC = importlib.util.spec_from_file_location(
    "a07_demo", Path(__file__).resolve().parents[1] / "scripts/run_workbench_v2_review_demo.py",
)
demo = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(demo)


@pytest.fixture
def handoff(tmp_path):
    service, workflow = demo.make_fixture_service(tmp_path / "external")
    draft = service.draft_v2_study_spec("MN9 sensory assay firing rate")
    snapshot = service.get_v2_study_draft(draft["draft_id"])
    request = {
        "expected_draft_sha256": snapshot["draft_sha256"],
        "reviewer": "synthetic-test-reviewer", "review_decision": "APPROVED",
        "evaluation_split": "synthetic_fixture", "study_payload": demo.reviewed_fixture_study(),
    }
    return service, workflow, draft, request


def test_complete_synthetic_demo_reports_qc_lineage_and_no_live_model(tmp_path):
    summary = demo.run_demo(tmp_path / "demo")
    assert summary["status"] == "PASS_SYNTHETIC_DEMO"
    assert summary["completed_job_count"] == summary["job_count"] == summary["qc_pass_count"] == 2
    assert summary["pre_approval_state"] == "HUMAN_APPROVAL_REQUIRED"
    assert summary["audit_chain_status"] == "VALID"
    assert summary["live_model_called"] is False
    assert summary["heldout_status"] == "LOCKED_NOT_RUN"
    report = json.loads(Path(summary["report_path"]).read_text(encoding="utf-8"))
    assert report["ai_draft_lineage"]["draft_id"] == summary["draft_id"]
    assert report["ai_draft_lineage"]["draft_sha256"] == summary["draft_sha256"]
    assert report["ai_draft_lineage"]["run_approval_granted"] is False
    assert report["prompt_template_sha256"]
    assert report["evidence_corpus_sha256"]
    digest = report.pop("report_sha256")
    assert stable_hash(report) == digest == summary["report_sha256"]


def test_promotion_preserves_draft_and_mappings_and_requires_separate_run_approval(handoff):
    service, workflow, draft, request = handoff
    mapping_before = copy.deepcopy(service.list_mapping_records())
    result = service.promote_v2_study_draft(draft["draft_id"], **request)
    study_id = result["study"]["study_id"]
    assert result["status"] == "PROMOTED_REQUIRES_RUN_APPROVAL"
    assert result["job_created"] is False and result["simulation_started"] is False
    assert not service.list_jobs(study_id=study_id)
    assert service.store.get_support_approval(study_id) is None
    assert service.list_mapping_records() == mapping_before
    assert service.get_v2_study_draft(draft["draft_id"])["draft_sha256"] == request["expected_draft_sha256"]
    assert "hypothesis" in result["promotion"]["edited_or_completed_fields"]
    assert result["promotion"]["selected_mapping_hashes"] == {
        "a07-fixture-map": mapping_before["a07-fixture-map"]["record_hash"],
    }
    with pytest.raises(ValueError, match="requires_researcher_approval"):
        workflow.submit(study_id, seeds=[101])
    assert not service.list_jobs(study_id=study_id)


@pytest.mark.parametrize(("field", "value", "message"), [
    ("reviewer", "", "reviewer is required"),
    ("review_decision", "REJECTED", "review_decision"),
    ("expected_draft_sha256", "0" * 64, "checksum changed"),
    ("evaluation_split", "heldout", "held-out is locked"),
])
def test_unreviewed_or_out_of_scope_request_creates_no_study(handoff, field, value, message):
    service, _workflow, draft, request = handoff
    request[field] = value
    with pytest.raises(ValueError, match=message):
        service.promote_v2_study_draft(draft["draft_id"], **request)
    assert not service.list_studies()


@pytest.mark.parametrize("problem", ["control", "unit", "unit_mismatch", "plan", "mapping", "assay", "intervention", "reserved"])
def test_incomplete_or_incompatible_human_design_cannot_be_promoted(handoff, problem):
    service, _workflow, draft, request = handoff
    study = request["study_payload"]
    if problem == "control":
        study["controls"] = []
    elif problem == "unit":
        study["metadata"].pop("primary_metric_unit")
    elif problem == "unit_mismatch":
        study["metadata"]["primary_metric_unit"] = "ms"
    elif problem == "plan":
        study["run_plan"] = {}
    elif problem == "mapping":
        study["candidates"][1]["metadata"]["mapping_id"] = "unknown-map"
    elif problem == "assay":
        study["assay"] = "unsupported_assay"
    elif problem == "intervention":
        study["candidates"][1]["intervention"] = {}
    else:
        study["metadata"]["ai_draft_lineage"] = {"reviewer": "forged"}
    with pytest.raises(ValueError):
        service.promote_v2_study_draft(draft["draft_id"], **request)
    assert not service.list_studies()


def test_pending_mapping_is_rejected_without_creating_a_study(handoff):
    service, _workflow, draft, request = handoff
    raw = service.list_mapping_records()["a07-fixture-map"]
    raw.pop("record_hash")
    raw.update(mapping_id="pending-fixture-map", review_status="PENDING_SCIENTIFIC_REVIEW")
    service.register_mapping_record(MappingRecord.from_dict(raw))
    request["study_payload"]["candidates"][1]["metadata"]["mapping_id"] = "pending-fixture-map"
    with pytest.raises(ValueError, match="mapping_review_required"):
        service.promote_v2_study_draft(draft["draft_id"], **request)
    assert not service.list_studies()


def test_backend_preflight_blocks_conflicting_target_ids(handoff):
    service, workflow, draft, request = handoff
    request["study_payload"]["candidates"][1]["intervention"]["input_ids"] = ["unreviewed-id"]
    result = service.promote_v2_study_draft(draft["draft_id"], **request)
    assert result["status"] == "PROMOTED_BLOCKED_BY_SUPPORT_GATE"
    assert result["support_assessment"]["run_allowed"] is False
    with pytest.raises(ValueError, match="not_run_allowed"):
        workflow.approve(result["study"]["study_id"], reviewer="synthetic-test-reviewer")
    assert not service.list_jobs(study_id=result["study"]["study_id"])


def test_no_evidence_draft_has_no_promotion_path(handoff):
    service, _workflow, _draft, request = handoff
    draft = service.draft_v2_study_spec("olfactory mushroom body memory")
    request["expected_draft_sha256"] = service.get_v2_study_draft(draft["draft_id"])["draft_sha256"]
    with pytest.raises(ValueError, match="evidence-backed"):
        service.promote_v2_study_draft(draft["draft_id"], **request)
    assert not service.list_studies()


def test_changed_artifact_or_corpus_cannot_reuse_review(handoff):
    service, _workflow, draft, request = handoff
    path = Path(draft["artifact_path"])
    edited = json.loads(path.read_text(encoding="utf-8"))
    edited["corpus_sha256"] = "0" * 64
    path.write_text(json.dumps(edited), encoding="utf-8")
    with pytest.raises(ValueError, match="checksum changed"):
        service.promote_v2_study_draft(draft["draft_id"], **request)
    request["expected_draft_sha256"] = service.get_v2_study_draft(draft["draft_id"])["draft_sha256"]
    with pytest.raises(ValueError, match="corpus does not match"):
        service.promote_v2_study_draft(draft["draft_id"], **request)
    with pytest.raises(ValueError, match="invalid V2 study draft ID"):
        service.get_v2_study_draft("../outside")


def test_revised_study_requires_new_identity_and_new_run_approval(handoff):
    service, workflow, draft, request = handoff
    first = service.promote_v2_study_draft(draft["draft_id"], **request)
    first_id = first["study"]["study_id"]
    workflow.approve(first_id, reviewer="synthetic-first-run-approver")
    request["study_payload"]["hypothesis"] = "Revised synthetic hypothesis."
    with pytest.raises(ValueError, match="already exists"):
        service.promote_v2_study_draft(draft["draft_id"], **request)
    request["study_payload"]["study_id"] = "a07-fixture-revision-2"
    second = service.promote_v2_study_draft(draft["draft_id"], **request)
    assert first["study"]["configuration_hash"] != second["study"]["configuration_hash"]
    assert workflow.status(second["study"]["study_id"])["workflow_state"] == "HUMAN_APPROVAL_REQUIRED"


def test_two_promoted_studies_can_submit_same_candidate_names_and_seeds(handoff):
    service, workflow, draft, request = handoff
    first = service.promote_v2_study_draft(draft["draft_id"], **request)
    first_id = first["study"]["study_id"]
    workflow.approve(first_id, reviewer="synthetic-run-reviewer")
    first_jobs = workflow.submit(first_id, seeds=[101])
    request["study_payload"]["study_id"] = "a07-second-study"
    second = service.promote_v2_study_draft(draft["draft_id"], **request)
    second_id = second["study"]["study_id"]
    workflow.approve(second_id, reviewer="synthetic-run-reviewer")
    second_jobs = workflow.submit(second_id, seeds=[101])
    assert first_jobs["submitted_job_count"] == second_jobs["submitted_job_count"] == 2
    assert set(first_jobs["job_ids"]).isdisjoint(second_jobs["job_ids"])
    repeated = workflow.submit(second_id, seeds=[101])
    assert repeated["job_ids"] == second_jobs["job_ids"]


def test_frozen_run_parameters_cannot_be_overridden(handoff):
    service, workflow, draft, request = handoff
    result = service.promote_v2_study_draft(draft["draft_id"], **request)
    study_id = result["study"]["study_id"]
    workflow.approve(study_id, reviewer="synthetic-run-reviewer")
    blocked = workflow.submit(study_id, seeds=[101], base_config={"duration_s": 9})
    assert blocked["submitted_job_count"] == 0
    assert blocked["errors"] and all("differs from the frozen StudySpec" in row["reason"] for row in blocked["errors"])
    assert not service.list_jobs(study_id=study_id)


def test_existing_legacy_screening_jobs_are_reused_within_the_same_study(handoff):
    service, workflow, draft, request = handoff
    result = service.promote_v2_study_draft(draft["draft_id"], **request)
    study_id = result["study"]["study_id"]
    workflow.approve(study_id, reviewer="synthetic-run-reviewer")
    legacy = service.submit_job(
        study_id, {"candidate_id": "condition", "seed": 101, "phase": "screening"},
        job_id="confirmation-screening-condition-seed-101",
    )
    submitted = workflow.submit(study_id, seeds=[101], candidate_ids=["condition"])
    assert submitted["submitted_job_count"] == 1
    assert submitted["job_ids"] == [legacy.job_id]
    assert len(service.list_jobs(study_id=study_id)) == 1


def test_promoted_study_preserves_failure_qc_and_lineage(tmp_path):
    service, workflow = demo.make_fixture_service(tmp_path / "failure-demo", fail_backend=True)
    draft = service.draft_v2_study_spec("MN9 sensory firing rate")
    snapshot = service.get_v2_study_draft(draft["draft_id"])
    result = service.promote_v2_study_draft(
        draft["draft_id"], expected_draft_sha256=snapshot["draft_sha256"], reviewer="synthetic-reviewer",
        review_decision="APPROVED", evaluation_split="synthetic_fixture",
        study_payload=demo.reviewed_fixture_study(),
    )
    study_id = result["study"]["study_id"]
    workflow.approve(study_id, reviewer="synthetic-run-reviewer")
    workflow.submit(study_id, seeds=[101])
    run = workflow.run(study_id, timeout_s=30)
    assert run["status"] == "PARTIAL"
    assert run["completed_job_count"] == 0
    assert run["automatic_retries"] == 0
    report = workflow.report(study_id)
    assert all(row["status"] == "FAILED" and not row["qc"]["qc_pass"] for row in report["results"])
    assert report["ai_draft_lineage"]["draft_id"] == draft["draft_id"]
    assert report["audit_chain"]["status"] == "VALID"


def test_promotion_api_contract_and_disabled_runtime(handoff, tmp_path):
    pytest.importorskip("fastapi")
    from fastapi import HTTPException
    from drosophila_pd.workbench.api import create_app
    from drosophila_pd.workbench.service import WorkbenchService
    from drosophila_pd.workbench.store import WorkbenchStore

    service, workflow, draft, request = handoff
    app = create_app(service, workflow_automation=workflow)
    def endpoint(app, path):
        return next(route.endpoint for route in app.routes if getattr(route, "path", None) == path)
    getter = endpoint(app, "/v2/study-spec/drafts/{draft_id}")
    promoter = endpoint(app, "/v2/study-spec/drafts/{draft_id}/promote")
    assert getter(draft["draft_id"])["draft_sha256"] == request["expected_draft_sha256"]
    payload = dict(request)
    payload["study"] = payload.pop("study_payload")
    assert promoter(draft["draft_id"], payload)["status"] == "PROMOTED_REQUIRES_RUN_APPROVAL"
    with pytest.raises(HTTPException) as invalid:
        promoter(draft["draft_id"], {"reviewer": "only-one-field"})
    assert invalid.value.status_code == 400
    disabled = WorkbenchService(store=WorkbenchStore(tmp_path / "disabled.sqlite3"), artifact_root=tmp_path / "disabled")
    with pytest.raises(HTTPException) as unavailable:
        endpoint(create_app(disabled), "/v2/study-spec/drafts/{draft_id}")(draft["draft_id"])
    assert unavailable.value.status_code == 503
