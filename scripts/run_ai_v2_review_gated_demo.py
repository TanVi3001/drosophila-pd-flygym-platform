"""Prepare/finalize a synthetic, human-in-the-loop AI V2 workflow demo.

This fixture exercises local evidence retrieval, an AI-shaped draft envelope,
human edits, exact selection of a fixture mapping, and Workbench StudySpec
support assessment. It never calls an LLM, a biological simulator, or a real
mapping registry and never approves/submits/runs a study.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from drosophila_pd.ai_v2.contracts import AIStudySpec
from drosophila_pd.ai_v2.mapping_resolution import (
    MappingRequest,
    bind_mapping_to_draft,
    resolve_mapping,
    select_mapping,
)
from drosophila_pd.ai_v2.workbench_workflow import AIV2WorkbenchWorkflow
from drosophila_pd.workbench.models import (
    CandidateSpec,
    CapabilityDescriptor,
    StudySpec,
    stable_hash,
)
from drosophila_pd.workbench.service import WorkbenchService
from drosophila_pd.workbench.store import WorkbenchStore
from drosophila_pd.workbench.support import MappingRecord


SCHEMA = "ai-v2-review-gated-synthetic-demo-1"
FIXTURE_NOTICE = "SYNTHETIC SOFTWARE DEMO ONLY; no real LLM, biology, FlyWire, or measured outcome."
TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)
REVIEW_FIELDS = {
    "schema_version", "fixture_notice", "reviewer_id", "decision", "rationale",
    "study_edits", "mapping_choice", "acknowledgements",
}
EDIT_FIELDS = {"name", "hypothesis", "falsifiable_prediction", "assay", "primary_metric"}
ACK_FIELDS = {"synthetic_fixture_only", "no_biological_claim", "study_spec_reviewed"}
FROZEN_INPUTS = {
    "protocol_input.json",
    "synthetic_corpus.jsonl",
    "retrieved_evidence.json",
    "ai_draft_fixture.json",
    "synthetic_mapping_registry.json",
    "mapping_options.json",
}
PREPARE_MANIFEST_FIELDS = {
    "schema_version", "demo_mode", "prepared_at_utc", "retrieval_k",
    "corpus_sha256", "frozen_input_sha256", "editable_review_file",
    "actual_llm_called", "biological_simulator_called", "heldout_status",
}


class SyntheticCapabilityOnly:
    """Workbench capability fixture; run() is intentionally unavailable."""

    name = "synthetic_demo"
    result_path = Path("result.json")

    def describe(self) -> CapabilityDescriptor:
        return CapabilityDescriptor(
            name=self.name,
            display_name="Synthetic fixture capability (not a biological simulator)",
            ready=True,
            supported_assays=("synthetic_demo",),
            supported_interventions=("none", "activation"),
            limitations=("Fixture-only support validation; no simulator is registered.",),
        )

    def validate(self, study: StudySpec, config: Mapping[str, object]) -> tuple[str, ...]:
        errors: list[str] = []
        if study.backend != self.name or study.assay != "synthetic_demo":
            errors.append("fixture accepts only synthetic_demo studies")
        if not config.get("candidate_id"):
            errors.append("candidate_id is required")
        return tuple(errors)

    def run(self, _context: Any) -> Any:
        raise RuntimeError("simulation execution is intentionally disabled in this demo")


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _checkpoint_sqlite(path: Path) -> None:
    """Checkpoint Workbench state before hashing its stable database file."""

    connection = sqlite3.connect(path)
    try:
        result = connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        if result is None or int(result[0]) != 0:
            raise RuntimeError("could not checkpoint synthetic Workbench state before hashing")
    finally:
        connection.close()


def _artifact_checksums(output: Path) -> dict[str, str]:
    """Hash stable artifacts, excluding transient SQLite WAL/SHM sidecars."""

    return {
        path.relative_to(output).as_posix(): _sha256(path)
        for path in sorted(output.rglob("*"))
        if path.is_file() and path.name != "sha256.json" and not path.name.endswith(("-wal", "-shm"))
    }


def _safe_session(path: Path, *, must_exist: bool) -> Path:
    root = (ROOT / ".workbench" / "ai-v2-e2e-demo").resolve()
    candidate = path.resolve()
    if candidate == root or not candidate.is_relative_to(root):
        raise ValueError(f"session must be inside the local ignored directory {root}")
    if must_exist:
        if not candidate.is_dir():
            raise ValueError("session directory does not exist")
    else:
        if candidate.exists() and (not candidate.is_dir() or any(candidate.iterdir())):
            raise ValueError("session directory must be new or empty; refusing to overwrite")
        candidate.mkdir(parents=True, exist_ok=True)
    return candidate


def _fixture_mapping() -> MappingRecord:
    return MappingRecord(
        mapping_id="SYNTHETIC_MAPPING_V1",
        version="1",
        biological_target="synthetic target",
        backend="synthetic_demo",
        id_namespace="synthetic_id",
        dataset_id="synthetic_dataset",
        intervention_type="activation",
        target_ids=("SYNTHETIC_TARGET_ID_001",),
        readout_ids=("SYNTHETIC_READOUT_ID_001",),
        sources=({"citation": "SYNTHETIC FIXTURE ONLY", "locator": "mapping demo fixture"},),
        review_status="COMPUTATIONALLY_REVIEWED",
        context={},
        reviewer="synthetic-fixture-placeholder-not-a-scientific-reviewer",
        reviewed_at="2000-01-01T00:00:00Z",
        limitations=("Invented software fixture; not a neuron, connectome mapping, or scientific review.",),
    )


def _fixture_corpus() -> list[dict[str, str]]:
    return [
        {
            "source_id": "SYNTHETIC_SOFTWARE_FIXTURE",
            "citation": "SYNTHETIC FIXTURE ONLY",
            "chunk_id": "fixture-study-fields-001",
            "text": "A software-only synthetic study uses assay synthetic_demo and primary metric metrics.response. These are fixture labels, not biological measurements.",
            "provenance": "Generated fixture text for software-flow demonstration.",
            "access_class": "DEVELOPMENT_INPUT",
        },
        {
            "source_id": "SYNTHETIC_SOFTWARE_FIXTURE",
            "citation": "SYNTHETIC FIXTURE ONLY",
            "chunk_id": "fixture-human-gate-001",
            "text": "A generated protocol proposal remains a draft until a human reviews and edits it. Mapping selection must use an exact registered mapping ID, version, and record hash.",
            "provenance": "Generated fixture text for software-flow demonstration.",
            "access_class": "DEVELOPMENT_INPUT",
        },
    ]


def _retrieve_fixture(query: str, corpus: list[dict[str, str]]) -> list[dict[str, Any]]:
    query_terms = set(token.casefold() for token in TOKEN_RE.findall(query))
    ranked: list[tuple[int, str, dict[str, str]]] = []
    for row in corpus:
        text_terms = set(token.casefold() for token in TOKEN_RE.findall(row["text"]))
        overlap = len(query_terms & text_terms)
        if overlap:
            ranked.append((overlap, row["chunk_id"], row))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [
        {
            "source_id": row["source_id"],
            "citation": row["citation"],
            "chunk_id": row["chunk_id"],
            "retrieval_score": float(score),
            "provenance": row["provenance"],
            "access_class": row["access_class"],
            "text": row["text"],
        }
        for score, _chunk_id, row in ranked[:5]
    ]


def prepare(session_dir: Path) -> Path:
    session = _safe_session(session_dir, must_exist=False)
    protocol = {
        "fixture_only": True,
        "text": (
            "Software demo protocol: create a synthetic study about a synthetic target. "
            "Use the synthetic_demo assay and metrics.response. Compare a synthetic activation "
            "condition with a synthetic control. No fly, neuron, intervention, or observed outcome is represented."
        ),
        "source_uri": "synthetic://ai-v2/demo-protocol",
    }
    corpus = _fixture_corpus()
    corpus_bytes = "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in corpus).encode("utf-8")
    corpus_sha = hashlib.sha256(corpus_bytes).hexdigest()
    evidence = _retrieve_fixture(protocol["text"], corpus)
    mapping = _fixture_mapping()

    # The draft envelope is deterministic fixture output, not a model response.
    study_draft = StudySpec(
        name="SYNTHETIC DEMO ONLY — no biological interpretation",
        hypothesis="A synthetic condition changes a generated scalar.",
        falsifiable_prediction="The fixture response differs between synthetic condition and control.",
        assay="synthetic_demo",
        primary_metric="metrics.response",
        backend="synthetic_demo",
        candidates=(
            CandidateSpec("control", "Synthetic control", intervention={"type": "none"}),
            CandidateSpec(
                "condition", "Synthetic condition", target="synthetic target",
                intervention={"type": "activation"},
                sources=({"citation": "SYNTHETIC FIXTURE ONLY", "locator": "fixture-study-fields-001"},),
            ),
        ),
        controls=({"id": "control", "role": "synthetic fixture control"},),
        sources=tuple({"citation": item["citation"], "locator": item["chunk_id"]} for item in evidence),
        run_plan={"backend_requirements": {"dataset_id": "synthetic_dataset", "id_namespace": "synthetic_id"}},
        metadata={"dataset_id": "synthetic_dataset", "id_namespace": "synthetic_id", "synthetic_fixture": True},
    )
    draft = AIStudySpec(
        study=study_draft,
        evidence_ids=tuple(item["chunk_id"] for item in evidence),
        provenance={
            "provider_id": "synthetic-fixture-not-an-llm",
            "model_id": "none",
            "prompt_version": "synthetic-fixture-draft-v1",
            "corpus_sha256": corpus_sha,
            "generator_output_sha256": stable_hash(study_draft.as_dict()),
        },
    )
    request = MappingRequest(
        biological_target="synthetic target",
        backend="synthetic_demo",
        dataset_id="synthetic_dataset",
        id_namespace="synthetic_id",
        intervention_type="activation",
    )
    resolution = resolve_mapping(request, [mapping])
    if resolution.status != "HUMAN_SELECTION_REQUIRED":
        raise RuntimeError("the synthetic fixture mapping did not enter the explicit-selection path")

    protocol_path = session / "protocol_input.json"
    corpus_path = session / "synthetic_corpus.jsonl"
    evidence_path = session / "retrieved_evidence.json"
    draft_path = session / "ai_draft_fixture.json"
    registry_path = session / "synthetic_mapping_registry.json"
    options_path = session / "mapping_options.json"
    _write_json(protocol_path, protocol)
    corpus_path.write_bytes(corpus_bytes)
    _write_json(evidence_path, {
        "status": "SYNTHETIC_EVIDENCE_RETRIEVED",
        "retrieval_engine": "fixture-token-overlap-v1",
        "internet_access": False,
        "hits": evidence,
    })
    _write_json(draft_path, draft.as_dict())
    _write_json(registry_path, {"fixture_only": True, "records": [mapping.as_dict()]})
    _write_json(options_path, {
        "fixture_only": True,
        "resolution": resolution.as_dict(),
        "selectable_records": [{
            "mapping_id": mapping.mapping_id,
            "version": mapping.version,
            "record_hash": mapping.record_hash,
            "synthetic_target_ids": list(mapping.target_ids),
            "synthetic_readout_ids": list(mapping.readout_ids),
            "review_status": mapping.review_status,
            "note": "All IDs and review metadata are invented fixtures, not biological mappings/reviews.",
        }],
    })
    review_form = {
        "schema_version": SCHEMA,
        "fixture_notice": FIXTURE_NOTICE,
        "reviewer_id": "",
        "decision": "PENDING",
        "rationale": "",
        "study_edits": {
            "name": study_draft.name,
            "hypothesis": study_draft.hypothesis,
            "falsifiable_prediction": study_draft.falsifiable_prediction,
            "assay": study_draft.assay,
            "primary_metric": study_draft.primary_metric,
        },
        "mapping_choice": {"mapping_id": "", "version": "", "record_hash": ""},
        "acknowledgements": {key: False for key in sorted(ACK_FIELDS)},
    }
    review_path = session / "human_review_form.json"
    _write_json(review_path, review_form)
    frozen_inputs = [protocol_path, corpus_path, evidence_path, draft_path, registry_path, options_path]
    _write_json(session / "prepare_manifest.json", {
        "schema_version": SCHEMA,
        "demo_mode": "SYNTHETIC_FIXTURE_ONLY",
        "prepared_at_utc": datetime.now(UTC).isoformat(),
        "retrieval_k": 5,
        "corpus_sha256": corpus_sha,
        "frozen_input_sha256": {path.name: _sha256(path) for path in frozen_inputs},
        "editable_review_file": review_path.name,
        "actual_llm_called": False,
        "biological_simulator_called": False,
        "heldout_status": "LOCKED_NOT_RUN",
    })
    (session / "README.md").write_text(
        "# Synthetic AI V2 review-gated demo\n\n"
        "**Fixture only:** no hosted LLM, Drosophila biology, FlyWire input, external evidence, or simulator.\n\n"
        "1. Inspect `protocol_input.json`, `retrieved_evidence.json`, and `ai_draft_fixture.json`.\n"
        "2. Inspect `mapping_options.json`; its mapping and IDs are invented fixture values.\n"
        "3. Edit `human_review_form.json` yourself. Do not change frozen input files.\n"
        "4. Run the finalize command in `docs/ai_v2/review_gated_demo.md`. It will validate the selected exact mapping and StudySpec.\n"
        "5. Finalization stops before Workbench approval, job submission, and simulation.\n\n"
        "The demo cannot establish AI quality, mapping validity, biological validity, or wet-lab utility.\n",
        encoding="utf-8",
    )
    return session


def _read_json(path: Path) -> Any:
    value = json.loads(path.read_text(encoding="utf-8"))
    return value


def finalize(session_dir: Path) -> dict[str, Any]:
    session = _safe_session(session_dir, must_exist=True)
    manifest = _read_json(session / "prepare_manifest.json")
    if not isinstance(manifest, dict) or set(manifest) != PREPARE_MANIFEST_FIELDS or manifest.get("schema_version") != SCHEMA:
        raise ValueError("unsupported demo session manifest")
    if manifest.get("demo_mode") != "SYNTHETIC_FIXTURE_ONLY" or manifest.get("heldout_status") != "LOCKED_NOT_RUN":
        raise ValueError("demo manifest scientific-scope boundary is invalid")
    frozen_hashes = manifest.get("frozen_input_sha256")
    if not isinstance(frozen_hashes, dict) or set(frozen_hashes) != FROZEN_INPUTS:
        raise ValueError("demo manifest frozen-input inventory is incomplete or unsupported")
    for filename, expected in frozen_hashes.items():
        if Path(filename).name != filename:
            raise ValueError("demo manifest input paths must be simple filenames")
        path = session / filename
        if not path.is_file() or _sha256(path) != expected:
            raise ValueError(f"frozen demo input changed or is missing: {filename}")
    output = session / "finalized"
    if output.exists():
        raise ValueError("finalized output already exists; start a new session rather than overwrite")

    review = _read_json(session / "human_review_form.json")
    if not isinstance(review, dict) or set(review) != REVIEW_FIELDS:
        raise ValueError("human review form has missing or unsupported fields")
    if review.get("schema_version") != SCHEMA:
        raise ValueError("human review form schema does not match")
    if not isinstance(review.get("fixture_notice"), str) or review["fixture_notice"] != FIXTURE_NOTICE:
        raise ValueError("human review fixture_notice does not match the required synthetic-only notice")
    reviewer = review.get("reviewer_id")
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise ValueError("enter your self-reported reviewer_id in human_review_form.json")
    if review.get("decision") != "ACCEPT_FOR_SYNTHETIC_DEMO_ONLY":
        raise ValueError("decision must be ACCEPT_FOR_SYNTHETIC_DEMO_ONLY to continue")
    if not isinstance(review.get("rationale"), str) or not review["rationale"].strip():
        raise ValueError("write a short synthetic-demo rationale in the review form")
    if not isinstance(review.get("acknowledgements"), dict) or set(review["acknowledgements"]) != ACK_FIELDS or not all(
        review["acknowledgements"].get(item) is True for item in ACK_FIELDS
    ):
        raise ValueError("all synthetic-scope acknowledgements must be true")
    edits = review.get("study_edits")
    if not isinstance(edits, dict) or set(edits) != EDIT_FIELDS or any(
        not isinstance(value, str) or not value.strip() for value in edits.values()
    ):
        raise ValueError("study_edits must contain five non-empty string fields")
    if edits["assay"] != "synthetic_demo" or edits["primary_metric"] != "metrics.response":
        raise ValueError("fixture capability supports only assay=synthetic_demo and primary_metric=metrics.response")

    protocol = _read_json(session / "protocol_input.json")
    evidence = _read_json(session / "retrieved_evidence.json")
    draft_payload = _read_json(session / "ai_draft_fixture.json")
    registry = _read_json(session / "synthetic_mapping_registry.json")
    choice = review.get("mapping_choice")
    if not isinstance(choice, dict) or set(choice) != {"mapping_id", "version", "record_hash"}:
        raise ValueError("mapping_choice must contain exact mapping_id, version, and record_hash")
    records = [MappingRecord.from_dict(row) for row in registry.get("records", [])]
    if not records or registry.get("fixture_only") is not True:
        raise ValueError("synthetic mapping fixture registry is invalid")
    request = MappingRequest(
        biological_target="synthetic target", backend="synthetic_demo",
        dataset_id="synthetic_dataset", id_namespace="synthetic_id",
        intervention_type="activation",
    )
    resolution = resolve_mapping(request, records)
    binding = select_mapping(
        resolution, records,
        mapping_id=str(choice.get("mapping_id", "")),
        version=str(choice.get("version", "")),
        record_hash=str(choice.get("record_hash", "")),
    )
    base_draft = AIStudySpec.from_dict(draft_payload)
    source = base_draft.study
    edited_study = StudySpec(
        name=edits["name"], hypothesis=edits["hypothesis"],
        falsifiable_prediction=edits["falsifiable_prediction"],
        assay=edits["assay"], primary_metric=edits["primary_metric"],
        backend=source.backend, candidates=source.candidates,
        controls=source.controls, sources=source.sources,
        run_plan=source.run_plan, metadata=source.metadata,
    )
    edited_draft = AIStudySpec(
        study=edited_study,
        evidence_ids=base_draft.evidence_ids,
        approval_status="DRAFT",
        provenance=base_draft.provenance,
    )
    bound_draft = bind_mapping_to_draft(edited_draft, candidate_id="condition", binding=binding)

    output.mkdir(parents=False)
    service = WorkbenchService(
        store=WorkbenchStore(output / "synthetic_demo_state.sqlite3"),
        artifact_root=output / "workbench_artifacts",
        adapters={"synthetic_demo": SyntheticCapabilityOnly()},
        assays={},
    )
    service.register_mapping_record(records[0])
    workflow = AIV2WorkbenchWorkflow(service)
    created = workflow.create_draft(bound_draft)
    assessment = created["support_assessment"]
    if assessment.get("status") != "READY_FOR_COMPUTATIONAL_REVIEW":
        raise RuntimeError(f"fixture StudySpec did not pass support assessment: {assessment.get('status')}")
    status = workflow.status(created["study"]["study_id"])
    if status["stage"] != "AWAITING_HUMAN_APPROVAL" or status["approval"] is not None or status["jobs"]:
        raise RuntimeError("demo did not stop at the required approval gate")

    _write_json(output / "human_review_record.json", {
        "reviewer_id_self_reported": reviewer.strip(),
        "decision": review["decision"],
        "rationale": review["rationale"],
        "study_edits": edits,
        "selected_mapping": binding.as_dict(),
        "review_scope": "Synthetic software demonstration only; not a biological mapping review.",
        "recorded_at_utc": datetime.now(UTC).isoformat(),
    })
    _write_json(output / "validated_study_spec.json", created["study"])
    _write_json(output / "support_assessment.json", assessment)
    summary = {
        "schema_version": SCHEMA,
        "status": "SYNTHETIC_STUDYSPEC_VALIDATED_AWAITING_RESEARCHER_APPROVAL",
        "stages": {
            "protocol": "SYNTHETIC_FIXTURE",
            "evidence_retrieval": evidence.get("status"),
            "draft": "SYNTHETIC_FIXTURE_NOT_A_MODEL_OUTPUT",
            "human_review_and_edits": "SELF_REPORTED_LOCAL_DEMO_REVIEW",
            "mapping": "EXACT_FIXTURE_MAPPING_SELECTED_BY_OPERATOR",
            "studyspec_validation": assessment["status"],
        },
        "retrieved_chunk_ids": [item["chunk_id"] for item in evidence.get("hits", [])],
        "corpus_sha256": manifest["corpus_sha256"],
        "study_id": created["study"]["study_id"],
        "study_configuration_hash": created["study"]["configuration_hash"],
        "support_assessment_hash": assessment["assessment_hash"],
        "human_approval": False,
        "job_submitted": False,
        "simulation_run": False,
        "actual_llm_called": False,
        "biological_mapping_used": False,
        "biological_validation": False,
        "heldout_status": "LOCKED_NOT_RUN",
        "claim_boundary": "Synthetic software-flow demonstration only; not AI-quality or biological evidence.",
    }
    _write_json(output / "demo_summary.json", summary)
    _checkpoint_sqlite(output / "synthetic_demo_state.sqlite3")
    checksums = _artifact_checksums(output)
    _write_json(output / "sha256.json", checksums)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true", help="write synthetic inputs and a blank human-review form")
    mode.add_argument("--finalize", action="store_true", help="validate the edited review form and StudySpec")
    parser.add_argument("--session-dir", type=Path, help="session under .workbench/ai-v2-e2e-demo")
    args = parser.parse_args()
    try:
        if args.prepare:
            default = ROOT / ".workbench" / "ai-v2-e2e-demo" / datetime.now(UTC).strftime("session-%Y%m%dT%H%M%SZ")
            session = prepare(args.session_dir or default)
            print(json.dumps({"status": "SYNTHETIC_REVIEW_REQUIRED", "session_dir": str(session), "review_form": str(session / "human_review_form.json"), "heldout_status": "LOCKED_NOT_RUN"}, indent=2))
        else:
            if args.session_dir is None:
                parser.error("--finalize requires --session-dir")
            summary = finalize(args.session_dir)
            print(json.dumps({"status": summary["status"], "study_id": summary["study_id"], "simulation_run": False, "output_dir": str(args.session_dir.resolve() / "finalized"), "heldout_status": summary["heldout_status"]}, indent=2))
    except (OSError, ValueError, TypeError, RuntimeError, KeyError) as error:
        print(json.dumps({"status": "BLOCKED", "error": f"{type(error).__name__}: {error}"}, indent=2))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
