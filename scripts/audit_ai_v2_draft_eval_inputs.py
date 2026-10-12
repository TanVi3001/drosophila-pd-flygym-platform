#!/usr/bin/env python3
"""Structurally audit draft AI V2 corpus/rubric inputs without approving them.

This checks hashes, schemas, references, and obvious forbidden data fields. It
cannot decide whether prose contains a biological outcome or is safe to share;
human review is still required before creating an approved manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


CHUNK_FIELDS = {
    "source_id", "citation", "chunk_id", "text", "provenance", "access_class"
}
FORBIDDEN_KEYS = {
    "label", "labels", "outcome", "outcomes", "phenotype", "response_class",
    "responder_status", "experimental_result", "result_summary", "heldout_label",
}
REQUIRED_SYSTEMS = {"manual_template", "llm_no_retrieval", "llm_rag"}
TASK_TYPES = {"SOFTWARE_POLICY_QA", "PROTOCOL_DRAFT_EXTRACTION"}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _forbidden_keys(value: Any, path: str = "root") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).casefold() in FORBIDDEN_KEYS:
                found.append(f"{path}.{key}")
            found.extend(_forbidden_keys(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_forbidden_keys(child, f"{path}[{index}]"))
    return found


def _audit_protocol_references(
    rubric: dict[str, Any], chunks: dict[str, dict[str, str]], rubric_path: Path
) -> None:
    """Check synthetic reference shape against intake, never approve its content."""
    from drosophila_pd.workbench import intake

    _require(rubric.get("synthetic_fixture") is True,
             "this protocol pack must explicitly identify synthetic fixtures")
    _require(rubric.get("claim_scope") == "SYNTHETIC_SOFTWARE_ONLY",
             "synthetic protocol references cannot claim biological quality")
    _require(rubric.get("reference_output_schema") == "protocol-rag-intake-draft-1",
             "protocol references must target the actual RAG draft schema")
    _require(rubric.get("intended_endpoint") == "/v1/ai/rag/draft",
             "protocol references must identify the draft endpoint")
    source_name = rubric.get("source_document_file")
    _require(isinstance(source_name, str) and source_name == Path(source_name).name,
             "source document must be a sibling filename")
    source_bytes = (rubric_path.parent / source_name).read_bytes()
    _require(hashlib.sha256(source_bytes).hexdigest() == rubric.get("source_document_sha256"),
             "source document hash does not match exact bytes")
    source_text = source_bytes.decode("utf-8")
    for chunk in chunks.values():
        _require(chunk["text"] in source_text,
                 f"{chunk['chunk_id']} is not an exact excerpt of the synthetic source")
        prefix = source_name + " — "
        _require(chunk["citation"].startswith(prefix),
                 "protocol chunk must cite its synthetic source document")
        heading = chunk["citation"][len(prefix):]
        _require(f"## {heading}" in source_text.splitlines(),
                 f"unknown synthetic source heading: {heading}")

    runtime_required = set(intake._REQUIRED_FIELDS)
    allowed_proposals = intake._ALLOWED_FIELDS - {"citations", "missing_fields"}
    for case in rubric["cases"]:
        case_id = case["case_id"]
        text = case.get("protocol_text")
        _require(isinstance(text, str) and 0 < len(text.strip()) <= 20_000,
                 f"{case_id} needs non-empty runtime-sized protocol_text")
        _require("question" not in case, f"{case_id} must not masquerade as policy Q&A")
        _require(case.get("synthetic_fixture") is True,
                 f"{case_id} must be explicitly synthetic")
        expected = case.get("expected_output")
        _require(isinstance(expected, dict), f"{case_id} needs an expected output reference")
        _require(set(expected) == {
            "schema_version", "status", "proposed_fields", "missing_fields",
            "approved", "study_created", "mapping_created",
        }, f"{case_id} has unsupported expected output fields")
        _require(expected["schema_version"] == rubric["reference_output_schema"],
                 f"{case_id} expected output schema differs from runtime")
        for flag in ("approved", "study_created", "mapping_created"):
            _require(expected[flag] is False, f"{case_id} must keep {flag}=false")
        proposed = expected["proposed_fields"]
        _require(isinstance(proposed, dict) and set(proposed).issubset(allowed_proposals),
                 f"{case_id} has policy fields or unsupported proposed fields")
        _require(not intake._contains_forbidden_key(proposed),
                 f"{case_id} reference must not generate mappings or executable choices")
        for field, value in proposed.items():
            if field in runtime_required | {"name"}:
                _require(isinstance(value, str) and bool(value.strip()),
                         f"{case_id}.{field} must be a non-empty string")
            elif field == "context":
                _require(isinstance(value, dict) and bool(value)
                         and set(value).issubset(intake._ALLOWED_CONTEXT_FIELDS)
                         and all(isinstance(item, str) and item.strip() for item in value.values()),
                         f"{case_id} context must match runtime allowed string fields")
            else:
                allowed = (intake._ALLOWED_SUGGESTION_FIELDS if field == "candidate_suggestions"
                           else intake._ALLOWED_CONTROL_FIELDS)
                _require(isinstance(value, list)
                         and all(isinstance(item, dict) and set(item).issubset(allowed)
                                 for item in value), f"{case_id} has malformed suggestions")
        required = case["required_fields"]
        gold = case["gold_fields"]
        _require(len(required) == len(set(required))
                 and runtime_required.issubset(required) and set(required).issubset(allowed_proposals),
                 f"{case_id} required_fields must cover runtime core fields, not policy answers")
        _require(set(gold) == set(required), f"{case_id} gold field set differs from required_fields")
        for field in required:
            _require(gold[field] == proposed.get(field),
                     f"{case_id}.{field} gold differs from expected proposed_fields")
        missing = runtime_required - set(proposed)
        for declared in (expected["missing_fields"], case.get("gold_missing_fields")):
            _require(isinstance(declared, list) and len(declared) == len(set(declared))
                     and set(declared) == missing,
                     f"{case_id} missing_fields differ from runtime required-field behavior")
        support = case.get("field_support")
        _require(isinstance(support, dict) and set(support) == set(proposed),
                 f"{case_id} needs support quotes for every proposed field")
        for field, quote in support.items():
            _require(isinstance(quote, str) and bool(quote.strip()) and quote in text,
                     f"{case_id}.{field} support quote is absent from protocol_text")
            if isinstance(proposed[field], str):
                _require(proposed[field] in quote,
                         f"{case_id}.{field} exact reference value is absent from its quote")
        reasons = case.get("missing_field_reasons")
        _require(isinstance(reasons, dict) and set(reasons) == missing
                 and all(isinstance(reason, str) and reason.strip() for reason in reasons.values()),
                 f"{case_id} needs a reason for each missing field")
        no_evidence = case.get("answerability") == "NO_EVIDENCE"
        if no_evidence:
            _require(expected["status"] == "ABSTAINED_NO_EVIDENCE"
                     and not proposed and not case["gold_evidence_chunk_ids"],
                     f"{case_id} no-evidence branch must abstain with empty proposed fields")
        else:
            _require(case.get("answerability") in {"COMPLETE_PROTOCOL", "PARTIAL_PROTOCOL"},
                     f"{case_id} unknown protocol answerability")
            _require(expected["status"] == "DRAFT_REQUIRES_RESEARCHER_REVIEW"
                     and bool(case["gold_evidence_chunk_ids"]),
                     f"{case_id} supported protocol must remain a human-review draft")
            _require((case["answerability"] == "PARTIAL_PROTOCOL") == bool(missing),
                     f"{case_id} answerability differs from required-field completeness")


def audit_inputs(corpus_path: Path, rubric_path: Path) -> dict[str, Any]:
    corpus_bytes = corpus_path.read_bytes()
    rubric = json.loads(rubric_path.read_text(encoding="utf-8"))
    _require(isinstance(rubric, dict), "rubric root must be a JSON object")
    _require(rubric.get("schema_version") == "ai-v2-assistant-reference-draft-1",
             "only the non-evaluable draft rubric schema is accepted")
    _require(rubric.get("status") == "DRAFT_NOT_APPROVED",
             "draft rubric must remain explicitly unapproved")
    _require(rubric.get("partition") == "DEVELOPMENT",
             "draft inputs must be DEVELOPMENT only")
    task_type = rubric.get("task_type", "SOFTWARE_POLICY_QA")
    _require(isinstance(task_type, str) and task_type in TASK_TYPES, "unknown reference task_type")
    _require(not rubric.get("reviewer_ids"),
             "this audit must not turn pending reviewer fields into approval")
    _require("systems" not in rubric and "outputs" not in rubric,
             "draft reference pack must not contain generated evaluation outputs")

    privacy = rubric.get("privacy_decision")
    _require(isinstance(privacy, dict), "privacy_decision must be an object")
    _require(privacy.get("status") == "NOT_DECIDED", "provider/privacy decision is still pending")
    _require(privacy.get("corpus_text_sharing_approved") is False,
             "draft must not imply corpus sharing approval")
    _require(privacy.get("protocol_text_sharing_approved") is False,
             "draft must not imply protocol sharing approval")
    _require(not privacy.get("provider_id") and not privacy.get("provider_endpoint"),
             "provider identity must remain unset until selected and reviewed")

    actual_hash = hashlib.sha256(corpus_bytes).hexdigest()
    _require(rubric.get("corpus_sha256") == actual_hash,
             "rubric corpus_sha256 does not match exact corpus bytes")

    chunks: dict[str, dict[str, str]] = {}
    sources: set[str] = set()
    for line_number, raw_line in enumerate(corpus_bytes.splitlines(), start=1):
        _require(bool(raw_line.strip()), f"blank JSONL row at line {line_number}")
        try:
            row = json.loads(raw_line)
        except json.JSONDecodeError as error:
            raise ValueError(f"invalid JSONL at line {line_number}: {error}") from error
        _require(isinstance(row, dict) and set(row) == CHUNK_FIELDS,
                 f"corpus row {line_number} has unsupported or missing fields")
        _require(all(isinstance(row[key], str) and row[key].strip() for key in CHUNK_FIELDS),
                 f"corpus row {line_number} has an empty/non-string field")
        _require(row["access_class"] in {"PUBLIC_UNLABELED", "DEVELOPMENT_INPUT"},
                 f"corpus row {line_number} has a forbidden access class")
        chunk_id = row["chunk_id"]
        _require(chunk_id not in chunks, f"duplicate chunk_id: {chunk_id}")
        chunks[chunk_id] = row
        sources.add(row["source_id"])

    cases = rubric.get("cases")
    _require(isinstance(cases, list) and cases, "rubric cases must be a non-empty list")
    case_ids: set[str] = set()
    for index, case in enumerate(cases):
        _require(isinstance(case, dict), f"case {index} must be an object")
        case_id = case.get("case_id")
        _require(isinstance(case_id, str) and case_id.strip(), f"case {index} needs case_id")
        _require(case_id not in case_ids, f"duplicate case_id: {case_id}")
        case_ids.add(case_id)
        required = case.get("required_fields")
        gold = case.get("gold_fields")
        _require(isinstance(required, list) and required, f"{case_id} needs required_fields")
        _require(isinstance(gold, dict) and all(field in gold for field in required),
                 f"{case_id} lacks a gold value for a required field")
        evidence_ids = case.get("gold_evidence_chunk_ids")
        _require(isinstance(evidence_ids, list), f"{case_id} gold evidence must be a list")
        _require(set(evidence_ids).issubset(chunks), f"{case_id} refers to an unknown evidence chunk")
        citations = case.get("gold_citations")
        _require(isinstance(citations, list), f"{case_id} gold citations must be a list")
        cited_pairs: set[tuple[str, str]] = set()
        for citation in citations:
            _require(isinstance(citation, dict), f"{case_id} has a malformed gold citation")
            pair = (citation.get("source_id"), citation.get("chunk_id"))
            _require(pair[1] in chunks and chunks[pair[1]]["source_id"] == pair[0],
                     f"{case_id} citation does not identify a corpus source/chunk pair")
            cited_pairs.add(pair)
        expected_pairs = {
            (chunks[chunk_id]["source_id"], chunk_id) for chunk_id in evidence_ids
        }
        _require(cited_pairs == expected_pairs,
                 f"{case_id} gold citations and gold evidence IDs differ")

    forbidden = _forbidden_keys(rubric)
    _require(not forbidden, "forbidden outcome/label-like keys found: " + ", ".join(forbidden))
    _require(REQUIRED_SYSTEMS.issubset(
        set(rubric.get("evaluation_protocol_draft", {}).get("comparison_systems", []))
    ), "draft comparator list must preserve all three planned systems")
    if task_type == "PROTOCOL_DRAFT_EXTRACTION":
        _audit_protocol_references(rubric, chunks, rubric_path)

    return {
        "status": "STRUCTURE_PASS_DRAFT_ONLY",
        "partition": "DEVELOPMENT",
        "task_type": task_type,
        "corpus_sha256": actual_hash,
        "source_count": len(sources),
        "chunk_count": len(chunks),
        "question_count": len(cases) if task_type == "SOFTWARE_POLICY_QA" else 0,
        "case_count": len(cases),
        "reviewer_count": 0,
        "provider_policy": "NOT_DECIDED",
        "outputs_present": False,
        "approval_granted": False,
        "note": "Structural checks only; human content/privacy review remains mandatory.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=Path(".workbench/evidence/rag_development_corpus_draft.jsonl"))
    parser.add_argument("--rubric", type=Path, default=Path(".workbench/evidence/ai_v2_development_questions_rubric_draft.json"))
    args = parser.parse_args()
    try:
        report = audit_inputs(args.corpus, args.rubric)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"status": "FAIL", "error": str(error)}, indent=2), file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
