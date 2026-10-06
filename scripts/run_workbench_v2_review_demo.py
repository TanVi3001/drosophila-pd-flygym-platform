"""Run the A07 handoff with synthetic evidence, a fake LLM and a fixture backend.

All artifacts are stored in a new repository-external run directory. Numbers
are fixture values chosen to exercise QC/reporting, never neuroscience results.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import uuid

from drosophila_pd.workbench.evidence import CORPUS_SCHEMA, ApprovedEvidenceCorpus, OfflineEvidenceRetriever
from drosophila_pd.workbench.models import CapabilityDescriptor
from drosophila_pd.workbench.adapters import CommandBackendAdapter
from drosophila_pd.workbench.service import WorkbenchService
from drosophila_pd.workbench.store import WorkbenchStore
from drosophila_pd.workbench.support import MappingRecord
from drosophila_pd.workbench.v2_automation import WorkbenchV2Automation
from drosophila_pd.workbench.v2_runtime import RuntimeLayout, WorkbenchV2DraftRuntime


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_ID = "a07-fixture-methods-001"


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class FixtureGenerator:
    provider_id = "synthetic-a07-fake-generator"

    def generate_json(self, *, system_prompt, user_payload):
        return {
            "title": "Synthetic A07 study",
            "hypothesis": "A declared fixture input changes a fixture readout.",
            "falsifiable_prediction": "The fixture readout differs from its control.",
            "assay": "sensory_mn9", "primary_metric": "mn9_rate", "primary_metric_unit": "Hz",
            "field_citations": {field: [EVIDENCE_ID] for field in (
                "hypothesis", "falsifiable_prediction", "assay", "primary_metric", "primary_metric_unit",
            )},
            "uncertainties": ["Handcrafted fixture only; no scientific quality evaluation."],
        }


def make_fixture_service(runtime_root: Path, *, fail_backend: bool = False):
    layout = RuntimeLayout.from_root(runtime_root, repository_root=REPOSITORY_ROOT)
    layout.prepare()
    text = "Synthetic methods fixture: sensory assay MN9 firing rate in hertz."
    timestamp = "2026-10-06T00:00:00Z"
    corpus_doc = {
        "schema_version": CORPUS_SCHEMA, "corpus_id": "a07-fixture-corpus", "corpus_version": "1",
        "sources": [{
            "source_id": "a07-fixture-source", "citation": "Synthetic fixture, not a scientific paper",
            "source_uri": "https://example.org/a07-fixture", "dataset_version": "synthetic-only",
            "evidence_tier": "METHODS", "source_sha256": _sha("synthetic-source"),
            "review_status": "APPROVED", "reviewer": "synthetic-only", "reviewed_at": timestamp,
            "approval_record_id": "a07-fixture-approval", "blind_use": "ELIGIBLE",
            "chunks": [{
                "chunk_id": EVIDENCE_ID, "locator": "Synthetic fixture paragraph",
                "evidence_scope": "methods", "text": text, "text_sha256": _sha(text),
                "access_class": "PUBLIC_UNLABELED", "blind_review_status": "PASS",
                "blind_reviewer": "synthetic-only", "blind_reviewed_at": timestamp,
            }],
        }],
    }
    corpus_file = layout.v2_corpus / "corpus.json"
    with corpus_file.open("x", encoding="utf-8") as stream:
        json.dump(corpus_doc, stream, ensure_ascii=False, sort_keys=True)
    corpus = ApprovedEvidenceCorpus.load(
        corpus_file, expected_sha256=hashlib.sha256(corpus_file.read_bytes()).hexdigest(),
        corpus_root=layout.v2_corpus,
    )
    retriever = OfflineEvidenceRetriever(
        corpus, audit_path=layout.v2_outputs / "retrieval_audit.jsonl", output_root=layout.v2_outputs,
    )
    def command(_study, config, artifact):
        if fail_backend:
            return (sys.executable, "-c", "import sys; sys.exit(3)")
        value = 0.0 if config["candidate_id"] == "control" else 1.0
        payload = {"status": "PASS", "metrics": {"mn9_rate": value},
                   "scientific_scope": "SYNTHETIC_FIXTURE_ONLY"}
        return (
            sys.executable, "-c",
            "import pathlib,sys; pathlib.Path(sys.argv[1]).write_text(sys.argv[2], encoding='utf-8')",
            str(artifact / "fixture_metrics.json"), json.dumps(payload),
        )
    adapter = CommandBackendAdapter(
        name="fixture", descriptor=CapabilityDescriptor(
            name="fixture", display_name="Synthetic fixture backend", ready=True,
            supported_assays=("sensory_mn9",), supported_interventions=("none", "activation"),
        ), repo_root=REPOSITORY_ROOT, interpreter=sys.executable,
        command_factory=command, script_path=Path(__file__).resolve(), result_path="fixture_metrics.json",
    )
    service = WorkbenchService(
        store=WorkbenchStore(layout.v1_database), artifact_root=layout.v1_artifacts,
        adapters={"fixture": adapter},
        v2_draft_runtime=WorkbenchV2DraftRuntime(
            provider=None, output_root=layout.v2_outputs / "drafts", evidence_retriever=retriever,
            study_spec_generator=FixtureGenerator(), supported_assays={"sensory_mn9"},
        ),
    )
    service.register_mapping_record(MappingRecord(
        mapping_id="a07-fixture-map", biological_target="synthetic-target", backend="fixture",
        id_namespace="fixture-id", dataset_id="fixture-dataset", intervention_type="activation",
        target_ids=("fixture-001",), sources=({"citation": "Synthetic mapping fixture"},),
        review_status="COMPUTATIONALLY_REVIEWED", reviewer="synthetic-only", reviewed_at=timestamp,
        context={"assay": "synthetic-only"},
    ))
    automation = WorkbenchV2Automation(service, output_root=layout.v2_outputs / "automation")
    return service, automation


def reviewed_fixture_study(study_id="a07-fixture-study"):
    return {
        "study_id": study_id, "name": "Synthetic A07 study",
        "hypothesis": "Human-reviewed synthetic input changes the fixture readout.",
        "falsifiable_prediction": "The fixture readout differs from its control.",
        "assay": "sensory_mn9", "primary_metric": "mn9_rate", "backend": "fixture",
        "candidates": [
            {"candidate_id": "control", "label": "Synthetic control", "intervention": {"type": "none"}},
            {"candidate_id": "condition", "label": "Synthetic condition", "target": "synthetic-target",
             "intervention": {"type": "activation"}, "metadata": {"mapping_id": "a07-fixture-map"}},
        ],
        "controls": [{"candidate_id": "control", "description": "No fixture input"}],
        "run_plan": {"seed_repetitions": 1, "backend_requirements": {
            "dataset_id": "fixture-dataset", "id_namespace": "fixture-id", "input_ids": [],
            "duration_s": 1, "trials": 1, "readout_ids": ["fixture-readout"],
        }},
        "metadata": {"primary_metric_unit": "Hz", "context": {"assay": "synthetic-only"},
                     "dataset_id": "fixture-dataset", "id_namespace": "fixture-id"},
    }


def run_demo(runtime_root: Path):
    service, workflow = make_fixture_service(runtime_root)
    draft = service.draft_v2_study_spec("How is MN9 firing rate measured in the sensory assay?")
    snapshot = service.get_v2_study_draft(draft["draft_id"])
    promotion = service.promote_v2_study_draft(
        draft["draft_id"], expected_draft_sha256=snapshot["draft_sha256"],
        reviewer="synthetic-demo-attestation", review_decision="APPROVED",
        evaluation_split="synthetic_fixture", study_payload=reviewed_fixture_study(),
    )
    study_id = promotion["study"]["study_id"]
    pre_approval_state = workflow.status(study_id)["workflow_state"]
    workflow.approve(study_id, reviewer="synthetic-demo-run-approval")
    workflow.submit(study_id, seeds=[101])
    run = workflow.run(study_id, timeout_s=30)
    report = workflow.report(study_id)
    qc_pass_count = sum(bool(row["qc"] and row["qc"].get("qc_pass")) for row in report["results"])
    passed = (run["status"] == "COMPLETED" and qc_pass_count == run["job_count"]
              and report["audit_chain"]["status"] == "VALID")
    summary = {
        "status": "PASS_SYNTHETIC_DEMO" if passed else "FAILED",
        "evaluation_split": "synthetic_fixture", "live_model_called": False,
        "biological_validation": "NOT_PERFORMED", "heldout_status": "LOCKED_NOT_RUN",
        "draft_id": draft["draft_id"], "draft_sha256": snapshot["draft_sha256"],
        "promotion_status": promotion["status"], "pre_approval_state": pre_approval_state,
        "job_count": run["job_count"], "completed_job_count": run["completed_job_count"],
        "qc_pass_count": qc_pass_count,
        "audit_chain_status": report["audit_chain"]["status"],
        "report_sha256": report["report_sha256"], "report_path": report["artifact_path"],
    }
    with (runtime_root / "demo_summary.json").open("x", encoding="utf-8") as stream:
        json.dump(summary, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", required=True, type=Path)
    args = parser.parse_args()
    root = RuntimeLayout.from_root(args.runtime_root, repository_root=REPOSITORY_ROOT).root
    run_root = root / f"a07-demo-{uuid.uuid4().hex}"
    summary = run_demo(run_root)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["status"] == "PASS_SYNTHETIC_DEMO" else 1


if __name__ == "__main__":
    raise SystemExit(main())
