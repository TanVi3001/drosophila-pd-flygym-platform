"""Locked, label-blind score construction for the Shiu v2 benchmark.

The score builder deliberately separates three things that are easy to mix up:
the observed computational effect from the rewired-LIF run, the uncertainty
penalty taken from the published model summary, and the reviewed mapping gates.
It never reads the retrospective response label when constructing a score.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from typing import Any


SCORE_LOCK_VERSION = 1
DEFAULT_UNCERTAINTY_STIMULUS_HZ = "50"
DEFAULT_UNCERTAINTY_FLOOR_HZ = 1e-12


def _finite(value: Any, *, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric") from exc
    if not math.isfinite(number):
        raise ValueError(f"{field} must be finite")
    return number


def _parse_json_list(value: Any, *, field: str) -> list[str]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{field} must contain a JSON list") from exc
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{field} must contain a list")
    return [str(item) for item in value]


def _mapping_value(row: Mapping[str, Any], field: str) -> str:
    return str(row.get(field, "")).strip()


def _mapping_gate(row: Mapping[str, Any], *, expected_readout_ids: Sequence[str]) -> tuple[int, int, dict[str, Any]]:
    mapping_status = _mapping_value(row, "mapping_status").upper()
    assay_comparable = _mapping_value(row, "assay_comparable").upper()
    reviewer_1 = _mapping_value(row, "reviewer_1")
    reviewer_2 = _mapping_value(row, "reviewer_2")
    reviewer_1_decision = _mapping_value(row, "reviewer_1_decision").upper()
    reviewer_2_decision = _mapping_value(row, "reviewer_2_decision").upper()
    review_decision = _mapping_value(row, "review_decision").upper()
    readout_ids = _parse_json_list(row.get("readout_ids_json", ""), field="readout_ids_json")
    input_ids = _parse_json_list(row.get("input_ids_json", ""), field="input_ids_json")
    expected = [str(item) for item in expected_readout_ids]

    evidence_ok = bool(
        mapping_status == "APPROVED"
        and reviewer_1
        and reviewer_2
        and reviewer_1_decision == "APPROVED"
        and reviewer_2_decision == "APPROVED"
        and review_decision == "APPROVED"
    )
    capability_ok = bool(
        assay_comparable == "YES"
        and bool(input_ids)
        and readout_ids == expected
    )
    audit = {
        "mapping_status": mapping_status,
        "assay_comparable": assay_comparable,
        "reviewer_1_present": bool(reviewer_1),
        "reviewer_2_present": bool(reviewer_2),
        "reviewer_1_decision": reviewer_1_decision,
        "reviewer_2_decision": reviewer_2_decision,
        "review_decision": review_decision,
        "input_count": len(input_ids),
        "readout_ids": readout_ids,
        "expected_readout_ids": expected,
        "evidence_gate": int(evidence_ok),
        "capability_gate": int(capability_ok),
    }
    return int(evidence_ok), int(capability_ok), audit


def _published_uncertainty(case: Any, *, stimulus_hz: str) -> tuple[float, float]:
    sd_by_stimulus = case.metadata.get("model_mn9_sd_hz", {})
    if not isinstance(sd_by_stimulus, Mapping):
        raise ValueError(f"{case.case_id} is missing model_mn9_sd_hz")
    sides = sd_by_stimulus.get(str(stimulus_hz))
    if not isinstance(sides, Mapping):
        raise ValueError(f"{case.case_id} is missing uncertainty at {stimulus_hz} Hz")
    left = _finite(sides.get("left"), field=f"{case.case_id} uncertainty.left")
    right = _finite(sides.get("right"), field=f"{case.case_id} uncertainty.right")
    if left < 0 or right < 0:
        raise ValueError(f"{case.case_id} uncertainty cannot be negative")
    return (left + right) / 2.0, left if left == right else right


def build_locked_scores(
    protocol: Any,
    mapping_rows: Sequence[Mapping[str, Any]],
    rewire_scores: Mapping[str, Any],
    score_spec: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the frozen score systems and an auditable per-case table.

    ``protocol`` is a :class:`BenchmarkProtocol`, but it is typed as ``Any``
    here to keep this small pure function easy to exercise with test doubles.
    The function fails closed on missing/extra case IDs and on malformed gates.
    """

    expected_protocol_hash = str(score_spec.get("protocol_hash", "")).strip()
    if expected_protocol_hash != protocol.protocol_hash:
        raise ValueError("score spec protocol_hash does not match benchmark protocol")
    formula = score_spec.get("formula", {})
    if not isinstance(formula, Mapping):
        raise ValueError("score spec formula must be an object")
    stimulus_hz = str(formula.get("uncertainty_stimulus_hz", DEFAULT_UNCERTAINTY_STIMULUS_HZ))
    uncertainty_floor = _finite(
        formula.get("uncertainty_floor_hz", DEFAULT_UNCERTAINTY_FLOOR_HZ),
        field="uncertainty_floor_hz",
    )
    if uncertainty_floor <= 0:
        raise ValueError("uncertainty_floor_hz must be positive")
    expected_readout_ids = _parse_json_list(
        score_spec.get("capability_gate", {}).get("expected_readout_ids", []),
        field="capability_gate.expected_readout_ids",
    )
    if not expected_readout_ids:
        raise ValueError("score spec must declare expected readout IDs")

    rows_by_id: dict[str, Mapping[str, Any]] = {}
    for row in mapping_rows:
        case_id = _mapping_value(row, "case_id")
        if not case_id:
            raise ValueError("mapping row has an empty case_id")
        if case_id in rows_by_id:
            raise ValueError(f"duplicate mapping row: {case_id}")
        rows_by_id[case_id] = row
    case_by_id = {case.case_id: case for case in protocol.cases}
    expected_case_ids = set(case_by_id)
    if set(rows_by_id) != expected_case_ids:
        missing = sorted(expected_case_ids - set(rows_by_id))
        extra = sorted(set(rows_by_id) - expected_case_ids)
        raise ValueError(f"mapping case IDs do not match protocol; missing={missing}, extra={extra}")
    if set(str(case_id) for case_id in rewire_scores) != expected_case_ids:
        missing = sorted(expected_case_ids - set(str(case_id) for case_id in rewire_scores))
        extra = sorted(set(str(case_id) for case_id in rewire_scores) - expected_case_ids)
        raise ValueError(f"rewire score IDs do not match protocol; missing={missing}, extra={extra}")

    systems = {
        "rewire_effect_only": {},
        "rewire_plus_uncertainty": {},
        "full_workbench_locked": {},
    }
    rows: list[dict[str, Any]] = []
    evidence_pass = 0
    capability_pass = 0
    for case in protocol.cases:
        case_id = case.case_id
        simulation_effect = _finite(rewire_scores[case_id], field=f"{case_id} rewire score")
        if simulation_effect < 0:
            raise ValueError(f"{case_id} rewire score cannot be negative")
        uncertainty, right_uncertainty = _published_uncertainty(case, stimulus_hz=stimulus_hz)
        evidence_gate, capability_gate, gate_audit = _mapping_gate(
            rows_by_id[case_id], expected_readout_ids=expected_readout_ids
        )
        evidence_pass += evidence_gate
        capability_pass += capability_gate
        uncertainty_adjusted = simulation_effect / max(uncertainty, uncertainty_floor)
        full_score = uncertainty_adjusted * evidence_gate * capability_gate
        systems["rewire_effect_only"][case_id] = simulation_effect
        systems["rewire_plus_uncertainty"][case_id] = uncertainty_adjusted
        systems["full_workbench_locked"][case_id] = full_score
        rows.append(
            {
                "case_id": case_id,
                "simulation_effect_hz": simulation_effect,
                "published_uncertainty_mean_hz": uncertainty,
                "published_uncertainty_right_hz": right_uncertainty,
                "uncertainty_adjusted_score": uncertainty_adjusted,
                "evidence_gate": evidence_gate,
                "capability_gate": capability_gate,
                "full_workbench_score": full_score,
                "gate_audit": gate_audit,
            }
        )

    return {
        "score_lock_version": SCORE_LOCK_VERSION,
        "systems": systems,
        "rows": rows,
        "audit": {
            "case_count": len(rows),
            "evidence_gate_pass_count": evidence_pass,
            "capability_gate_pass_count": capability_pass,
            "evidence_variation": "NONE" if evidence_pass in {0, len(rows)} else "PRESENT",
            "capability_variation": "NONE" if capability_pass in {0, len(rows)} else "PRESENT",
            "label_blind_score_construction": True,
            "forbidden_score_inputs": list(score_spec.get("forbidden_score_inputs", [])),
        },
    }
