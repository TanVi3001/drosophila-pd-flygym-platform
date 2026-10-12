from __future__ import annotations

import copy

import pytest

from drosophila_pd.ai_v2.evaluation import evaluate_assistant_bundle


def _bundle():
    cases = [
        {
            "case_id": "Q_DEV_001",
            "required_fields": ["assay", "primary_metric"],
            "gold_fields": {"assay": "sensory", "primary_metric": "neural_rate"},
            "gold_missing_fields": ["readout_identity"],
            "gold_evidence_chunk_ids": ["CHUNK_A"],
            "gold_citations": [{"source_id": "SRC_A", "chunk_id": "CHUNK_A"}],
        },
        {
            "case_id": "Q_DEV_002",
            "required_fields": ["assay", "primary_metric"],
            "gold_fields": {"assay": "neural", "primary_metric": "mn9_rate"},
            "gold_missing_fields": [],
            "gold_evidence_chunk_ids": ["CHUNK_B"],
            "gold_citations": [{"source_id": "SRC_B", "chunk_id": "CHUNK_B"}],
        },
    ]
    def outputs():
        return [
            {
                "case_id": "Q_DEV_001", "status": "COMPLETED", "schema_valid": True,
                "retrieved_chunk_ids": ["CHUNK_A"],
                "citations": [{"source_id": "SRC_A", "chunk_id": "CHUNK_A"}],
                "fields": {"assay": "sensory", "primary_metric": "neural_rate"},
                "missing_fields": ["readout_identity"],
                "claim_reviews": [{"support_status": "SUPPORTED", "reviewer_ids": ["human-1"]}],
            },
            {
                "case_id": "Q_DEV_002", "status": "ABSTAINED", "schema_valid": True,
                "retrieved_chunk_ids": [], "citations": [], "fields": {},
                "missing_fields": ["assay", "primary_metric"],
                "claim_reviews": [{"support_status": "UNSUPPORTED", "reviewer_ids": ["human-2"]}],
            },
        ]
    return {
        "schema_version": "ai-v2-assistant-evaluation-input-1",
        "evaluation_mode": "SYNTHETIC_TEST_ONLY",
        "synthetic_fixture": True,
        "partition": "DEVELOPMENT",
        "cases": cases,
        "systems": [
            {"system_id": system_id, "outputs": outputs()}
            for system_id in ("manual_template", "llm_no_retrieval", "llm_rag")
        ],
    }


def _approved_bundle():
    bundle = _bundle()
    bundle.update({
        "evaluation_mode": "APPROVED_DEVELOPMENT", "synthetic_fixture": False,
        "corpus_status": "APPROVED", "rubric_status": "APPROVED",
        "corpus_sha256": "a" * 64, "rubric_sha256": "b" * 64,
        "evaluation_protocol_sha256": "c" * 64, "provider_policy_approved": True,
        "retrieval_k": 5, "reviewer_ids": ["reviewer-1", "reviewer-2"],
    })
    for system in bundle["systems"]:
        if system["system_id"] != "manual_template":
            system.update({"provider_id": "approved-provider", "model_id": "approved-model", "prompt_version": "prompt-v1"})
    return bundle


def _owner_demo_bundle():
    bundle = _approved_bundle()
    bundle.update({
        "evaluation_mode": "OWNER_REVIEWED_DEMO",
        "owner_demo": True,
        "independent_review_claim": False,
        "reviewer_ids": ["owner-v"],
    })
    for system in bundle["systems"]:
        for output in system["outputs"]:
            for claim in output["claim_reviews"]:
                claim["reviewer_ids"] = ["owner-v"]
    return bundle


def test_synthetic_evaluator_emits_transparent_denominators_and_claim_label():
    result = evaluate_assistant_bundle(_bundle(), k=5)

    assert result["evaluation_status"] == "SYNTHETIC_TEST_ONLY"
    assert result["partition"] == "DEVELOPMENT"
    assert result["case_count"] == 2
    rag = next(item for item in result["systems"] if item["system_id"] == "llm_rag")
    assert rag["coverage"] == 0.5
    assert rag["recall_at_k"] == 0.5
    assert rag["citation_precision"] == 1.0
    assert rag["field_denominator"] == 4
    assert rag["claim_review"]["unsupported_claim_rate"] == 0.5
    assert result["scoring_policy"]["llm_as_judge"] is False
    assert rag["precision_at_k_case_denominator"] == 2
    assert rag["precision_returned_hit_denominator_sum"] == 1
    assert next(item for item in result["systems"] if item["system_id"] == "llm_no_retrieval")["precision_at_k"] is None


def test_schema_validity_is_separate_from_field_correctness():
    correct = evaluate_assistant_bundle(_bundle(), k=5)
    changed = _bundle()
    rag_outputs = next(system for system in changed["systems"] if system["system_id"] == "llm_rag")["outputs"]
    rag_outputs[0]["fields"]["assay"] = "wrong but still a string"
    wrong_content = evaluate_assistant_bundle(changed, k=5)
    correct_rag = next(row for row in correct["systems"] if row["system_id"] == "llm_rag")
    wrong_rag = next(row for row in wrong_content["systems"] if row["system_id"] == "llm_rag")
    assert wrong_rag["schema_valid_rate"] == correct_rag["schema_valid_rate"]
    assert wrong_rag["required_field_exact_accuracy"] < correct_rag["required_field_exact_accuracy"]

    malformed = copy.deepcopy(changed)
    rag_outputs = next(system for system in malformed["systems"] if system["system_id"] == "llm_rag")["outputs"]
    rag_outputs[0]["schema_valid"] = False
    malformed_rag = next(row for row in evaluate_assistant_bundle(malformed, k=5)["systems"]
                         if row["system_id"] == "llm_rag")
    assert malformed_rag["schema_valid_rate"] < wrong_rag["schema_valid_rate"]


def test_errors_abstentions_and_unobserved_raw_schema_remain_in_report():
    bundle = _bundle()
    for system in bundle["systems"]:
        system["outputs"][0].update(status="ERROR", schema_valid=None,
                                    processed_schema_status="NOT_PRODUCED",
                                    provider_attempted=True, raw_schema_status="NO_RESPONSE")
        system["outputs"][1].update(status="ABSTAINED", schema_valid=True,
                                    processed_schema_status="VALID",
                                    provider_attempted=False, raw_schema_status="NOT_CALLED")
    result = evaluate_assistant_bundle(bundle, k=5)
    rag = next(row for row in result["systems"] if row["system_id"] == "llm_rag")
    assert rag["status_counts"] == {"ERROR": 1, "ABSTAINED": 1}
    assert rag["error_count"] == 1 and rag["abstained_count"] == 1
    assert rag["schema_validity"]["raw_output"]["status_counts"] == {"NO_RESPONSE": 1, "NOT_CALLED": 1}
    assert rag["schema_validity"]["raw_output"]["response_denominator"] == 0
    assert rag["schema_validity"]["processed_draft"]["status_counts"] == {"NOT_PRODUCED": 1, "VALID": 1}


def test_evaluator_refuses_heldout_or_unapproved_real_bundle():
    heldout = _bundle()
    heldout["partition"] = "HELDOUT"
    with pytest.raises(ValueError, match="DEVELOPMENT only"):
        evaluate_assistant_bundle(heldout)

    real = _bundle()
    real.update({
        "evaluation_mode": "APPROVED_DEVELOPMENT",
        "synthetic_fixture": False,
        "corpus_status": "APPROVED",
        "rubric_status": "APPROVED",
        "corpus_sha256": "a" * 64,
        "rubric_sha256": "b" * 64,
        "evaluation_protocol_sha256": "c" * 64,
        "provider_policy_approved": False,
        "retrieval_k": 5,
        "reviewer_ids": ["reviewer-1", "reviewer-2"],
    })
    with pytest.raises(ValueError, match="provider/privacy"):
        evaluate_assistant_bundle(real)


def test_real_mode_requires_two_reviewers_and_three_comparators():
    real = _bundle()
    real.update({
        "evaluation_mode": "APPROVED_DEVELOPMENT", "synthetic_fixture": False,
        "corpus_status": "APPROVED", "rubric_status": "APPROVED",
        "corpus_sha256": "a" * 64, "rubric_sha256": "b" * 64,
        "evaluation_protocol_sha256": "c" * 64, "provider_policy_approved": True,
        "retrieval_k": 5,
        "reviewer_ids": ["reviewer-1", "reviewer-1"],
    })
    with pytest.raises(ValueError, match="two distinct"):
        evaluate_assistant_bundle(real)
    real["reviewer_ids"] = ["reviewer-1", "reviewer-2"]
    real["systems"] = real["systems"][:1]
    with pytest.raises(ValueError, match="must include"):
        evaluate_assistant_bundle(real)


def test_approved_development_contract_path_scores_only_after_all_freezes():
    result = evaluate_assistant_bundle(_approved_bundle(), k=5)

    assert result["evaluation_status"] == "MEASURED_APPROVED_DEVELOPMENT"
    assert result["case_count"] == 2
    assert result["retrieval_k"] == 5


def test_approved_development_rejects_k_drift_and_secret_like_provider_metadata():
    bundle = _approved_bundle()
    bundle["retrieval_k"] = 10
    with pytest.raises(ValueError, match="differs from the frozen"):
        evaluate_assistant_bundle(bundle, k=5)
    bundle = _approved_bundle()
    bundle["systems"][1]["provider_id"] = "Bearer sk-example-secret"
    with pytest.raises(ValueError, match="contains a secret"):
        evaluate_assistant_bundle(bundle, k=5)


def test_owner_reviewed_demo_computes_metrics_but_is_explicitly_non_independent():
    result = evaluate_assistant_bundle(_owner_demo_bundle(), k=5)

    assert result["evaluation_status"] == "MEASURED_OWNER_REVIEWED_DEMO_NOT_INDEPENDENT"
    assert result["reviewer_count"] == 1
    assert result["review_claim"] == "single owner reviewer; not independent"
    assert result["case_count"] == 2
    assert len(result["systems"]) == 3


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"reviewer_ids": []}, "exactly one named reviewer"),
        ({"reviewer_ids": ["owner-v", "second-v"]}, "exactly one named reviewer"),
        ({"independent_review_claim": True}, "independent_review_claim=false"),
        ({"owner_demo": False}, "owner_demo=true"),
    ],
)
def test_owner_demo_requires_one_reviewer_and_non_independent_label(change, message):
    bundle = _owner_demo_bundle()
    bundle.update(change)

    with pytest.raises(ValueError, match=message):
        evaluate_assistant_bundle(bundle, k=5)


def test_owner_demo_claim_annotations_must_name_only_the_owner():
    bundle = _owner_demo_bundle()
    bundle["systems"][0]["outputs"][0]["claim_reviews"][0]["reviewer_ids"] = ["other-reviewer"]

    with pytest.raises(ValueError, match="must name only"):
        evaluate_assistant_bundle(bundle, k=5)


def test_predictions_may_not_contain_label_or_outcome_fields():
    bundle = _bundle()
    contaminated = copy.deepcopy(bundle)
    contaminated["systems"][0]["outputs"][0]["outcome"] = "positive"
    with pytest.raises(ValueError, match="outcome/label"):
        evaluate_assistant_bundle(contaminated)
