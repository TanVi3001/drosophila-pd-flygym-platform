from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from pathlib import Path

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
        "expected_categorical_values": {"assay": "sensory_mn9"},
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
            "proposed_fields": {"hypothesis": "fixture", "assay": "sensory_mn9"},
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
        "expected_categorical_values": {},
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
    assert metrics["retrieval_precision_at_k_macro"] == pytest.approx(0.5)
    assert metrics["retrieval_recall_at_k_macro"] == pytest.approx(0.5)
    assert metrics["retrieval_mrr"] == pytest.approx(0.5)
    assert metrics["abstention_accuracy"] == 1.0
    assert metrics["answer_coverage"] == 0.5
    assert metrics["false_acceptance_rate"] == 0.0
    assert metrics["false_rejection_rate"] == 0.0
    assert metrics["selective_risk"] == 1.0
    assert metrics["forbidden_evidence_case_count"] == 1
    assert metrics["expected_field_coverage"] == 1.0
    assert metrics["study_spec_categorical_field_accuracy"] == 1.0
    assert metrics["citation_precision_reference_proxy"] == 0.5
    assert metrics["unsupported_claim_rate_reference_proxy"] == 0.5
    assert metrics["citation_retrieval_membership"] == 0.5
    assert metrics["draft_non_executable_invariant_pass_rate"] == 1.0
    assert report["interpretation_limits"]["biological_validity"] == "NOT_ASSESSED"
    assert report["interpretation_limits"]["heldout_status"] == "LOCKED_NOT_RUN"
    assert report["confidence_intervals_95"]["retrieval_recall_at_k_macro"] is None
    assert report["confidence_intervals_95"]["abstention_accuracy"]["n_cases"] == 2
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


def test_categorical_field_accuracy_detects_wrong_assay_value():
    bundle = _bundle()
    bundle["cases"][0]["draft"]["proposed_fields"]["assay"] = "wrong_assay"
    report = evaluate_ai_v2_bundle(bundle)
    assert report["metrics"]["study_spec_categorical_field_accuracy"] == 0.0


def test_does_not_mutate_input_bundle():
    bundle = _bundle()
    original = copy.deepcopy(bundle)
    first = evaluate_ai_v2_bundle(bundle)
    second = evaluate_ai_v2_bundle(bundle)
    assert bundle == original
    assert first == second


def test_cli_writes_report_and_refuses_overwrite(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    input_path = tmp_path / "synthetic_bundle.json"
    output_path = tmp_path / "synthetic_report.json"
    input_path.write_text(json.dumps(_bundle()), encoding="utf-8")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root / "src")
    command = [
        sys.executable,
        str(repo_root / "scripts" / "evaluate_workbench_v2_ai.py"),
        "--input", str(input_path), "--output", str(output_path), "--k", "2",
    ]

    first = subprocess.run(command, check=False, capture_output=True, text=True, env=env)
    assert first.returncode == 0, first.stderr
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["evaluation_split"] == "synthetic_fixture"
    prior_bytes = output_path.read_bytes()

    second = subprocess.run(command, check=False, capture_output=True, text=True, env=env)
    assert second.returncode == 2
    assert "refusing to overwrite" in second.stderr
    assert output_path.read_bytes() == prior_bytes
