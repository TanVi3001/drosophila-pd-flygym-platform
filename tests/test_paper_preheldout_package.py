from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).parents[1]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_final_protocol_records_comparator_approval_but_keeps_execution_locked() -> None:
    protocol = json.loads((ROOT / "configs/workbench/final_evaluation_protocol_v1.json").read_text())
    score_lock = json.loads((ROOT / "configs/workbench/shiu_workbench_score_v1.json").read_text())
    score_path = ROOT / protocol["score_lock"]["path"]

    assert protocol["status"] == "OWNER_APPROVED_COMPARATORS_ONLY"
    assert protocol["owner_approval"]["status"] == "APPROVED_COMPARATORS_ONLY"
    assert protocol["owner_comparator_approval"] == "APPROVED_OPTION_A"
    assert protocol["benchmark"]["case_count"] == 106
    assert protocol["benchmark"]["development_count"] == 74
    assert protocol["benchmark"]["held_out_count"] == 32
    assert protocol["score_lock"]["k"] == score_lock["precision_at_k"] == 5
    assert protocol["evaluation"]["primary_metric"] == score_lock["primary_endpoint"]
    assert protocol["score_lock"]["sha256"] == _sha(score_path)
    assert len(protocol["benchmark"]["registry_sha256"]) == 64
    assert len(protocol["mapping"]["sha256"]) == 64
    assert len(protocol["rewire_score_input"]["sha256"]) == 64
    assert protocol["approved_executor"] is None
    assert protocol["heldout_guard"]["approval_is_set"] is False
    assert protocol["heldout_guard"]["single_use_external_ledger_required"] is True
    assert protocol["heldout_guard"]["executor_case_count_must_equal"] == 32
    assert protocol["heldout_execution_authorized"] is False
    assert protocol["heldout_exposure_status"] == "UNVERIFIABLE"
    assert protocol["heldout_pristine_claim"] == "UNAVAILABLE"
    assert "held_out_outcomes_inspected" not in protocol


def test_comparator_lock_matches_incident_aware_protocol_without_execution_authority() -> None:
    lock = json.loads((ROOT / "configs/workbench/comparator_lock_v1.json").read_text())
    protocol = json.loads((ROOT / "configs/workbench/final_evaluation_protocol_v1.json").read_text())
    expected = [
        "rewire_effect_only",
        "rewire_plus_uncertainty",
        "full_workbench_locked",
        "random_reference",
    ]

    assert lock["status"] == "OWNER_APPROVED"
    assert lock["decision"] == "OPTION_A"
    assert lock["approved_primary_comparator_ids"] == expected
    assert lock["excluded_comparator_ids"] == ["heuristic", "original_model"]
    assert [item["id"] for item in protocol["comparators"]["approved_primary_set"]] == expected
    assert lock["protocol_status"] == protocol["status"] == "OWNER_APPROVED_COMPARATORS_ONLY"
    assert lock["benchmark_identity"]["registry_sha256"] == protocol["benchmark"]["registry_sha256"]
    assert lock["benchmark_identity"]["split_membership_sha256"] == protocol["benchmark"]["split_membership_sha256"]
    assert lock["score_lock"]["sha256"] == protocol["score_lock"]["sha256"]
    assert lock["score_lock"]["k"] == protocol["score_lock"]["k"] == 5
    assert lock["integrity_incident"]["heldout_pristine_claim"] == "UNAVAILABLE"
    assert lock["integrity_incident"]["current_32_case_set_classification"] == "POST_FREEZE_POTENTIALLY_EXPOSED_EVALUATION_SET"
    assert protocol["current_32_case_confirmatory_status"] == "NOT_PRISTINE_UNVERIFIABLE_EXPOSURE"
    assert lock["integrity_incident"]["execution_authorized"] is False
    assert protocol["heldout_execution_authorized"] is False
    assert protocol["heldout_status"] == "LOCKED_NOT_RUN"
    assert all(value is None for value in protocol["execution_pins"].values())
    assert "held_out_outcomes_inspected" not in lock


def test_readiness_docs_keep_heldout_and_scientific_review_pending() -> None:
    readiness = (ROOT / "docs/paper_preheldout_readiness.md").read_text(encoding="utf-8")
    science = (ROOT / "docs/scientific_case_review_status.md").read_text(encoding="utf-8")
    assert "HELDOUT_STATUS = LOCKED_NOT_RUN" in readiness
    assert "HELDOUT_EXPOSURE_STATUS = UNVERIFIABLE" in readiness
    assert "HELDOUT_PRISTINE_CLAIM = UNAVAILABLE" in readiness
    assert "NOT_READY_FOR_HELDOUT" in readiness
    assert "SCIENTIFIC_CASE_REVIEW = PENDING" in science


def test_manuscript_explicitly_separates_heldout_placeholder_and_claim_boundary() -> None:
    manuscript = (ROOT / "docs/workbench_state4_methods_results_draft_20260924.md").read_text(encoding="utf-8")
    assert "Final held-out evaluation — pending locked one-time execution" in manuscript
    assert "MN9 firing/activity is a computational neural readout" in manuscript
    assert "DEVELOPMENT only" in manuscript
