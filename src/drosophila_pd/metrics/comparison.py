"""Comparison metrics for paired locomotion reports."""

from __future__ import annotations

import math
from typing import Any


DEFAULT_RELATIVE_EPSILON = 1e-9


def compare_locomotion_reports(
    baseline_report: dict[str, Any],
    perturbed_report: dict[str, Any],
    *,
    relative_epsilon: float = DEFAULT_RELATIVE_EPSILON,
) -> dict[str, Any]:
    """Compare derived metrics from paired baseline and perturbed reports."""

    baseline = baseline_report["derived_locomotion_metrics"]
    perturbed = perturbed_report["derived_locomotion_metrics"]
    scalars = {
        "planar_displacement_mm": _scalar_delta(
            baseline["planar_displacement_mm"],
            perturbed["planar_displacement_mm"],
            relative_epsilon=relative_epsilon,
        ),
        "mean_planar_speed_mm_s": _scalar_delta(
            baseline["mean_planar_speed_mm_s"],
            perturbed["mean_planar_speed_mm_s"],
            relative_epsilon=relative_epsilon,
        ),
        "heading_yaw_change_rad": _scalar_delta(
            baseline["heading_yaw_change_rad"],
            perturbed["heading_yaw_change_rad"],
            relative_epsilon=relative_epsilon,
        ),
        "body_height_min_mm": _scalar_delta(
            baseline["body_height_mm"]["min"],
            perturbed["body_height_mm"]["min"],
            relative_epsilon=relative_epsilon,
        ),
        "body_height_mean_mm": _scalar_delta(
            baseline["body_height_mm"]["mean"],
            perturbed["body_height_mm"]["mean"],
            relative_epsilon=relative_epsilon,
        ),
        "body_height_range_mm": _scalar_delta(
            _height_range(baseline),
            _height_range(perturbed),
            relative_epsilon=relative_epsilon,
        ),
        "joint_angle_action_mean": _scalar_delta(
            baseline["controller_action_summary"]["joint_angle_action"]["mean"],
            perturbed["controller_action_summary"]["joint_angle_action"]["mean"],
            relative_epsilon=relative_epsilon,
        ),
        "joint_angle_action_abs_mean": _scalar_delta(
            baseline["controller_action_summary"]["joint_angle_action_abs"][
                "mean"
            ],
            perturbed["controller_action_summary"]["joint_angle_action_abs"][
                "mean"
            ],
            relative_epsilon=relative_epsilon,
        ),
    }
    for optional_metric in (
        "planar_path_length_mm",
        "trajectory_efficiency",
        "walking_duty_cycle",
        "walking_bout_count",
        "pause_bout_count",
        "walking_duration_s",
        "pause_duration_s",
        "mean_planar_displacement_speed_mm_s",
        "mean_planar_path_speed_mm_s",
        "cumulative_turning_rad",
        "left_right_asymmetry",
        "yaw_rate_mean_rad_s",
    ):
        if optional_metric in baseline and optional_metric in perturbed:
            scalars[optional_metric] = _scalar_delta(
                baseline[optional_metric],
                perturbed[optional_metric],
                relative_epsilon=relative_epsilon,
            )
    return {
        "scalars": scalars,
        "adhesion": _adhesion_delta(
            baseline["controller_action_summary"]["adhesion"],
            perturbed["controller_action_summary"]["adhesion"],
        ),
        "relative_epsilon": relative_epsilon,
    }


def evaluate_identity_equivalence(
    baseline_report: dict[str, Any],
    perturbed_report: dict[str, Any],
    *,
    abs_tol: float = 1e-9,
    rel_tol: float = 1e-9,
) -> dict[str, Any]:
    """Evaluate deterministic equivalence for baseline-vs-identity runs."""

    baseline = baseline_report["derived_locomotion_metrics"]
    perturbed = perturbed_report["derived_locomotion_metrics"]
    checks = {
        "step_count": _exact_check(
            baseline["step_count"], perturbed["step_count"]
        ),
        "final_thorax_position_mm": _sequence_close_check(
            baseline["final_thorax_position_mm"],
            perturbed["final_thorax_position_mm"],
            abs_tol=abs_tol,
            rel_tol=rel_tol,
        ),
        "planar_displacement_mm": _scalar_close_check(
            baseline["planar_displacement_mm"],
            perturbed["planar_displacement_mm"],
            abs_tol=abs_tol,
            rel_tol=rel_tol,
        ),
        "mean_planar_speed_mm_s": _scalar_close_check(
            baseline["mean_planar_speed_mm_s"],
            perturbed["mean_planar_speed_mm_s"],
            abs_tol=abs_tol,
            rel_tol=rel_tol,
        ),
        "heading_yaw_change_rad": _scalar_close_check(
            baseline["heading_yaw_change_rad"],
            perturbed["heading_yaw_change_rad"],
            abs_tol=abs_tol,
            rel_tol=rel_tol,
        ),
        "body_height_mm": _summary_close_check(
            baseline["body_height_mm"],
            perturbed["body_height_mm"],
            abs_tol=abs_tol,
            rel_tol=rel_tol,
        ),
        "joint_angle_action_summary": _summary_close_check(
            baseline["controller_action_summary"]["joint_angle_action"],
            perturbed["controller_action_summary"]["joint_angle_action"],
            abs_tol=abs_tol,
            rel_tol=rel_tol,
        ),
        "joint_angle_action_abs_summary": _summary_close_check(
            baseline["controller_action_summary"]["joint_angle_action_abs"],
            perturbed["controller_action_summary"]["joint_angle_action_abs"],
            abs_tol=abs_tol,
            rel_tol=rel_tol,
        ),
        "adhesion_summary": _adhesion_equivalence_check(
            baseline["controller_action_summary"]["adhesion"],
            perturbed["controller_action_summary"]["adhesion"],
            abs_tol=abs_tol,
            rel_tol=rel_tol,
        ),
    }
    return {
        "pass": all(check["pass"] for check in checks.values()),
        "abs_tol": abs_tol,
        "rel_tol": rel_tol,
        "checks": checks,
    }


def _scalar_delta(
    baseline: Any, perturbed: Any, *, relative_epsilon: float
) -> dict[str, float | None]:
    baseline_value = _as_finite_float(baseline)
    perturbed_value = _as_finite_float(perturbed)
    if baseline_value is None or perturbed_value is None:
        return {
            "baseline": baseline_value,
            "perturbed": perturbed_value,
            "absolute_delta": None,
            "relative_delta": None,
        }
    absolute_delta = perturbed_value - baseline_value
    relative_delta = (
        None
        if abs(baseline_value) <= relative_epsilon
        else absolute_delta / abs(baseline_value)
    )
    return {
        "baseline": baseline_value,
        "perturbed": perturbed_value,
        "absolute_delta": absolute_delta,
        "relative_delta": relative_delta,
    }


def _adhesion_delta(
    baseline: dict[str, Any], perturbed: dict[str, Any]
) -> dict[str, Any]:
    if not baseline.get("available") or not perturbed.get("available"):
        return {"available": False}
    leg_order = baseline.get("leg_order")
    if leg_order != perturbed.get("leg_order"):
        return {
            "available": False,
            "reason": "adhesion leg orders differ",
            "baseline_leg_order": leg_order,
            "perturbed_leg_order": perturbed.get("leg_order"),
        }
    baseline_duty = [_as_finite_float(value) for value in baseline["duty_factor_by_leg"]]
    perturbed_duty = [
        _as_finite_float(value) for value in perturbed["duty_factor_by_leg"]
    ]
    baseline_transitions = [int(value) for value in baseline["transition_count_by_leg"]]
    perturbed_transitions = [
        int(value) for value in perturbed["transition_count_by_leg"]
    ]
    return {
        "available": True,
        "leg_order": leg_order,
        "baseline_duty_factor_by_leg": baseline_duty,
        "perturbed_duty_factor_by_leg": perturbed_duty,
        "duty_factor_delta_by_leg": [
            (
                None
                if base is None or value is None
                else value - base
            )
            for base, value in zip(baseline_duty, perturbed_duty)
        ],
        "baseline_transition_count_by_leg": baseline_transitions,
        "perturbed_transition_count_by_leg": perturbed_transitions,
        "transition_count_delta_by_leg": [
            value - base
            for base, value in zip(baseline_transitions, perturbed_transitions)
        ],
    }


def _height_range(metrics: dict[str, Any]) -> float | None:
    height = metrics["body_height_mm"]
    minimum = _as_finite_float(height["min"])
    maximum = _as_finite_float(height["max"])
    if minimum is None or maximum is None:
        return None
    return maximum - minimum


def _exact_check(baseline: Any, perturbed: Any) -> dict[str, Any]:
    return {
        "baseline": baseline,
        "perturbed": perturbed,
        "pass": baseline == perturbed,
    }


def _scalar_close_check(
    baseline: Any, perturbed: Any, *, abs_tol: float, rel_tol: float
) -> dict[str, Any]:
    baseline_value = _as_finite_float(baseline)
    perturbed_value = _as_finite_float(perturbed)
    if baseline_value is None or perturbed_value is None:
        return {
            "baseline": baseline_value,
            "perturbed": perturbed_value,
            "absolute_difference": None,
            "pass": False,
        }
    absolute_difference = abs(perturbed_value - baseline_value)
    return {
        "baseline": baseline_value,
        "perturbed": perturbed_value,
        "absolute_difference": absolute_difference,
        "pass": math.isclose(
            baseline_value,
            perturbed_value,
            abs_tol=abs_tol,
            rel_tol=rel_tol,
        ),
    }


def _sequence_close_check(
    baseline: list[Any],
    perturbed: list[Any],
    *,
    abs_tol: float,
    rel_tol: float,
) -> dict[str, Any]:
    if len(baseline) != len(perturbed):
        return {
            "baseline": baseline,
            "perturbed": perturbed,
            "max_absolute_difference": None,
            "pass": False,
        }
    item_checks = [
        _scalar_close_check(base, value, abs_tol=abs_tol, rel_tol=rel_tol)
        for base, value in zip(baseline, perturbed)
    ]
    differences = [
        check["absolute_difference"]
        for check in item_checks
        if check["absolute_difference"] is not None
    ]
    return {
        "baseline": baseline,
        "perturbed": perturbed,
        "max_absolute_difference": max(differences) if differences else None,
        "pass": all(check["pass"] for check in item_checks),
    }


def _summary_close_check(
    baseline: dict[str, Any],
    perturbed: dict[str, Any],
    *,
    abs_tol: float,
    rel_tol: float,
) -> dict[str, Any]:
    checks = {}
    for key in ("count", "min", "max", "mean", "initial", "final"):
        if key == "count":
            checks[key] = _exact_check(baseline.get(key), perturbed.get(key))
        else:
            checks[key] = _scalar_close_check(
                baseline.get(key),
                perturbed.get(key),
                abs_tol=abs_tol,
                rel_tol=rel_tol,
            )
    return {"pass": all(check["pass"] for check in checks.values()), "checks": checks}


def _adhesion_equivalence_check(
    baseline: dict[str, Any],
    perturbed: dict[str, Any],
    *,
    abs_tol: float,
    rel_tol: float,
) -> dict[str, Any]:
    if baseline.get("available") != perturbed.get("available"):
        return {"pass": False, "reason": "adhesion availability differs"}
    if not baseline.get("available"):
        return {"pass": True, "available": False}
    checks = {
        "leg_order": _exact_check(baseline.get("leg_order"), perturbed.get("leg_order")),
        "duty_factor_by_leg": _sequence_close_check(
            baseline["duty_factor_by_leg"],
            perturbed["duty_factor_by_leg"],
            abs_tol=abs_tol,
            rel_tol=rel_tol,
        ),
        "transition_count_by_leg": _exact_check(
            baseline["transition_count_by_leg"],
            perturbed["transition_count_by_leg"],
        ),
    }
    return {"pass": all(check["pass"] for check in checks.values()), "checks": checks}


def _as_finite_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


__all__ = [
    "compare_locomotion_reports",
    "evaluate_identity_equivalence",
]
