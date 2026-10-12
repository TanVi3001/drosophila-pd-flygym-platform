from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Mapping

import pytest

from drosophila_pd.ai_v2.contracts import AIStudySpec
from drosophila_pd.ai_v2.mapping_resolution import (
    MappingRequest, bind_mapping_to_draft, resolve_mapping, select_mapping,
)
from drosophila_pd.ai_v2.workbench_workflow import AIV2WorkbenchWorkflow
from drosophila_pd.workbench.adapters import BackendRunContext, BackendRunResult
from drosophila_pd.workbench.assays import AssayEvaluation
from drosophila_pd.workbench.models import CandidateSpec, CapabilityDescriptor, StudySpec
from drosophila_pd.workbench.service import WorkbenchService
from drosophila_pd.workbench.store import WorkbenchStore
from drosophila_pd.workbench.support import MappingRecord


class FixtureBackend:
    name = "fixture"
    result_path = Path("result.json")

    def describe(self):
        return CapabilityDescriptor(
            self.name, "Fixture backend", True,
            supported_assays=("synthetic_demo",), supported_interventions=("none", "activation"),
        )

    def validate(self, study, config):
        return () if study.assay == "synthetic_demo" and config.get("candidate_id") else ("unsupported fixture request",)

    def run(self, context: BackendRunContext):
        context.artifact_dir.mkdir(parents=True, exist_ok=True)
        response = 1.5 if context.job.config.get("intervention_type") == "activation" else 1.0
        (context.artifact_dir / "result.json").write_text(
            json.dumps({"status": "SYNTHETIC_ONLY", "metrics": {"response": response}}), encoding="utf-8"
        )
        context.log_path.write_text("synthetic fixture only", encoding="utf-8")
        return BackendRunResult(("fixture",), sys.executable, Path(__file__).resolve().parents[1].as_posix(), 0)


class FixtureAssay:
    name = "synthetic_demo"

    def evaluate(self, result: Mapping[str, Any]):
        metrics = result.get("metrics", {})
        good = isinstance(metrics, Mapping) and isinstance(metrics.get("response"), (int, float))
        return AssayEvaluation(self.name, "SYNTHETIC_FIXTURE_PASS" if good else "FAIL", good, good, metrics)

    def compare(self, reference, condition, *, primary_metric):
        return {"status": "SYNTHETIC_ONLY", "primary_metric": primary_metric}


def _mapping():
    return MappingRecord(
        mapping_id="demo-map", version="r1", biological_target="synthetic target",
        backend="fixture", id_namespace="synthetic_id", dataset_id="synthetic_dataset",
        intervention_type="activation", target_ids=("ID_FROM_REGISTRY",),
        readout_ids=("SYNTHETIC_READOUT",),
        sources=({"citation": "synthetic fixture", "locator": "test only"},),
        review_status="COMPUTATIONALLY_REVIEWED", context={}, reviewer="fixture-reviewer",
        reviewed_at="2026-10-01T00:00:00Z", limitations=("Not biological evidence.",),
    )


def _draft():
    study = StudySpec(
        name="Synthetic workflow test", hypothesis="Fixture changes output",
        falsifiable_prediction="Scalar differs", assay="synthetic_demo", primary_metric="metrics.response",
        backend="fixture",
        candidates=(
            CandidateSpec("control", "Control", intervention={"type": "none"}),
            CandidateSpec("condition", "Condition", target="synthetic target", intervention={"type": "activation"}),
        ),
        run_plan={"backend_requirements": {"dataset_id": "synthetic_dataset", "id_namespace": "synthetic_id"}},
        metadata={"dataset_id": "synthetic_dataset", "id_namespace": "synthetic_id"},
    )
    return AIStudySpec(
        study, ("SYNTHETIC_CHUNK",),
        provenance={"provider_id": "fixture-not-llm", "prompt_version": "test-v1", "corpus_sha256": "a" * 64},
    )


def _service(tmp_path):
    return WorkbenchService(
        store=WorkbenchStore(tmp_path / "state.sqlite3"), artifact_root=tmp_path / "artifacts",
        adapters={"fixture": FixtureBackend()}, assays={"synthetic_demo": FixtureAssay()},
    )


def test_mapping_approval_execution_report_and_provenance_are_separate_gates(tmp_path):
    service = _service(tmp_path)
    workflow = AIV2WorkbenchWorkflow(service)
    mapping = _mapping()
    service.register_mapping_record(mapping)
    request = MappingRequest("synthetic target", "fixture", "synthetic_dataset", "synthetic_id", "activation")
    resolution = resolve_mapping(request, [mapping])
    option = resolution.options[0]
    binding = select_mapping(
        resolution, [mapping], mapping_id=option.mapping_id,
        version=option.version, record_hash=option.record_hash,
    )
    draft = bind_mapping_to_draft(_draft(), candidate_id="condition", binding=binding)
    created = workflow.create_draft(draft)
    study_id = created["study"]["study_id"]

    assert created["support_assessment"]["status"] == "READY_FOR_COMPUTATIONAL_REVIEW"
    assert created["workflow_status"]["stage"] == "AWAITING_HUMAN_APPROVAL"
    with pytest.raises(ValueError, match="requires_researcher_approval"):
        workflow.submit(study_id, candidate_id="condition")

    approval = workflow.approve(study_id, reviewer="human operator fixture")
    assert approval["status"] == "FROZEN_FOR_COMPUTATIONAL_RUN"
    submitted = workflow.submit(study_id, candidate_id="condition")
    assert submitted["job"]["config"]["mapping_version"] == mapping.version
    assert submitted["job"]["config"]["mapping_record_hash"] == mapping.record_hash
    assert submitted["job"]["config"]["readout_ids"] == list(mapping.readout_ids)
    finished = workflow.run(submitted["job"]["job_id"])
    assert finished["job"]["status"] == "COMPLETED"
    assert finished["workflow_status"]["stage"] == "RUNS_COMPLETED"

    manifest_path = Path(finished["job"]["manifest_path"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    job_config = manifest["provenance"]["job_configuration"]
    assert job_config["mapping_version"] == mapping.version
    assert job_config["mapping_record_hash"] == mapping.record_hash
    assert job_config["readout_ids"] == list(mapping.readout_ids)
    assert job_config["ai_v2_provenance"]["provider_id"] == "fixture-not-llm"
    assert job_config["ai_v2_provenance"]["evidence_ids"] == ["SYNTHETIC_CHUNK"]
    report = service.get_report(study_id)
    condition_row = next(row for row in report["results"] if row["candidate_id"] == "condition")
    assert condition_row["qc"]["status"] == "SYNTHETIC_FIXTURE_PASS"
    assert condition_row["metrics"]["metrics"]["response"] == 1.5


def test_pending_mapping_and_unsupported_capability_cannot_be_approved_or_run(tmp_path):
    service = _service(tmp_path)
    workflow = AIV2WorkbenchWorkflow(service)
    mapping = _mapping()
    pending = MappingRecord(**{
        **mapping.__dict__, "review_status": "PENDING_SCIENTIFIC_REVIEW",
        "reviewer": None, "reviewed_at": None,
    })
    service.register_mapping_record(pending)
    mapping_request = MappingRequest(
        "synthetic target", "fixture", "synthetic_dataset", "synthetic_id", "activation"
    )
    assert resolve_mapping(mapping_request, [pending]).status == "REVIEW_REQUIRED"
    assessment = workflow.create_draft(_draft())["support_assessment"]
    assert assessment["status"] == "MAPPING_REQUIRED"
    with pytest.raises(ValueError, match="not_run_allowed"):
        workflow.approve(assessment["study_id"], reviewer="reviewer")

