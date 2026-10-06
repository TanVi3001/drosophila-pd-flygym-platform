from __future__ import annotations

import copy

import pytest

from drosophila_pd.workbench.v2_evaluation import (
    EVALUATION_SCHEMA,
    EvaluationContractError,
    evaluate_ai_v2_bundle,
)


def _case_with_evidence():
    return {
        "case_id": "fixture-case-1",
        "expected_relevant_evidence_ids": ["evidence-a", "evidence-b"],
        "expected_fields": ["hypothesis", "assay"],
        "field_support": {
            "hypothesis": ["evidence-a"],
            "assay": ["evidence-a"],
        },
        "expected_abstention": False,
        "forbidden_evidence_ids": ["evidence-secret"],
        "retrieval": {
            "status": "RETRIEVED",
            "evidence_ids": ["evidence-noise", "evidence-a", "evidence-secret"],
        },
        "draft": {
            "status": "DRAFT_REQUIRES_RESEARCHER_REVIEW",
            "proposed_fields": {"hypothesis": "fixture", "assay": "fixture"},
            "field_citations": {
                "hypothesis": ["evidence-a"],
                "assay": ["evidence-not-retrieved"],
            },
            "approved": False,
            "study_created": False,
            "mapping_created": False,
            "job_created": False,
            "graph_used": False,
            "simulation_started": False,
        },
    }


def _bundle():
    abstention_case = {
        "case_id": "fixture-case-2",
        "expected_relevant_evidence_ids": [],
        "expected_fields": [],
        "field_support": {},
        "expected_abstention": True,
        "forbidden_evidence_ids": ["evidence-secret"],
        "retrieval": {"status": "NO_APPROVED_EVIDENCE", "evidence_ids": []},
        "draft": {
            "status": "NO_APPROVED_EVIDENCE",
            "proposed_fields": {},
            "field_citations": {},
            "approved": False,
            "study_created": False,
            "mapping_created": False,
            "job_created": False,
            "graph_used": False,
            "simulation_started": False,
        },
    }
    return {
        "schema_version": EVALUATION_SCHEMA,
        "evaluation_id": "fixture-evaluation-a04",
        "evaluation_split": "synthetic_fixture",
        "cases": [_case_with_evidence(), abstention_case],
    }


def test_reports_ranking_abstention_citation_and_safety_metrics():
    report = evaluate_ai_v2_bundle(_bundle(), k=2)
    metrics = report["metrics"]

    assert report["evaluation_case_count"] == 2
    assert metrics["retrieval_recall_at_k_macro"] == pytest.approx(0.5)
    assert metrics["retrieval_mrr"] == pytest.approx(0.5)
    assert metrics["retrieval_ndcg_at_k_macro"] == pytest.approx(0.38685280723454163)
    assert metrics["abstention_accuracy"] == 1.0
    assert metrics["forbidden_evidence_case_count"] == 1
    assert metrics["expected_field_coverage"] == 1.0
    assert metrics["reference_citation_alignment"] == 0.5
    assert metrics["citation_retrieval_membership"] == 0.5
    assert metrics["draft_non_executable_invariant_pass_rate"] == 1.0
    assert report["interpretation_limits"]["biological_validity"] == "NOT_ASSESSED"
    assert report["interpretation_limits"]["heldout_status"] == "LOCKED_NOT_RUN"
    assert len(report["input_bundle_sha256"]) == 64
    assert len(report["report_sha256"]) == 64


def test_rejects_heldout_split_without_inspecting_case_payload():
    bundle = _bundle()
    bundle["evaluation_split"] = "held_out"
    with pytest.raises(EvaluationContractError, match="held-out is locked"):
        evaluate_ai_v2_bundle(bundle)


@pytest.mark.parametrize("split", ["all", "validation", "test"])
def test_rejects_unrecognized_split(split):
    bundle = _bundle()
    bundle["evaluation_split"] = split
    with pytest.raises(EvaluationContractError, match="only development"):
        evaluate_ai_v2_bundle(bundle)


def test_rejects_duplicate_ids_and_invalid_reference_support():
    bundle = _bundle()
    bundle["cases"][0]["retrieval"]["evidence_ids"] = ["evidence-a", "evidence-a"]
    with pytest.raises(EvaluationContractError, match="duplicate IDs"):
        evaluate_ai_v2_bundle(bundle)

    bundle = _bundle()
    bundle["cases"][0]["field_support"]["assay"] = ["not-relevant"]
    with pytest.raises(EvaluationContractError, match="relevant evidence IDs"):
        evaluate_ai_v2_bundle(bundle)


def test_flags_non_executable_boundary_violation():
    bundle = _bundle()
    bundle["cases"][0]["draft"]["job_created"] = True
    report = evaluate_ai_v2_bundle(bundle)
    assert report["metrics"]["draft_non_executable_invariant_pass_rate"] == 0.5
    assert report["cases"][0]["draft_non_executable_invariant_pass"] is False


def test_does_not_mutate_input_bundle():
    bundle = _bundle()
    original = copy.deepcopy(bundle)
    evaluate_ai_v2_bundle(bundle)
    assert bundle == original
