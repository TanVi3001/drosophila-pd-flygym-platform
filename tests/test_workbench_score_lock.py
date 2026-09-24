from __future__ import annotations

from types import SimpleNamespace

import pytest

from drosophila_pd.workbench.score_lock import build_locked_scores


def _protocol():
    cases = []
    for case_id in ("case_a", "case_b"):
        cases.append(
            SimpleNamespace(
                case_id=case_id,
                metadata={
                    "model_mn9_sd_hz": {
                        "50": {"left": 2.0, "right": 4.0},
                    }
                },
            )
        )
    return SimpleNamespace(
        cases=tuple(cases),
        protocol_hash="protocol-hash",
    )


def _spec():
    return {
        "protocol_hash": "protocol-hash",
        "formula": {"uncertainty_stimulus_hz": "50", "uncertainty_floor_hz": 1e-12},
        "capability_gate": {"expected_readout_ids": ["readout_a", "readout_b"]},
        "forbidden_score_inputs": ["reference_label", "observed_response_fraction", "shortest_path"],
    }


def _mapping(case_id: str, *, approved: bool = True):
    decision = "APPROVED" if approved else "PENDING"
    return {
        "case_id": case_id,
        "mapping_status": decision,
        "assay_comparable": "YES" if approved else "NO",
        "input_ids_json": '["input"]',
        "readout_ids_json": '["readout_a", "readout_b"]',
        "reviewer_1": "reviewer 1",
        "reviewer_2": "reviewer 2",
        "reviewer_1_decision": decision,
        "reviewer_2_decision": decision,
        "review_decision": decision,
    }


def test_build_locked_scores_is_label_blind_and_applies_gates():
    built = build_locked_scores(
        _protocol(),
        [_mapping("case_a"), _mapping("case_b", approved=False)],
        {"case_a": 12.0, "case_b": 6.0},
        _spec(),
    )
    assert built["systems"]["rewire_effect_only"]["case_a"] == 12.0
    assert built["systems"]["rewire_plus_uncertainty"]["case_a"] == pytest.approx(4.0)
    assert built["systems"]["full_workbench_locked"]["case_a"] == pytest.approx(4.0)
    assert built["systems"]["full_workbench_locked"]["case_b"] == 0.0
    assert built["audit"]["label_blind_score_construction"] is True
    assert built["audit"]["evidence_variation"] == "PRESENT"


def test_build_locked_scores_rejects_case_mismatch():
    with pytest.raises(ValueError, match="mapping case IDs"):
        build_locked_scores(
            _protocol(),
            [_mapping("case_a")],
            {"case_a": 1.0, "case_b": 1.0},
            _spec(),
        )
