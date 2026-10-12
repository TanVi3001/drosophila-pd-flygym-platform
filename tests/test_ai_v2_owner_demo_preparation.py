from __future__ import annotations

import copy
import json
import runpy
from pathlib import Path

import pytest

from drosophila_pd.ai_v2.comparison import encoded, digest, prepare_inputs, read_json
from drosophila_pd.workbench import intake

ROOT = Path(__file__).resolve().parents[1]
helper = runpy.run_path(str(ROOT / "scripts" / "prepare_ai_v2_owner_demo.py"))
prepare_review = helper["prepare_review"]
freeze_review = helper["freeze_review"]
verify_inventory = helper["verify_inventory"]


def synthetic_inputs(tmp_path: Path):
    folder = tmp_path / "inputs"
    folder.mkdir()
    source = folder / "source.md"
    excerpt = "Synthetic protocol. Copy only declared fields. No biological results."
    source.write_text("# Synthetic source\n\n## Rules\n\n" + excerpt + "\n", encoding="utf-8")
    chunk = {"source_id": "SYNTHETIC_PROTOCOL_GUIDE_V1", "chunk_id": "fixture:rules",
             "citation": "source.md — Rules", "text": excerpt,
             "provenance": "Synthetic software fixture only", "access_class": "DEVELOPMENT_INPUT"}
    corpus = folder / "corpus.jsonl"
    corpus.write_bytes((json.dumps(chunk) + "\n").encode())
    fields = {"hypothesis": "Fixture hypothesis.", "falsifiable_prediction": "Fixture prediction.",
              "assay": "synthetic_assay", "primary_metric": "fixture_metric"}
    cases = []
    for ordinal in range(1, 13):
        values = copy.deepcopy(fields)
        support = {key: key + ": " + value for key, value in values.items()}
        if ordinal == 3:
            values["context"] = {"sex": "female"}
            support["context"] = 'context: {"sex":"female","feeding_state":"not specified"}'
        no_hit = ordinal == 12
        if no_hit:
            values, support = {}, {}
        required = list(fields) + (["context"] if ordinal == 3 else [])
        missing = list(fields) if no_hit else []
        cases.append({
            "case_id": f"AI_PROTO_DEV_DRAFT_{ordinal:03d}", "synthetic_fixture": True,
            "category": "no_lexical_evidence_probe" if no_hit else "fixture_protocol",
            "protocol_text": "zzqvunsupportedprobe" if no_hit else "Synthetic protocol.\n" + "\n".join(support.values()),
            "required_fields": required, "gold_fields": {key: values.get(key) for key in required},
            "gold_missing_fields": missing, "gold_evidence_chunk_ids": [] if no_hit else ["fixture:rules"],
            "gold_citations": [] if no_hit else [{"source_id": chunk["source_id"], "chunk_id": chunk["chunk_id"]}],
            "answerability": "NO_EVIDENCE" if no_hit else "COMPLETE_PROTOCOL",
            "field_support": support, "missing_field_reasons": {key: "Not specified" for key in missing},
            "expected_output": {"schema_version": "protocol-rag-intake-draft-1",
                                "status": "ABSTAINED_NO_EVIDENCE" if no_hit else "DRAFT_REQUIRES_RESEARCHER_REVIEW",
                                "proposed_fields": values, "missing_fields": missing,
                                "approved": False, "study_created": False, "mapping_created": False},
        })
    rubric = folder / "rubric.json"
    rubric.write_bytes(encoded({
        "schema_version": "ai-v2-assistant-reference-draft-1", "status": "DRAFT_NOT_APPROVED",
        "partition": "DEVELOPMENT", "task_type": "PROTOCOL_DRAFT_EXTRACTION",
        "synthetic_fixture": True, "claim_scope": "SYNTHETIC_SOFTWARE_ONLY",
        "reference_output_schema": "protocol-rag-intake-draft-1", "intended_endpoint": "/v1/ai/rag/draft",
        "corpus_file": corpus.name, "corpus_sha256": digest(corpus.read_bytes()),
        "source_document_file": source.name, "source_document_sha256": digest(source.read_bytes()),
        "reviewer_ids": [], "review_policy_draft": {"owner_reviewed_demo": {"reviewer_count": 1}},
        "privacy_decision": {"status": "NOT_DECIDED", "provider_id": "", "provider_endpoint": "",
                             "corpus_text_sharing_approved": False, "protocol_text_sharing_approved": False},
        "evaluation_protocol_draft": {"retrieval_k": 5, "comparison_systems": ["manual_template", "llm_no_retrieval", "llm_rag"]},
        "cases": cases,
    }))
    plan = folder / "plan.md"
    plan.write_text("Fixture measurement plan: 11 protocol cases plus one no-hit diagnostic.\n", encoding="utf-8")
    return corpus, rubric, plan


def prepared(tmp_path: Path):
    paths = synthetic_inputs(tmp_path)
    review = tmp_path / "review"
    prepare_review(*paths, review)
    return paths, review


def fixture_confirmation(review: Path) -> Path:
    decision = read_json(review / "owner_decision_pending.json")
    decision.update(status="OWNER_CONFIRMED", confirmed_at="2026-10-09T19:00:00+07:00",
                    owner_statement="Test-only owner attestation for local synthetic fixtures, not a real owner decision.",
                    model_id=helper["MODEL"], provider_id="openai-compatible:" + helper["MODEL"],
                    provider_endpoint=helper["ENDPOINT"], api_service_tier="UNPAID")
    for key in ("corpus_approved", "rubric_approved", "case003_context_accepted",
                "case012_diagnostic_only_accepted", "corpus_text_sharing_approved", "protocol_text_sharing_approved"):
        decision[key] = True
    path = review / "fixture_confirmation.json"
    path.write_bytes(encoded(decision))
    return path


def test_preparation_keeps_drafts_and_manual_blank_and_does_not_send_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKBENCH_LLM_KEY", "fixture-secret-never-sent")
    paths = synthetic_inputs(tmp_path)
    before = [path.read_bytes() for path in paths]
    review = tmp_path / "review"
    result = prepare_review(*paths, review)
    assert [path.read_bytes() for path in paths] == before
    assert result["status"] == "REVIEW_READY_PENDING_OWNER_AND_CREDENTIAL"
    assert result["approval_granted"] is False and result["freeze_created"] is False
    assert not list(review.glob("*.manifest.json"))
    assert read_json(review / "rubric.json")["status"] == "DRAFT_NOT_APPROVED"
    assert all(row["status"] == "PENDING" and not row["fields"] and not row["reviewer_ids"]
               for row in read_json(review / "manual_template_pending.json")["cases"])
    preview = read_json(review / "request_previews.json")
    assert len(preview) == 24 and all(row["provider_called"] is False for row in preview)
    diagnostic = next(row for row in preview if row["case_id"].endswith("012") and row["system_id"] == "llm_rag")
    assert not diagnostic["would_call_if_authorized"] and "body" not in diagnostic
    assert read_json(review / "comparison_policy_proposal.json")["max_provider_requests"] == 23
    for row in preview:
        if "body" in row:
            assert row["endpoint"] == helper["ENDPOINT"]
            body = row["body"]
            assert body["temperature"] == 0 and body["response_format"]["type"] == "json_schema"
            assert body["response_format"]["json_schema"]["schema"]["additionalProperties"] is False
            user = json.loads(body["messages"][1]["content"])
            assert set(user) == {"protocol_text", "approved_evidence"}
            assert all(set(chunk) == {"source_id", "citation", "chunk_id", "text"} for chunk in user["approved_evidence"])
    text = (review / "request_previews.json").read_text("utf-8")
    assert "fixture-secret-never-sent" not in text and "Authorization" not in text and "gold_fields" not in text
    verify_inventory(review, "review_inventory.json")


def test_pending_decision_cannot_freeze(tmp_path):
    _, review = prepared(tmp_path)
    target = tmp_path / "frozen"
    with pytest.raises(ValueError, match="actual single-owner"):
        freeze_review(review, review / "owner_decision_pending.json", target)
    assert not target.exists()


@pytest.mark.parametrize("key,value", [
    ("corpus_approved", False), ("rubric_approved", False), ("case003_context_accepted", False),
    ("case012_diagnostic_only_accepted", False), ("corpus_text_sharing_approved", False),
    ("protocol_text_sharing_approved", False), ("corpus_text_sharing_approved", 1),
    ("review_package_sha256", "0" * 64), ("rubric_sha256", "0" * 64),
    ("provider_endpoint", "https://example.invalid/chat/completions"),
    ("model_id", "another-model"), ("api_service_tier", "UNKNOWN"),
    ("confirmed_at", "2026-10-09T19:00:00"), ("independent_review_claim", True),
])
def test_freeze_requires_each_actual_decision_and_exact_binding(tmp_path, key, value):
    _, review = prepared(tmp_path)
    decision = fixture_confirmation(review)
    data = read_json(decision)
    data[key] = value
    decision.write_bytes(encoded(data))
    with pytest.raises(ValueError):
        freeze_review(review, decision, tmp_path / "frozen")
    assert not (tmp_path / "frozen").exists()


def test_inventory_drift_and_unknown_decision_fields_block_before_write(tmp_path):
    _, review = prepared(tmp_path)
    decision = fixture_confirmation(review)
    data = read_json(decision)
    data["extra_approval"] = True
    decision.write_bytes(encoded(data))
    with pytest.raises(ValueError, match="unsupported fields"):
        freeze_review(review, decision, tmp_path / "frozen")
    decision = fixture_confirmation(review)
    (review / "measurement_plan.md").write_text("Altered after review", encoding="utf-8")
    with pytest.raises(ValueError, match="bytes changed"):
        freeze_review(review, decision, tmp_path / "frozen")
    assert not (tmp_path / "frozen").exists()


def test_confirmed_fixture_freeze_reuses_manifest_and_loader_without_provider_or_overwrite(tmp_path, monkeypatch):
    paths, review = prepared(tmp_path)
    before = [path.read_bytes() for path in paths]
    decision = fixture_confirmation(review)

    def no_network(*args, **kwargs):
        raise AssertionError("Freeze must never call a provider")

    monkeypatch.setattr(intake, "urlopen", no_network)
    target = tmp_path / "frozen"
    result = freeze_review(review, decision, target)
    assert result["status"] == "FROZEN_OWNER_REVIEWED_DEMO" and result["provider_called"] is False
    assert [path.read_bytes() for path in paths] == before
    rubric = read_json(target / "reference_owner_reviewed.json")
    assert rubric["reviewer_ids"] == ["owner-le-tan-vi"]
    assert rubric["evaluation_mode"] == "OWNER_REVIEWED_DEMO" and rubric["independent_review_claim"] is False
    assert rubric["reviewed_at"] == read_json(decision)["confirmed_at"]
    assert (target / "owner_decision.json").read_bytes() == decision.read_bytes()
    inputs = prepare_inputs(target / paths[0].name, target / "reference_owner_reviewed.json",
                            target / "corpus.manifest.json", generation=True)
    worksheet = read_json(target / "manual_template_pending.json")
    assert worksheet["rubric_sha256"] == inputs["rubric_sha256"]
    assert all(row["status"] == "PENDING" and not row["reviewer_ids"] and row["elapsed_seconds"] is None
               for row in worksheet["cases"])
    verify_inventory(target, "freeze_inventory.json")
    before_inventory = (target / "freeze_inventory.json").read_bytes()
    with pytest.raises(FileExistsError):
        freeze_review(review, decision, target)
    assert (target / "freeze_inventory.json").read_bytes() == before_inventory


def test_original_case003_context_cannot_be_mislabeled_as_proposal(tmp_path):
    paths = synthetic_inputs(tmp_path)
    rubric = read_json(paths[1])
    for obj in (rubric["cases"][2]["gold_fields"], rubric["cases"][2]["expected_output"]["proposed_fields"]):
        obj["context"]["feeding_state"] = "not specified"
    paths[1].write_bytes(encoded(rubric))
    with pytest.raises(ValueError, match="case-003"):
        prepare_review(*paths, tmp_path / "review")
    assert not (tmp_path / "review").exists()
