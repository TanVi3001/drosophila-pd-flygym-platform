from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from drosophila_pd.ai_v2.comparison import (
    _gold_set_precision_at_k, encoded, load_manual, manual_template, prepare_inputs,
    raw_output_schema_valid, read_json, run_comparison, score_comparison, verify_run,
)


def pack(root, *, approved=True, diagnostic_second=False):
    folder = root / "inputs"
    folder.mkdir()
    corpus = folder / "corpus.jsonl"
    chunk = {"source_id": "FIXTURE", "chunk_id": "fixture:1", "citation": "Synthetic guide",
             "text": "fixture protocol metric definitions", "provenance": "synthetic software test",
             "access_class": "DEVELOPMENT_INPUT"}
    corpus.write_bytes((json.dumps(chunk) + "\n").encode())
    sha = hashlib.sha256(corpus.read_bytes()).hexdigest()
    manifest = folder / "manifest.json"
    manifest.write_bytes(encoded({"schema_version": "approved-evidence-corpus-1", "corpus_id": "synthetic-test",
        "corpus_file": "corpus.jsonl", "corpus_sha256": sha, "approved_source_ids": ["FIXTURE"],
        "denied_source_ids": [], "partition": "DEVELOPMENT", "owner_approved": True, "outcome_free": True,
        "reviewed_by": ["owner-test"], "reviewed_at": "2026-10-07T14:00:00+07:00",
        "provider_sharing_approved": approved, "protocol_text_sharing_approved": approved,
        "approved_provider_id": "stub" if approved else "",
        "approved_provider_endpoint": "http://localhost:9000/chat/completions" if approved else ""}))
    required = ["hypothesis", "falsifiable_prediction", "assay", "primary_metric"]
    fields = dict(zip(required, ["fixture h", "fixture p", "fixture_assay", "fixture_metric"]))
    rubric = folder / "rubric.json"
    rubric.write_bytes(encoded({"schema_version": "ai-v2-assistant-reference-reviewed-1" if approved else "ai-v2-assistant-reference-draft-1",
        "status": "APPROVED" if approved else "DRAFT_NOT_APPROVED", "partition": "DEVELOPMENT",
        "task_type": "PROTOCOL_DRAFT_EXTRACTION", "synthetic_fixture": True,
        "reviewer_ids": ["owner-test"] if approved else [], "corpus_sha256": sha,
        "privacy_decision": {"status": "APPROVED" if approved else "NOT_DECIDED",
                             "corpus_text_sharing_approved": approved, "protocol_text_sharing_approved": approved,
                             "provider_id": "stub" if approved else "", "provider_endpoint": "http://localhost:9000/chat/completions" if approved else ""},
        "evaluation_protocol_draft": {"retrieval_k": 5},
        "cases": [
            {"case_id": "CASE_001", "protocol_text": "fixture protocol metric", "required_fields": required,
             "gold_fields": fields, "gold_missing_fields": [], "gold_evidence_chunk_ids": ["fixture:1"],
             "gold_citations": [{"source_id": "FIXTURE", "chunk_id": "fixture:1"}]},
            {"case_id": "CASE_002", "protocol_text": "zzqnonce", "category": "no_lexical_evidence_probe" if diagnostic_second else "other_fixture_case", "required_fields": required,
             "gold_fields": {key: None for key in required}, "gold_missing_fields": required,
             "gold_evidence_chunk_ids": [], "gold_citations": []}]}))
    return corpus, rubric, manifest, fields


class Provider:
    provider_id = "stub"
    model = "stub-model-not-gemini"
    endpoint = "http://localhost:9000/chat/completions"

    def __init__(self, fields):
        self.fields = fields
        self.calls = []
        self.modify = lambda text, evidence, output: output

    def extract_with_evidence(self, text, *, evidence):
        self.calls.append((text, copy.deepcopy(evidence)))
        value = {**self.fields, "candidate_suggestions": [], "control_suggestions": [],
                 "missing_fields": [], "citations": [{"source_id": "FIXTURE", "chunk_id": "fixture:1"}]}
        return self.modify(text, evidence, value)


def setup(root, *, approved=True, diagnostic_second=False):
    paths = pack(root, approved=approved, diagnostic_second=diagnostic_second)
    inputs = prepare_inputs(*paths[:3], generation=approved)
    return paths, inputs, Provider(paths[3])


@pytest.mark.parametrize("missing", ["candidate_suggestions", "control_suggestions", "citations", "missing_fields"])
def test_raw_contract_rejects_missing_provider_required_array(missing):
    value = {"candidate_suggestions": [], "control_suggestions": [], "citations": [], "missing_fields": []}
    assert raw_output_schema_valid(value)
    del value[missing]
    assert not raw_output_schema_valid(value)


def test_missing_raw_array_remains_invalid_despite_valid_processed_draft(tmp_path):
    paths, inputs, provider = setup(tmp_path, diagnostic_second=True)
    provider.modify = lambda text, evidence, output: {k: v for k, v in output.items() if k != "control_suggestions"}
    result = run_comparison(inputs, paths[2], provider, tmp_path / "run", test_only=True)
    rag = next(x for x in result["systems"] if x["system_id"] == "llm_rag")
    assert rag["schema_validity"]["raw_output_schema"]["valid_count"] == 0
    assert rag["schema_validity"]["processed_draft_schema"]["valid_count"] == 1


def records(root):
    return read_json(root / "case_outputs.json")["records"]


def test_blank_template_contains_no_gold_answers_or_fabricated_review(tmp_path):
    _, inputs, _ = setup(tmp_path, approved=False)
    template = manual_template(inputs)
    assert all(r["status"] == "PENDING" and not r["fields"] and not r["reviewer_ids"] for r in template["cases"])
    assert "fixture h" not in json.dumps(template)
    assert "gold_fields" not in json.dumps(template)
    assert inputs["rubric"]["status"] == "DRAFT_NOT_APPROVED"


def test_three_arms_keep_all_cases_and_use_same_method_without_gold(tmp_path):
    paths, inputs, provider = setup(tmp_path)
    result = run_comparison(inputs, paths[2], provider, tmp_path / "run", test_only=True)
    assert len(records(tmp_path / "run")) == 6
    assert len(provider.calls) == 3  # RAG nonce abstains before a provider request.
    assert all(text in {"fixture protocol metric", "zzqnonce"} for text, _ in provider.calls)
    assert "gold_fields" not in json.dumps(provider.calls)
    assert sum(bool(evidence) for _, evidence in provider.calls) == 1
    assert result["status"] == "SOFTWARE_TEST_STUB_RESULTS"
    by_system = {s["system_id"]: s for s in result["systems"]}
    assert by_system["llm_rag"]["retrieval"]["recall_at_5"] == 1
    assert by_system["llm_rag"]["schema_validity"]["raw_output_schema"]["valid_rate_among_responses"] == 1
    assert by_system["llm_rag"]["schema_validity"]["processed_draft_schema"]["valid_rate_among_produced"] == 1
    assert by_system["llm_rag"]["schema_validity"]["raw_output_schema"]["status_counts"]["NOT_CALLED"] == 1
    assert by_system["llm_no_retrieval"]["retrieval"]["recall_at_5"] is None
    assert by_system["manual_template"]["measurement_status"] == "NOT_MEASURED"
    assert by_system["manual_template"]["field_exact"]["accuracy"] is None
    assert not result["comparison_complete"]
    assert all(s["claim_review"]["unsupported_claim_rate"] is None for s in result["systems"])
    assert not list(paths[0].parent.glob("*log*"))
    config, output, sha = verify_run(tmp_path / "run", inputs)
    assert config["test_only"] is True and len(output) == 6 and len(sha) == 64


def test_real_manual_outputs_are_imported_not_generated(tmp_path):
    paths, inputs, provider = setup(tmp_path)
    manual = manual_template(inputs)
    manual["cases"][0].update(status="COMPLETED", fields=paths[3], reviewer_ids=["owner-test"], elapsed_seconds=40)
    manual["cases"][1].update(status="ABSTAINED", missing_fields=list(paths[3]), reviewer_ids=["owner-test"], elapsed_seconds=10)
    worksheet = tmp_path / "manual" / "filled.json"
    worksheet.parent.mkdir()
    worksheet.write_bytes(encoded(manual))
    assert set(load_manual(worksheet, inputs)) == {"CASE_001", "CASE_002"}
    result = run_comparison(inputs, paths[2], provider, tmp_path / "run", manual_path=worksheet, test_only=True)
    s = next(x for x in result["systems"] if x["system_id"] == "manual_template")
    assert s["field_exact"]["accuracy"] == 1
    assert s["missing_fields"]["f1"] == 1
    assert s["latency"]["mean_seconds"] == 25
    assert s["latency"]["source"] == "human_self_reported"
    assert result["comparison_complete"]


def test_provider_timeout_retains_retrieval_and_is_not_abstention(tmp_path):
    paths, inputs, provider = setup(tmp_path)

    def broken(text, evidence, value):
        if evidence:
            raise TimeoutError("secret-value-must-not-appear")
        return value

    provider.modify = broken
    result = run_comparison(inputs, paths[2], provider, tmp_path / "run", test_only=True)
    rag = next(s for s in result["systems"] if s["system_id"] == "llm_rag")
    assert rag["status_counts"] == {"ERROR": 1, "ABSTAINED": 1}
    assert rag["error_rate"] == .5 and rag["field_exact"]["accuracy"] == .5
    assert rag["field_exact"]["non_null_accuracy"] == 0
    assert rag["retrieval"]["recall_at_5"] == 1
    row = next(r for r in records(tmp_path / "run") if r["system_id"] == "llm_rag" and r["case_id"] == "CASE_001")
    assert row["provider_called"] is None and row["retrieved_evidence"]
    assert rag["schema_validity"]["raw_output_schema"]["status_counts"]["NO_RESPONSE"] == 1
    assert rag["status_counts"]["ERROR"] == 1 and rag["status_counts"]["ABSTAINED"] == 1
    assert "secret-value" not in json.dumps(records(tmp_path / "run"))
    assert len(provider.calls) == 3


def test_raw_invalid_citation_is_not_hidden_by_runtime_guardrail(tmp_path):
    paths, inputs, provider = setup(tmp_path)

    def add_bad_citation(text, evidence, value):
        value["citations"].append({"source_id": "INVENTED", "chunk_id": "invented:1"})
        return value

    provider.modify = add_bad_citation
    result = run_comparison(inputs, paths[2], provider, tmp_path / "run", test_only=True)
    rag = next(s for s in result["systems"] if s["system_id"] == "llm_rag")
    assert rag["citations"]["raw_count"] == 2
    assert rag["citations"]["raw_source_precision"] == .5
    assert rag["citations"]["accepted_count"] == 1
    assert rag["citations"]["accepted_source_precision"] == 1


def test_human_support_annotations_are_bound_and_have_explicit_coverage(tmp_path):
    paths, inputs, provider = setup(tmp_path)
    run_comparison(inputs, paths[2], provider, tmp_path / "run", test_only=True)
    config, output, sha = verify_run(tmp_path / "run", inputs)
    annotations = read_json(tmp_path / "run" / "claim_review_template.json")
    for row in annotations["reviews"]:
        row.update(support_status="SUPPORTED", reviewer_ids=["owner-test"])
    annotations["reviews"][0]["support_status"] = "UNSUPPORTED"
    result = score_comparison(inputs, output, config, sha, annotations)
    row = next(s for s in result["systems"] if s["system_id"] == annotations["reviews"][0]["system_id"])
    assert row["claim_review"]["review_coverage"] == 1
    assert row["claim_review"]["unsupported_claim_rate"] > 0
    assert not result["independent_review_claim"]


@pytest.mark.parametrize("mutation", ["hash", "text", "reviewer", "duplicate"])
def test_annotation_forgery_or_mismatch_is_rejected(tmp_path, mutation):
    paths, inputs, provider = setup(tmp_path)
    run_comparison(inputs, paths[2], provider, tmp_path / "run", test_only=True)
    config, output, sha = verify_run(tmp_path / "run", inputs)
    annotations = read_json(tmp_path / "run" / "claim_review_template.json")
    if mutation == "hash":
        annotations["case_outputs_sha256"] = "a" * 64
    elif mutation == "text":
        annotations["reviews"][0]["text"] = "changed output"
    elif mutation == "reviewer":
        annotations["reviews"][0].update(support_status="SUPPORTED", reviewer_ids=["invented-owner"])
    else:
        annotations["reviews"].append(annotations["reviews"][0])
    with pytest.raises(ValueError):
        score_comparison(inputs, output, config, sha, annotations)


@pytest.mark.parametrize("violation", ["wrong_provider", "existing_output", "protected_output", "draft_reference"])
def test_preflight_blocks_before_generation(tmp_path, violation):
    paths, inputs, provider = setup(tmp_path, approved=violation != "draft_reference")
    target = tmp_path / "run"
    if violation == "wrong_provider":
        provider.endpoint = "https://other.example/chat/completions"
    elif violation == "existing_output":
        target.mkdir()
    elif violation == "protected_output":
        target = paths[0].parent / "run"
    with pytest.raises((ValueError, FileExistsError)):
        run_comparison(inputs, paths[2], provider, target, test_only=True)
    assert provider.calls == []


@pytest.mark.parametrize("mutation", ["case_deleted", "input_changed", "k_changed", "partition_changed"])
def test_scoring_refuses_dropped_failures_and_scope_changes(tmp_path, mutation):
    paths, inputs, provider = setup(tmp_path)
    run_comparison(inputs, paths[2], provider, tmp_path / "run", test_only=True)
    config, output, sha = verify_run(tmp_path / "run", inputs)
    if mutation == "case_deleted":
        output.pop()
    elif mutation == "input_changed":
        output[0]["input_sha256"] = "a" * 64
    elif mutation == "k_changed":
        config["retrieval_k"] = 3
    else:
        config["partition"] = "HELD_OUT"
    with pytest.raises(ValueError):
        score_comparison(inputs, output, config, sha)


def test_integrity_verifier_rejects_tampered_outputs(tmp_path):
    paths, inputs, provider = setup(tmp_path)
    run_comparison(inputs, paths[2], provider, tmp_path / "run", test_only=True)
    file = tmp_path / "run" / "case_outputs.json"
    file.write_bytes(file.read_bytes() + b" ")
    with pytest.raises(ValueError, match="integrity"):
        verify_run(tmp_path / "run", inputs)


def test_provider_identity_drift_stops_remaining_requests(tmp_path):
    paths, inputs, provider = setup(tmp_path)

    def drift(text, evidence, value):
        provider.model = "different-model"
        return value

    provider.modify = drift
    result = run_comparison(inputs, paths[2], provider, tmp_path / "run", test_only=True)
    assert len(provider.calls) == 1
    assert sum(s["status_counts"].get("ERROR", 0) for s in result["systems"]) == 1
    assert not result["comparison_complete"]


@pytest.mark.parametrize("violation", ["negative_time", "bool_time", "input", "reviewer"])
def test_manual_worksheet_validation(tmp_path, violation):
    _, inputs, _ = setup(tmp_path)
    manual = manual_template(inputs)
    row = manual["cases"][0]
    if violation == "negative_time":
        row["elapsed_seconds"] = -1
    elif violation == "bool_time":
        row["elapsed_seconds"] = True
    elif violation == "input":
        row["protocol_text"] = "changed"
    else:
        row.update(status="COMPLETED", reviewer_ids=[])
    path = tmp_path / "manual.json"
    path.write_bytes(encoded(manual))
    with pytest.raises(ValueError):
        load_manual(path, inputs)


def test_cli_prepares_without_provider_and_offline_report_needs_no_key(tmp_path):
    paths, inputs, provider = setup(tmp_path)
    script = Path(__file__).resolve().parents[1] / "scripts/compare_ai_v2_protocols.py"
    common = [sys.executable, str(script), "--corpus", str(paths[0]), "--rubric", str(paths[1])]
    result = subprocess.run([*common, "--dry-run"], text=True, capture_output=True)
    assert result.returncode == 0 and "STRUCTURE_ONLY_NO_REQUESTS" in result.stdout
    run_comparison(inputs, paths[2], provider, tmp_path / "run", test_only=True)
    result = subprocess.run([*common, "--report-only", str(tmp_path / "run"), "--output-dir", str(tmp_path / "report")],
                            text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert '"provider_called": false' in result.stdout
    assert (tmp_path / "report/report_manifest.json").exists()


def test_validation_paths_are_rejected_before_read(tmp_path):
    with pytest.raises(ValueError, match="validation"):
        read_json(tmp_path / "held-out.json")


def test_malformed_nested_citation_is_counted_wrong_not_crashing_report(tmp_path):
    paths, inputs, provider = setup(tmp_path)

    def malformed(text, evidence, output):
        output["citations"] = [{"source_id": ["invalid"], "chunk_id": {"invalid": True}}]
        return output

    provider.modify = malformed
    result = run_comparison(inputs, paths[2], provider, tmp_path / "run", test_only=True)
    assert all(s["citations"]["raw_source_precision"] == 0 for s in result["systems"] if s["system_id"] != "manual_template")


def test_provider_secrets_are_not_preserved_even_if_echoed(tmp_path):
    paths, inputs, provider = setup(tmp_path)

    def echo(text, evidence, output):
        output["hypothesis"] = "echo secret-string"
        output["api_key"] = "secret-string"
        return output

    provider.modify = echo
    run_comparison(inputs, paths[2], provider, tmp_path / "run", secrets=("secret-string",), test_only=True)
    assert "secret-string" not in json.dumps(records(tmp_path / "run"))
    assert "[REDACTED]" in json.dumps(records(tmp_path / "run"))


def test_runtime_missing_field_repair_is_not_counted_as_model_declaration(tmp_path):
    paths, inputs, provider = setup(tmp_path)

    def missing(text, evidence, value):
        value.pop("hypothesis")
        value["missing_fields"] = []  # Model fails to flag its missing hypothesis.
        return value

    provider.modify = missing
    result = run_comparison(inputs, paths[2], provider, tmp_path / "run", test_only=True)
    rag = next(s for s in result["systems"] if s["system_id"] == "llm_rag")
    row = next(r for r in records(tmp_path / "run") if r["system_id"] == "llm_rag" and r["case_id"] == "CASE_001")
    assert "hypothesis" in row["missing_fields"]
    assert row["raw_output"]["missing_fields"] == []
    assert rag["raw_missing_declaration"]["attempted_cases"] == 1


def test_exact_missing_placeholder_replay_keeps_raw_claims_citations_and_diagnostic_separate(tmp_path):
    paths, inputs, provider = setup(tmp_path, diagnostic_second=True)

    def exact_placeholder(_text, _evidence, output):
        output["hypothesis"] = "missing"
        output["missing_fields"] = ["hypothesis"]
        return output

    provider.modify = exact_placeholder
    result = run_comparison(inputs, paths[2], provider, tmp_path / "run", test_only=True)
    rows = records(tmp_path / "run")
    rag = next(row for row in rows if row["system_id"] == "llm_rag" and row["case_id"] == "CASE_001")

    assert rag["raw_output"]["hypothesis"] == "missing"
    assert rag["raw_output"]["missing_fields"] == ["hypothesis"]
    assert rag["raw_response"] == rag["raw_output"]
    assert "hypothesis" not in rag["fields"]
    assert "hypothesis" in rag["missing_fields"]
    assert rag["citations"] == [{
        "source_id": "FIXTURE",
        "chunk_id": "fixture:1",
        "citation": "Synthetic guide",
        "locator": "fixture:1",
    }]
    assert rag["processed_schema_status"] == "VALID"

    diagnostic = next(item for item in result["lexical_no_hit_diagnostics"]
                      if item["case_id"] == "CASE_002")
    diagnostic_rag = next(item for item in diagnostic["systems"] if item["system_id"] == "llm_rag")
    diagnostic_no_rag = next(item for item in diagnostic["systems"]
                             if item["system_id"] == "llm_no_retrieval")
    assert result["case_count"] == 1
    assert result["diagnostic_case_count"] == 1
    assert diagnostic_rag["status"] == "ABSTAINED"
    assert diagnostic_rag["provider_called"] is False
    assert diagnostic_no_rag["provider_called"] is True


@pytest.mark.parametrize(
    ("retrieved", "gold", "expected"),
    [
        (["a", "b", "c"], ["a", "b"], 2 / 3),
        (["a", "unjudged"], ["a", "b"], 0.5),
        (["a"], ["a", "b"], 1.0),  # fewer than k: denominator is one actual hit
        ([], ["a"], 0.0),
        (["a"], [], None),
    ],
)
def test_gold_set_precision_at_5_uses_actual_hits_and_empty_gold_is_na(retrieved, gold, expected):
    assert _gold_set_precision_at_k(retrieved, gold, k=5) == expected


def test_raw_output_schema_and_processed_schema_are_independent_of_answer_accuracy(tmp_path):
    paths, inputs, provider = setup(tmp_path)
    correct = run_comparison(inputs, paths[2], provider, tmp_path / "correct", test_only=True)
    correct_rag = next(item for item in correct["systems"] if item["system_id"] == "llm_rag")

    def wrong_but_well_formed(text, evidence, output):
        output["hypothesis"] = "plausible but incorrect"
        return output

    provider.modify = wrong_but_well_formed
    result = run_comparison(inputs, paths[2], provider, tmp_path / "valid-wrong", test_only=True)
    rag = next(item for item in result["systems"] if item["system_id"] == "llm_rag")
    assert rag["schema_validity"]["raw_output_schema"]["valid_rate_among_responses"] == 1
    assert rag["schema_validity"]["processed_draft_schema"]["valid_rate_among_produced"] == 1
    assert rag["field_exact"]["accuracy"] < correct_rag["field_exact"]["accuracy"]

    def malformed_raw_shape(text, evidence, output):
        output["hypothesis"] = 123  # Sanitizer drops this; raw response must still fail schema.
        return output

    (tmp_path / "second").mkdir()
    _, _, provider2 = setup(tmp_path / "second")
    provider2.modify = malformed_raw_shape
    malformed = run_comparison(inputs, paths[2], provider2, tmp_path / "malformed", test_only=True)
    rag_bad = next(item for item in malformed["systems"] if item["system_id"] == "llm_rag")
    assert rag_bad["schema_validity"]["raw_output_schema"]["valid_count"] == 0
    assert rag_bad["schema_validity"]["raw_output_schema"]["response_denominator"] == 1
    assert rag_bad["schema_validity"]["processed_draft_schema"]["valid_rate_among_produced"] == 1
    raw_row = next(row for row in records(tmp_path / "malformed")
                   if row["system_id"] == "llm_rag" and row["case_id"] == "CASE_001")
    assert raw_row["raw_response"]["hypothesis"] == 123
    assert raw_row["raw_schema_status"] == "INVALID"


def test_raw_json_duplicate_keys_fail_schema_even_if_parser_normalizes_them():
    assert not raw_output_schema_valid('{"hypothesis":"first","hypothesis":"second"}')


def test_case_012_is_retained_but_cannot_change_11_case_quality_aggregate(tmp_path):
    paths, inputs, provider = setup(tmp_path, diagnostic_second=True)
    baseline = run_comparison(inputs, paths[2], provider, tmp_path / "run", test_only=True)
    config, output, sha = verify_run(tmp_path / "run", inputs)
    assert baseline["case_count"] == 1
    assert baseline["artifact_case_count"] == 2
    assert baseline["diagnostic_case_count"] == 1
    rag_diag = baseline["lexical_no_hit_diagnostics"][0]["systems"]
    rag_diag = next(row for row in rag_diag if row["system_id"] == "llm_rag")
    assert rag_diag["status"] == "ABSTAINED"
    assert rag_diag["provider_attempted"] is False
    assert rag_diag["raw_schema_status"] == "NOT_CALLED"

    changed = copy.deepcopy(output)
    for row in changed:
        if row["case_id"] == "CASE_002":
            row.update(status="ERROR", provider_attempted=True, provider_called=None,
                       raw_schema_status="NO_RESPONSE", processed_schema_status="NOT_PRODUCED")
    after = score_comparison(inputs, changed, config, sha)
    for before_system, after_system in zip(baseline["systems"], after["systems"]):
        assert before_system["status_counts"] == after_system["status_counts"]
        assert before_system["field_exact"] == after_system["field_exact"]
        assert before_system["completion_rate"] == after_system["completion_rate"]
        assert before_system["retrieval"] == after_system["retrieval"]
    assert after["lexical_no_hit_diagnostics"][0]["systems"][0]["status"] == "ERROR"
    assert after["artifact_case_count"] == 2 and after["case_count"] == 1


def test_manual_baseline_does_not_need_a_case_012_answer(tmp_path):
    paths, inputs, provider = setup(tmp_path, diagnostic_second=True)
    manual = manual_template(inputs)
    manual["cases"][0].update(status="COMPLETED", fields=paths[3], reviewer_ids=["owner-test"], elapsed_seconds=20)
    manual_path = tmp_path / "manual" / "filled.json"
    manual_path.parent.mkdir()
    manual_path.write_bytes(encoded(manual))
    result = run_comparison(inputs, paths[2], provider, tmp_path / "run", manual_path=manual_path, test_only=True)
    manifest = read_json(tmp_path / "run" / "run_manifest.json")
    assert result["comparison_complete"] is True
    assert manifest["status"] == "COMPLETE"
    assert manifest["required_output_count"] == 5  # three protocol rows plus two model diagnostic rows
    assert manifest["non_required_output_count"] == 1  # retained manual case 012, deliberately pending
    assert next(row for row in records(tmp_path / "run")
                if row["system_id"] == "manual_template" and row["case_id"] == "CASE_002")["status"] == "NOT_RUN"


def test_precision_denominators_and_empty_gold_are_reported_explicitly(tmp_path):
    paths, inputs, provider = setup(tmp_path, diagnostic_second=True)
    result = run_comparison(inputs, paths[2], provider, tmp_path / "run", test_only=True)
    rag = next(item for item in result["systems"] if item["system_id"] == "llm_rag")
    metric = rag["retrieval"]
    assert metric["precision_at_5"] == 1
    assert metric["precision_case_denominator"] == 1
    assert metric["precision_returned_hit_denominator_sum"] == 1
    assert metric["precision_relevant_hit_numerator_sum"] == 1
    assert metric["empty_gold_cases"] == 0  # case 012 is diagnostic, not a scored extraction case
    nonrag = next(item for item in result["systems"] if item["system_id"] == "llm_no_retrieval")
    assert nonrag["retrieval"]["precision_at_5"] is None
