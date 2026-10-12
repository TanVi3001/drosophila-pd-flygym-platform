from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "audit_ai_v2_draft_eval_inputs.py"


def _write_draft(tmp_path: Path) -> tuple[Path, Path]:
    corpus_path = tmp_path / "corpus.jsonl"
    row = {
        "source_id": "INTERNAL_DOCS",
        "citation": "docs/architecture.md section X",
        "chunk_id": "chunk-1",
        "text": "The assistant remains a draft until a person approves it.",
        "provenance": "Draft paraphrase; pending human review.",
        "access_class": "DEVELOPMENT_INPUT",
    }
    corpus_path.write_text(json.dumps(row, separators=(",", ":")) + "\n", encoding="utf-8")
    corpus_hash = hashlib.sha256(corpus_path.read_bytes()).hexdigest()
    rubric = {
        "schema_version": "ai-v2-assistant-reference-draft-1",
        "status": "DRAFT_NOT_APPROVED",
        "partition": "DEVELOPMENT",
        "corpus_file": "corpus.jsonl",
        "corpus_sha256": corpus_hash,
        "reviewer_ids": [],
        "privacy_decision": {
            "status": "NOT_DECIDED",
            "provider_id": "",
            "provider_endpoint": "",
            "corpus_text_sharing_approved": False,
            "protocol_text_sharing_approved": False,
        },
        "evaluation_protocol_draft": {
            "comparison_systems": ["manual_template", "llm_no_retrieval", "llm_rag"]
        },
        "cases": [{
            "case_id": "Q1",
            "required_fields": ["auto_approval"],
            "gold_fields": {"auto_approval": False},
            "gold_missing_fields": [],
            "gold_evidence_chunk_ids": ["chunk-1"],
            "gold_citations": [{"source_id": "INTERNAL_DOCS", "chunk_id": "chunk-1"}],
        }],
    }
    rubric_path = tmp_path / "rubric.json"
    rubric_path.write_text(json.dumps(rubric), encoding="utf-8")
    return corpus_path, rubric_path


def _run(corpus_path: Path, rubric_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--corpus", str(corpus_path), "--rubric", str(rubric_path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_draft_input_audit_passes_but_never_claims_approval(tmp_path: Path):
    corpus_path, rubric_path = _write_draft(tmp_path)
    result = _run(corpus_path, rubric_path)

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["status"] == "STRUCTURE_PASS_DRAFT_ONLY"
    assert report["approval_granted"] is False
    assert report["provider_policy"] == "NOT_DECIDED"
    assert report["question_count"] == 1


def test_draft_input_audit_rejects_hash_drift_and_approval_claim(tmp_path: Path):
    corpus_path, rubric_path = _write_draft(tmp_path)
    rubric = json.loads(rubric_path.read_text(encoding="utf-8"))
    rubric["corpus_sha256"] = "0" * 64
    rubric["status"] = "APPROVED"
    rubric_path.write_text(json.dumps(rubric), encoding="utf-8")

    result = _run(corpus_path, rubric_path)

    assert result.returncode == 2
    assert "unapproved" in result.stderr


def test_draft_input_audit_rejects_outcome_like_keys(tmp_path: Path):
    corpus_path, rubric_path = _write_draft(tmp_path)
    rubric = json.loads(rubric_path.read_text(encoding="utf-8"))
    rubric["cases"][0]["outcome"] = "not allowed"
    rubric_path.write_text(json.dumps(rubric), encoding="utf-8")

    result = _run(corpus_path, rubric_path)

    assert result.returncode == 2
    assert "outcome/label-like keys" in result.stderr


def _write_protocol_draft(tmp_path: Path) -> tuple[Path, Path]:
    corpus_path, rubric_path = _write_draft(tmp_path)
    excerpt = "Synthetic software only. Copy explicit protocol fields; never invent missing information."
    source = "# Synthetic test guide\n\n## Extraction rules\n\n" + excerpt + "\n"
    source_path = tmp_path / "source.md"
    source_path.write_text(source, encoding="utf-8")
    chunk = json.loads(corpus_path.read_text(encoding="utf-8"))
    chunk.update(citation="source.md — Extraction rules", text=excerpt)
    corpus_path.write_text(json.dumps(chunk) + "\n", encoding="utf-8")
    fields = {
        "hypothesis": "Fixture hypothesis.",
        "falsifiable_prediction": "Fixture prediction.",
        "assay": "synthetic_assay",
        "primary_metric": "fixture_rate",
    }
    support = {key: key + ": " + value for key, value in fields.items()}
    rubric = json.loads(rubric_path.read_text(encoding="utf-8"))
    rubric.update(
        task_type="PROTOCOL_DRAFT_EXTRACTION",
        synthetic_fixture=True,
        claim_scope="SYNTHETIC_SOFTWARE_ONLY",
        reference_output_schema="protocol-rag-intake-draft-1",
        intended_endpoint="/v1/ai/rag/draft",
        source_document_file="source.md",
        source_document_sha256=hashlib.sha256(source_path.read_bytes()).hexdigest(),
        corpus_sha256=hashlib.sha256(corpus_path.read_bytes()).hexdigest(),
    )
    case = rubric["cases"][0]
    case.update(
        case_id="PROTO1", synthetic_fixture=True,
        protocol_text="Synthetic protocol.\n" + "\n".join(support.values()),
        required_fields=list(fields), gold_fields=dict(fields),
        answerability="COMPLETE_PROTOCOL", field_support=support,
        missing_field_reasons={},
        expected_output={
            "schema_version": "protocol-rag-intake-draft-1",
            "status": "DRAFT_REQUIRES_RESEARCHER_REVIEW",
            "proposed_fields": fields,
            "missing_fields": [],
            "approved": False, "study_created": False, "mapping_created": False,
        },
    )
    rubric_path.write_text(json.dumps(rubric), encoding="utf-8")
    return corpus_path, rubric_path


def test_legacy_policy_pack_keeps_its_implicit_task_type(tmp_path: Path):
    result = _run(*_write_draft(tmp_path))
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["task_type"] == "SOFTWARE_POLICY_QA"
    assert report["case_count"] == report["question_count"] == 1


def test_protocol_pack_passes_structure_without_becoming_approved(tmp_path: Path):
    result = _run(*_write_protocol_draft(tmp_path))
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["task_type"] == "PROTOCOL_DRAFT_EXTRACTION"
    assert report["status"] == "STRUCTURE_PASS_DRAFT_ONLY"
    assert report["approval_granted"] is False
    assert report["outputs_present"] is False


@pytest.mark.parametrize("line_ending", ["\n", "\r\n"])
def test_protocol_source_headings_accept_lf_and_windows_crlf(tmp_path, line_ending):
    corpus_path, rubric_path = _write_protocol_draft(tmp_path)
    source_path = tmp_path / "source.md"
    source = source_path.read_text(encoding="utf-8")
    source_path.write_bytes(source.replace("\n", line_ending).encode("utf-8"))
    rubric = json.loads(rubric_path.read_text(encoding="utf-8"))
    rubric["source_document_sha256"] = hashlib.sha256(source_path.read_bytes()).hexdigest()
    rubric_path.write_text(json.dumps(rubric), encoding="utf-8")
    result = _run(corpus_path, rubric_path)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("field,value,error", [
    ("reference_output_schema", "policy-answer-1", "actual RAG draft schema"),
    ("synthetic_fixture", False, "synthetic fixtures"),
    ("claim_scope", "BIOLOGICAL_VALIDATION", "biological quality"),
    ("intended_endpoint", "/v1/ai/rag/retrieve", "draft endpoint"),
    ("source_document_file", "../source.md", "sibling filename"),
    ("source_document_sha256", "0" * 64, "source document hash"),
])
def test_protocol_pack_rejects_wrong_scope_schema_and_source(tmp_path, field, value, error):
    corpus_path, rubric_path = _write_protocol_draft(tmp_path)
    rubric = json.loads(rubric_path.read_text(encoding="utf-8"))
    rubric[field] = value
    rubric_path.write_text(json.dumps(rubric), encoding="utf-8")
    result = _run(corpus_path, rubric_path)
    assert result.returncode == 2
    assert error in result.stderr


@pytest.mark.parametrize("mutation,error", [
    ("policy_field", "policy fields"),
    ("approve", "approved=false"),
    ("quote", "absent from protocol_text"),
    ("gold", "gold differs"),
    ("missing", "missing_fields differ"),
    ("question", "policy Q&A"),
    ("no_evidence", "no-evidence branch"),
    ("context", "context must match"),
])
def test_protocol_pack_rejects_reference_runtime_mismatch(tmp_path, mutation, error):
    corpus_path, rubric_path = _write_protocol_draft(tmp_path)
    rubric = json.loads(rubric_path.read_text(encoding="utf-8"))
    case = rubric["cases"][0]
    if mutation == "policy_field":
        case["expected_output"]["proposed_fields"]["auto_approval"] = False
    elif mutation == "approve":
        case["expected_output"]["approved"] = True
    elif mutation == "quote":
        case["field_support"]["hypothesis"] = "A quote absent from the protocol."
    elif mutation == "gold":
        case["gold_fields"]["hypothesis"] = "A different hypothesis."
    elif mutation == "missing":
        case["gold_missing_fields"] = ["assay"]
    elif mutation == "question":
        case["question"] = "May the AI auto-approve?"
    elif mutation == "no_evidence":
        case["answerability"] = "NO_EVIDENCE"
    elif mutation == "context":
        case["expected_output"]["proposed_fields"]["context"] = {"unknown": "value"}
    rubric_path.write_text(json.dumps(rubric), encoding="utf-8")
    result = _run(corpus_path, rubric_path)
    assert result.returncode == 2
    assert error in result.stderr


@pytest.mark.parametrize("no_evidence", [False, True])
def test_partial_and_no_evidence_references_match_runtime_contract(tmp_path, no_evidence):
    from drosophila_pd.workbench.intake import create_intake_draft

    corpus_path, rubric_path = _write_protocol_draft(tmp_path)
    rubric = json.loads(rubric_path.read_text(encoding="utf-8"))
    case = rubric["cases"][0]
    proposed = case["expected_output"]["proposed_fields"]
    removed = list(proposed) if no_evidence else ["primary_metric"]
    for field in removed:
        del proposed[field]
        del case["field_support"][field]
        case["gold_fields"][field] = None
    case["gold_missing_fields"] = removed
    case["expected_output"]["missing_fields"] = removed
    case["missing_field_reasons"] = {field: "Not available in this protocol." for field in removed}
    case["answerability"] = "NO_EVIDENCE" if no_evidence else "PARTIAL_PROTOCOL"
    if no_evidence:
        case["expected_output"]["status"] = "ABSTAINED_NO_EVIDENCE"
        case["gold_evidence_chunk_ids"] = []
        case["gold_citations"] = []
    rubric_path.write_text(json.dumps(rubric), encoding="utf-8")
    result = _run(corpus_path, rubric_path)
    assert result.returncode == 0, result.stderr

    if not no_evidence:
        class ReferenceStub:
            provider_id = "synthetic-contract-stub"

            def extract(self, _text, *, source_uri=None):
                return proposed

        # This replays a reference through sanitization, not a real model evaluation.
        draft = create_intake_draft(case["protocol_text"], ReferenceStub())
        assert draft["proposed_fields"] == proposed
        assert draft["missing_fields"] == case["gold_missing_fields"]
        assert draft["approved"] is False
