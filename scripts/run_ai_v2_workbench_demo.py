"""Run a visibly synthetic end-to-end Workbench workflow demonstration.

This is not an LLM evaluation, a Drosophila model run, or biological evidence.
It demonstrates evidence allowlisting, draft creation, exact mapping binding,
human approval, gated job submission, QC/report generation, and fail-closed
branches using synthetic fixtures only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from drosophila_pd.ai_v2.contracts import AIStudySpec, EvidenceItem
from drosophila_pd.ai_v2.mapping_resolution import (
    MappingRequest,
    bind_mapping_to_draft,
    resolve_mapping,
    select_mapping,
)
from drosophila_pd.ai_v2.rag import RAGRuntimeContract
from drosophila_pd.ai_v2.workbench_workflow import AIV2WorkbenchWorkflow
from drosophila_pd.workbench.adapters import BackendRunContext, BackendRunResult
from drosophila_pd.workbench.assays import AssayEvaluation
from drosophila_pd.workbench.models import CandidateSpec, CapabilityDescriptor, StudySpec, stable_hash
from drosophila_pd.workbench.service import WorkbenchService
from drosophila_pd.workbench.store import WorkbenchStore
from drosophila_pd.workbench.support import MappingRecord
from drosophila_pd.workbench.intake import create_intake_draft


class SyntheticBackend:
    name = "synthetic_demo"
    result_path = Path("result.json")

    def describe(self) -> CapabilityDescriptor:
        return CapabilityDescriptor(
            name=self.name,
            display_name="Synthetic test backend (not a biological simulator)",
            ready=True,
            supported_assays=("synthetic_demo",),
            supported_interventions=("none", "activation"),
        )

    def validate(self, study: StudySpec, config: Mapping[str, object]) -> tuple[str, ...]:
        if study.backend != self.name or study.assay != "synthetic_demo":
            return ("synthetic backend accepts only synthetic_demo studies",)
        if not config.get("candidate_id"):
            return ("candidate_id is required",)
        return ()

    def run(self, context: BackendRunContext) -> BackendRunResult:
        context.artifact_dir.mkdir(parents=True, exist_ok=True)
        candidate_id = str(context.job.config["candidate_id"])
        value = 1.5 if context.job.config.get("intervention_type") == "activation" else 1.0
        payload = {
            "status": "SYNTHETIC_FIXTURE_ONLY",
            "metrics": {"response": value},
            "candidate_id": candidate_id,
            "scientific_scope": "Generated synthetic value; not Drosophila data.",
        }
        (context.artifact_dir / "result.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        context.log_path.parent.mkdir(parents=True, exist_ok=True)
        context.log_path.write_text("SYNTHETIC DEMO BACKEND; no biological simulator called.\n", encoding="utf-8")
        return BackendRunResult(
            command=("synthetic-demo-backend", candidate_id),
            interpreter=sys.executable,
            repo_root=ROOT.as_posix(),
            exit_code=0,
        )


class SyntheticAssay:
    name = "synthetic_demo"

    def evaluate(self, result: Mapping[str, Any]) -> AssayEvaluation:
        metrics = result.get("metrics", {})
        valid = isinstance(metrics, Mapping) and isinstance(metrics.get("response"), (int, float))
        return AssayEvaluation(
            assay=self.name,
            status="SYNTHETIC_FIXTURE_PASS" if valid else "SYNTHETIC_FIXTURE_FAIL",
            readout_available=valid,
            qc_pass=valid,
            metrics=dict(metrics) if isinstance(metrics, Mapping) else {},
            warnings=() if valid else ("synthetic response value missing",),
        )

    def compare(self, reference: Mapping[str, Any], condition: Mapping[str, Any], *, primary_metric: str) -> Mapping[str, Any]:
        left = reference.get("metrics", {}).get("response")
        right = condition.get("metrics", {}).get("response")
        if not isinstance(left, (int, float)) or not isinstance(right, (int, float)):
            return {"status": "NOT_ELIGIBLE", "reason": "synthetic metric missing"}
        return {
            "status": "SYNTHETIC_FIXTURE_ONLY",
            "primary_metric": primary_metric,
            "reference": left,
            "condition": right,
            "absolute_delta": right - left,
        }


class SyntheticIntakeProvider:
    """Deterministic fixture; it does not call or emulate a hosted LLM."""

    provider_id = "synthetic-fixture-not-an-llm"

    def extract(self, _protocol_text: str, *, source_uri: str | None = None) -> Mapping[str, Any]:
        return {
            "name": "SYNTHETIC DEMO ONLY — no biological interpretation",
            "hypothesis": "A synthetic condition changes a generated scalar",
            "falsifiable_prediction": "The generated scalar differs between fixture arms",
            "assay": "synthetic_demo",
            "primary_metric": "metrics.response",
            "candidate_suggestions": [{
                "label": "Synthetic condition",
                "target": "synthetic target",
                "rationale": "Fixed demonstration content; not evidence about a fly.",
                "sources": [{"citation": "SYNTHETIC FIXTURE", "locator": "demo-only"}],
            }],
            "control_suggestions": [{
                "label": "Synthetic control", "role": "negative_control",
                "rationale": "Fixed fixture control.",
            }],
            "citations": [{"citation": "SYNTHETIC FIXTURE", "locator": "demo-only"}],
            "missing_fields": [],
            "source_uri": source_uri,
        }


def _record() -> MappingRecord:
    return MappingRecord(
        mapping_id="SYNTHETIC_MAPPING_V1",
        version="1",
        biological_target="synthetic target",
        backend="synthetic_demo",
        id_namespace="synthetic_id",
        dataset_id="synthetic_dataset",
        intervention_type="activation",
        target_ids=("SYNTHETIC_INPUT_001",),
        readout_ids=("SYNTHETIC_READOUT_001",),
        sources=({"citation": "SYNTHETIC FIXTURE — not a paper", "locator": "demo-only"},),
        review_status="COMPUTATIONALLY_REVIEWED",
        context={},
        reviewer="synthetic-fixture-only",
        reviewed_at="2000-01-01T00:00:00Z",
        limitations=("Synthetic mapping fixture; does not map a real neuron or experiment.",),
    )


def _study(*, mapping: MappingRecord | None, assay: str = "synthetic_demo") -> StudySpec:
    metadata = {"dataset_id": "synthetic_dataset", "id_namespace": "synthetic_id"}
    candidates = [CandidateSpec("control", "Synthetic control", intervention={"type": "none"})]
    if mapping is not None:
        candidates.append(CandidateSpec(
            "condition", "Synthetic condition", target=mapping.biological_target,
            intervention={"type": "activation"},
            metadata={
                "mapping_id": mapping.mapping_id,
                "mapping_version": mapping.version,
                "mapping_record_hash": mapping.record_hash,
            },
            sources=mapping.sources,
        ))
    else:
        candidates.append(CandidateSpec(
            "condition", "Synthetic condition", target="synthetic target",
            intervention={"type": "activation"},
        ))
    return StudySpec(
        name="SYNTHETIC DEMO ONLY — no biological interpretation",
        hypothesis="Synthetic condition changes a generated scalar",
        falsifiable_prediction="The generated scalar differs between fixture arms",
        assay=assay,
        primary_metric="metrics.response",
        backend="synthetic_demo",
        candidates=tuple(candidates),
        controls=({"id": "control", "role": "synthetic fixture control"},),
        sources=({"citation": "SYNTHETIC FIXTURE", "locator": "demo-only"},),
        run_plan={"backend_requirements": {
            "dataset_id": "synthetic_dataset", "id_namespace": "synthetic_id",
            **({"readout_ids": list(mapping.readout_ids)} if mapping is not None else {}),
        }},
        metadata=metadata,
    )


def _draft_from_synthetic_intake(question: str, evidence: EvidenceItem, corpus_digest: str) -> AIStudySpec:
    intake = create_intake_draft(
        question,
        SyntheticIntakeProvider(),
        source_uri="synthetic://fixture/protocol",
        prompt_version="synthetic-demo-intake-v1",
    )
    proposed = intake["proposed_fields"]
    candidate_suggestion = proposed["candidate_suggestions"][0]
    control_suggestion = proposed["control_suggestions"][0]
    study = StudySpec(
        name=proposed["name"],
        hypothesis=proposed["hypothesis"],
        falsifiable_prediction=proposed["falsifiable_prediction"],
        assay=proposed["assay"],
        primary_metric=proposed["primary_metric"],
        backend="synthetic_demo",
        candidates=(
            CandidateSpec(
                "control", control_suggestion["label"],
                intervention={"type": "none"},
            ),
            # Intervention semantics are added by the explicit demo harness,
            # not inferred from provider output.
            CandidateSpec(
                "condition", candidate_suggestion["label"],
                target=candidate_suggestion["target"],
                intervention={"type": "activation"},
                sources=tuple(candidate_suggestion.get("sources", ())),
            ),
        ),
        controls=({"id": "control", "role": control_suggestion.get("role", "control")},),
        sources=tuple(proposed.get("citations", ())),
        run_plan={"backend_requirements": {
            "dataset_id": "synthetic_dataset", "id_namespace": "synthetic_id",
        }},
        metadata={"dataset_id": "synthetic_dataset", "id_namespace": "synthetic_id"},
    )
    return AIStudySpec(
        study,
        evidence_ids=(evidence.chunk_id,),
        approval_status="DRAFT",
        provenance={
            "provider_id": intake["provider_id"],
            "model_id": "none",
            "prompt_version": intake["prompt_version"],
            "corpus_sha256": corpus_digest,
            "generator_output_sha256": stable_hash(intake),
        },
    )


def run_demo(output_dir: Path) -> dict[str, Any]:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("output directory must be empty; refusing to overwrite demo artifacts")
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_root = output_dir / "workbench_artifacts"
    service = WorkbenchService(
        store=WorkbenchStore(output_dir / "demo_state.sqlite3"),
        artifact_root=artifact_root,
        adapters={"synthetic_demo": SyntheticBackend()},
        assays={"synthetic_demo": SyntheticAssay()},
    )
    workflow = AIV2WorkbenchWorkflow(service)

    corpus_digest = hashlib.sha256(b"synthetic-demo-corpus-v1").hexdigest()
    evidence = EvidenceItem(
        source_id="SYNTHETIC_SOURCE", citation="SYNTHETIC FIXTURE", chunk_id="SYNTHETIC_CHUNK_1",
        retrieval_score=1.0, provenance="in-script fixture", access_class="DEVELOPMENT_INPUT",
    )
    rag = RAGRuntimeContract(
        corpus_sha256=corpus_digest,
        approved_source_ids=frozenset({"SYNTHETIC_SOURCE"}),
        denied_source_ids=frozenset(),
        retrieval_log_path=output_dir / "retrieval.jsonl",
    )
    retrieval = [evidence]
    for item in retrieval:
        rag.validate_result(item)
    # Explicit negative path: an empty retrieval result never becomes a draft.
    no_evidence = _evidence_gate(())
    evidence_available = _evidence_gate(retrieval)

    mapping = _record()
    service.register_mapping_record(mapping)
    question = "For this synthetic demonstration, propose a draft study and show how missing mappings are gated."
    draft = _draft_from_synthetic_intake(question, evidence, corpus_digest)
    request = MappingRequest(
        biological_target="synthetic target", backend="synthetic_demo",
        dataset_id="synthetic_dataset", id_namespace="synthetic_id",
        intervention_type="activation",
    )
    resolution = resolve_mapping(request, [mapping])
    option = resolution.options[0]
    binding = select_mapping(
        resolution, [mapping], mapping_id=option.mapping_id,
        version=option.version, record_hash=option.record_hash,
    )
    bound_draft = bind_mapping_to_draft(draft, candidate_id="condition", binding=binding)
    created = workflow.create_draft(bound_draft)
    study_id = created["study"]["study_id"]
    if created["support_assessment"]["status"] != "READY_FOR_COMPUTATIONAL_REVIEW":
        raise RuntimeError("synthetic supported path did not reach human approval gate")
    workflow.approve(study_id, reviewer="synthetic-demo-operator (fixture only)")
    jobs = []
    for candidate_id in ("control", "condition"):
        submitted = workflow.submit(study_id, candidate_id=candidate_id)
        jobs.append(workflow.run(submitted["job"]["job_id"])["job"])
    report = service.get_report(study_id)

    missing_mapping_study = service.create_research_study(_study(mapping=None))
    missing_mapping_assessment = service.get_support_assessment(missing_mapping_study.study_id)
    unsupported_study = service.create_research_study(_study(mapping=mapping, assay="unsupported_assay"))
    unsupported_assessment = service.get_support_assessment(unsupported_study.study_id)
    branches = {
        "no_evidence": no_evidence,
        "evidence_present": evidence_available,
        "mapping_missing": {
            "status": missing_mapping_assessment["status"],
            "run_allowed": missing_mapping_assessment["run_allowed"],
        },
        "capability_mismatch": {
            "status": unsupported_assessment["status"],
            "run_allowed": unsupported_assessment["run_allowed"],
        },
    }
    chart_path = output_dir / "synthetic_workbench_report.png"
    _write_chart(report, chart_path)
    report_path = output_dir / "workbench_report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest_paths = [Path(job["manifest_path"]) for job in jobs]
    manifest_data = [json.loads(path.read_text(encoding="utf-8")) for path in manifest_paths]
    summary = {
        "schema_version": "ai-v2-synthetic-demo-1",
        "demo_mode": "SYNTHETIC_TEST_ONLY",
        "question": question,
        "ai_model_called": False,
        "biological_simulator_called": False,
        "heldout_status": "LOCKED_NOT_RUN",
        "supported_path": {
            "mapping_resolution": resolution.as_dict(),
            "mapping_binding": binding.as_dict(),
            "support_status": created["support_assessment"]["status"],
            "approval_status": "SYNTHETIC_FIXTURE_APPROVAL_ONLY",
            "jobs": [{"job_id": job["job_id"], "status": job["status"], "manifest_path": job["manifest_path"]} for job in jobs],
            "report_status": report["status"],
            "qc_statuses": [row.get("qc", {}).get("status") for row in report["results"]],
            "run_manifest_mapping_pins": [
                {
                    "candidate_id": payload["provenance"]["job_configuration"].get("candidate_id"),
                    "mapping_id": payload["provenance"]["job_configuration"].get("mapping_id"),
                    "mapping_version": payload["provenance"]["job_configuration"].get("mapping_version"),
                    "mapping_record_hash": payload["provenance"]["job_configuration"].get("mapping_record_hash"),
                    "ai_v2_provenance": payload["provenance"]["job_configuration"].get("ai_v2_provenance"),
                }
                for payload in manifest_data
            ],
        },
        "blocked_paths": branches,
        "ai_quality_evaluation": {
            "status": "BLOCKED_APPROVED_CORPUS_RUBRIC_AND_PROVIDER_POLICY_NOT_SUPPLIED",
            "metrics": None,
        },
        "artifacts": {
            "report_json": report_path.name,
            "visualization_png": chart_path.name,
            "retrieval_log": "retrieval.jsonl",
        },
        "claim_boundary": "Synthetic workflow demonstration only; no biological, Parkinson, wet-lab, or AI-quality claim.",
    }
    summary_path = output_dir / "demo_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    readme = [
        "# Synthetic AI V2 → Workbench demo",
        "",
        "**SYNTHETIC_TEST_ONLY.** No real LLM, biological mapping, FlyWire input, or simulator was used.",
        "",
        "## Demonstrated",
        "",
        "- allowlisted evidence and retrieval trace;",
        "- draft → exact mapping ID/version/hash → capability/support assessment;",
        "- explicit human-approval gate → two synthetic jobs → QC/report/provenance;",
        "- missing-evidence, missing-mapping, and unsupported-assay stop paths.",
        "",
        "See `demo_summary.json`, `workbench_report.json`, `retrieval.jsonl`, and `synthetic_workbench_report.png`.",
        "AI-quality evaluation remains blocked until the team approves a development corpus, human gold rubric, and provider/privacy policy.",
        "",
    ]
    (output_dir / "README.md").write_text("\n".join(readme), encoding="utf-8")
    checksums = {
        path.relative_to(output_dir).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(output_dir.rglob("*")) if path.is_file() and path.name != "sha256.json"
    }
    (output_dir / "sha256.json").write_text(json.dumps(checksums, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def _write_chart(report: Mapping[str, Any], path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = report.get("results", ())
    names = [str(row.get("candidate_id", "unknown")) for row in rows]
    values = [float(row.get("metrics", {}).get("metrics", {}).get("response", 0.0)) for row in rows]
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(names, values, color=["#4C78A8", "#F58518"][:len(names)])
    ax.set_ylabel("Synthetic response (arbitrary units)")
    ax.set_title("Synthetic fixture output — not biological data")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _evidence_gate(items: Any) -> dict[str, Any]:
    if not items:
        return {"status": "BLOCKED_NO_EVIDENCE", "draft_created": False}
    return {"status": "EVIDENCE_FOUND_SYNTHETIC_ONLY", "draft_created": True}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = run_demo(args.output_dir.resolve())
    except (OSError, ValueError, RuntimeError) as error:
        print(json.dumps({"status": "BLOCKED", "error": f"{type(error).__name__}: {error}"}, indent=2))
        return 2
    print(json.dumps({
        "status": result["demo_mode"],
        "heldout_status": result["heldout_status"],
        "workflow": result["supported_path"]["support_status"],
        "output_dir": str(args.output_dir.resolve()),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
