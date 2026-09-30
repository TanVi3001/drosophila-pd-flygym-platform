from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).parents[1]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_final_protocol_is_concrete_but_still_owner_gated() -> None:
    protocol = json.loads((ROOT / "configs/workbench/final_evaluation_protocol_v1.json").read_text())
    score_lock = json.loads((ROOT / "configs/workbench/shiu_workbench_score_v1.json").read_text())
    registry = ROOT / protocol["benchmark"]["registry"]
    score_path = ROOT / protocol["score_lock"]["path"]
    mapping = ROOT / protocol["mapping"]["path"]

    assert protocol["status"] == "PROPOSED_OWNER_APPROVAL_REQUIRED"
    assert protocol["owner_approval"]["status"] == "PENDING"
    assert protocol["benchmark"]["case_count"] == 106
    assert protocol["benchmark"]["development_count"] == 74
    assert protocol["benchmark"]["held_out_count"] == 32
    assert protocol["score_lock"]["k"] == score_lock["precision_at_k"] == 5
    assert protocol["evaluation"]["primary_metric"] == score_lock["primary_endpoint"]
    assert protocol["benchmark"]["registry_sha256"] == _sha(registry)
    assert protocol["score_lock"]["sha256"] == _sha(score_path)
    assert protocol["mapping"]["sha256"] == _sha(mapping)
    assert len(protocol["rewire_score_input"]["sha256"]) == 64
    assert protocol["approved_executor"] is None
    assert protocol["heldout_guard"]["approval_is_set"] is False
    assert protocol["heldout_guard"]["single_use_external_ledger_required"] is True
    assert protocol["heldout_guard"]["executor_case_count_must_equal"] == 32


def test_readiness_docs_keep_heldout_and_scientific_review_pending() -> None:
    readiness = (ROOT / "docs/paper_preheldout_readiness.md").read_text(encoding="utf-8")
    science = (ROOT / "docs/scientific_case_review_status.md").read_text(encoding="utf-8")
    assert "HELDOUT_STATUS = LOCKED_NOT_RUN" in readiness
    assert "NOT_READY_FOR_HELDOUT" in readiness
    assert "SCIENTIFIC_CASE_REVIEW = PENDING" in science


def test_manuscript_explicitly_separates_heldout_placeholder_and_claim_boundary() -> None:
    manuscript = (ROOT / "docs/workbench_state4_methods_results_draft_20260924.md").read_text(encoding="utf-8")
    assert "Final held-out evaluation — pending locked one-time execution" in manuscript
    assert "MN9 firing/activity is a computational neural readout" in manuscript
    assert "DEVELOPMENT only" in manuscript
