"""Derived metrics for deterministic locomotion rollouts."""

from __future__ import annotations

import math
from typing import Any

import numpy as np


def compute_locomotion_metrics(
    *,
    thorax_positions: np.ndarray,
    thorax_quaternions: np.ndarray,
    joint_angle_actions: np.ndarray,
    adhesion_onoff: np.ndarray | None,
    timestep_s: float,
    requested_duration_s: float,
    instability_height_floor_mm: float,
) -> dict[str, Any]:
    """Compute compact derived metrics from raw rollout arrays."""

    positions = _as_float_array("thorax_positions", thorax_positions, ndim=2)
    quaternions = _as_float_array("thorax_quaternions", thorax_quaternions, ndim=2)
    actions = _as_float_array("joint_angle_actions", joint_angle_actions, ndim=2)

    if positions.shape[1] != 3:
        raise ValueError("thorax_positions must have shape (n_samples, 3).")
    if quaternions.shape[1] != 4:
        raise ValueError("thorax_quaternions must have shape (n_samples, 4).")
    if positions.shape[0] != quaternions.shape[0]:
        raise ValueError("position and quaternion sample counts must match.")
    if positions.shape[0] != actions.shape[0] + 1:
        raise ValueError("positions must include one initial sample plus one per action.")

    step_count = int(actions.shape[0])
    executed_duration_s = step_count * float(timestep_s)

    initial_position = positions[0]
    final_position = positions[-1]
    planar_vector = final_position[:2] - initial_position[:2]
    planar_displacement_mm = float(np.linalg.norm(planar_vector))
    planar_step_vectors = np.diff(positions[:, :2], axis=0)
    planar_path_length_mm = float(
        np.sum(np.linalg.norm(planar_step_vectors, axis=1))
    )
    trajectory_efficiency = (
        planar_displacement_mm / planar_path_length_mm
        if math.isfinite(planar_path_length_mm) and planar_path_length_mm > 1e-12
        else None
    )
    mean_planar_displacement_speed_mm_s = (
        planar_displacement_mm / executed_duration_s
        if executed_duration_s > 0
        else math.nan
    )
    mean_planar_path_speed_mm_s = (
        planar_path_length_mm / executed_duration_s
        if executed_duration_s > 0
        else math.nan
    )

    yaws = np.array([_yaw_from_quaternion(quat) for quat in quaternions], dtype=float)
    yaws = np.unwrap(yaws)
    yaw_change_rad = float(yaws[-1] - yaws[0])

    finite = {
        "thorax_positions": bool(np.isfinite(positions).all()),
        "thorax_quaternions": bool(np.isfinite(quaternions).all()),
        "joint_angle_actions": bool(np.isfinite(actions).all()),
    }
    if adhesion_onoff is not None:
        adhesion = np.asarray(adhesion_onoff, dtype=bool)
        if adhesion.shape != (step_count, 6):
            raise ValueError("adhesion_onoff must have shape (n_steps, 6).")
        adhesion_summary = _adhesion_summary(adhesion)
    else:
        adhesion_summary = {
            "available": False,
            "duty_factor_by_leg": None,
            "transition_count_by_leg": None,
        }

    from drosophila_pd.metrics.bouts import compute_walking_bouts_from_positions
    from drosophila_pd.metrics.turning import compute_turning_metrics

    if finite["thorax_positions"]:
        bout_metrics = compute_walking_bouts_from_positions(
            thorax_positions=positions,
            timestep_s=timestep_s,
            speed_threshold_mm_s=1.0,
        )
    else:
        bout_metrics = {
            "walking_duty_cycle": math.nan,
            "bout_count": 0,
            "pause_count": 0,
            "walking_duration_s": math.nan,
            "pause_duration_s": math.nan,
        }

    if finite["thorax_quaternions"]:
        turning_metrics = compute_turning_metrics(
            heading_rad=yaws,
            timestep_s=timestep_s,
            turn_rate_threshold_rad_s=0.5,
        )
    else:
        turning_metrics = {
            "cumulative_turning_rad": math.nan,
            "left_right_asymmetry": math.nan,
            "yaw_rate_summary_rad_s": {"mean": math.nan},
        }

    height_summary = _summary(positions[:, 2])
    metrics = {
        "requested_duration_s": _json_float(requested_duration_s),
        "executed_duration_s": _json_float(executed_duration_s),
        "timestep_s": _json_float(timestep_s),
        "step_count": step_count,
        "sample_count": int(positions.shape[0]),
        "initial_thorax_position_mm": _json_float_list(initial_position),
        "final_thorax_position_mm": _json_float_list(final_position),
        "planar_displacement_vector_mm": _json_float_list(planar_vector),
        "planar_displacement_mm": _json_float(planar_displacement_mm),
        "planar_path_length_mm": _json_float(planar_path_length_mm),
        "trajectory_efficiency": _json_float(trajectory_efficiency),
        # Historical field retained for artifact compatibility. Its exact
        # definition is displacement-over-time, not distance travelled.
        "mean_planar_speed_mm_s": _json_float(mean_planar_displacement_speed_mm_s),
        "mean_planar_displacement_speed_mm_s": _json_float(
            mean_planar_displacement_speed_mm_s
        ),
        "mean_planar_path_speed_mm_s": _json_float(mean_planar_path_speed_mm_s),
        "metric_definition_version": "locomotion-metrics-2",
        "metric_definitions": {
            "mean_planar_speed_mm_s": "historical_planar_displacement_over_time",
            "mean_planar_displacement_speed_mm_s": "planar_displacement_over_time",
            "mean_planar_path_speed_mm_s": "planar_path_length_over_time",
        },
        "body_height_mm": height_summary,
        "heading_yaw_change_rad": _json_float(yaw_change_rad),
        "heading_yaw_initial_rad": _json_float(yaws[0]),
        "heading_yaw_final_rad": _json_float(yaws[-1]),
        "walking_duty_cycle": _json_float(bout_metrics["walking_duty_cycle"]),
        "walking_bout_count": int(bout_metrics["bout_count"]),
        "pause_bout_count": int(bout_metrics["pause_count"]),
        "walking_duration_s": _json_float(bout_metrics["walking_duration_s"]),
        "pause_duration_s": _json_float(bout_metrics["pause_duration_s"]),
        "cumulative_turning_rad": _json_float(turning_metrics["cumulative_turning_rad"]),
        "left_right_asymmetry": _json_float(turning_metrics["left_right_asymmetry"]),
        "yaw_rate_mean_rad_s": _json_float(turning_metrics["yaw_rate_summary_rad_s"]["mean"]),
        "body_height_below_floor": (
            height_summary["min"] is not None
            and height_summary["min"] < instability_height_floor_mm
        ),
        "instability_height_floor_mm": _json_float(instability_height_floor_mm),
        "finite": finite,
        "observations_are_finite": all(finite.values()),
        "controller_action_summary": {
            "joint_angle_action": _summary(actions),
            "joint_angle_action_abs": _summary(np.abs(actions)),
            "adhesion": adhesion_summary,
        },
    }
    metrics["derived_metrics_are_finite"] = _nested_numbers_are_finite(metrics)
    return metrics


def check_locomotion_pass_criteria(
    *,
    metrics: dict[str, Any],
    expected_step_count: int,
    expected_actuated_dofs: int,
    observed_actuated_dofs: int,
    expected_adhesion_actuators: int,
    observed_adhesion_actuators: int,
    deterministic_seed_recorded: bool,
) -> dict[str, dict[str, Any]]:
    """Build conservative software/simulation PASS/FAIL checks."""

    checks = {
        "expected_step_count": _check(expected_step_count, metrics["step_count"]),
        "required_observations_finite": _check(
            True, metrics["observations_are_finite"]
        ),
        "derived_metrics_finite": _check(True, metrics["derived_metrics_are_finite"]),
        "body_height_below_numerical_floor": _check(
            False, metrics["body_height_below_floor"]
        ),
        "expected_actuated_dofs": _check(
            expected_actuated_dofs, observed_actuated_dofs
        ),
        "expected_adhesion_actuators": _check(
            expected_adhesion_actuators, observed_adhesion_actuators
        ),
        "deterministic_seed_recorded": _check(True, deterministic_seed_recorded),
    }
    return checks


def _adhesion_summary(adhesion: np.ndarray) -> dict[str, Any]:
    if adhesion.shape[0] == 0:
        transition_count = np.zeros(adhesion.shape[1], dtype=int)
    else:
        transition_count = np.count_nonzero(np.diff(adhesion.astype(int), axis=0), axis=0)
    return {
        "available": True,
        "leg_order": ["lf", "lm", "lh", "rf", "rm", "rh"],
        "duty_factor_by_leg": _json_float_list(adhesion.mean(axis=0)),
        "transition_count_by_leg": [int(value) for value in transition_count],
    }


def _as_float_array(name: str, value: np.ndarray, *, ndim: int) -> np.ndarray:
    array = np.asarray(value, dtype=float)
    if array.ndim != ndim:
        raise ValueError(f"{name} must have {ndim} dimensions.")
    return array


def _check(expected: Any, observed: Any) -> dict[str, Any]:
    return {
        "expected": expected,
        "observed": observed,
        "pass": observed == expected,
    }


def _json_float(value: Any) -> float | None:
    try:
        as_float = float(value)
    except (TypeError, ValueError):
        return None
    return as_float if math.isfinite(as_float) else None


def _json_float_list(values: np.ndarray) -> list[float | None]:
    return [_json_float(value) for value in np.asarray(values).ravel()]


def _nested_numbers_are_finite(value: Any) -> bool:
    if isinstance(value, dict):
        return all(_nested_numbers_are_finite(item) for item in value.values())
    if isinstance(value, list):
        return all(_nested_numbers_are_finite(item) for item in value)
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return True
    if isinstance(value, (int, float)):
        return math.isfinite(float(value))
    return True


def _summary(values: np.ndarray) -> dict[str, float | int | None]:
    array = np.asarray(values, dtype=float)
    return {
        "count": int(array.size),
        "min": _json_float(np.nanmin(array)) if array.size else None,
        "max": _json_float(np.nanmax(array)) if array.size else None,
        "mean": _json_float(np.nanmean(array)) if array.size else None,
        "initial": _json_float(array.ravel()[0]) if array.size else None,
        "final": _json_float(array.ravel()[-1]) if array.size else None,
    }


def _yaw_from_quaternion(quat: np.ndarray) -> float:
    quat = np.asarray(quat, dtype=float)
    norm = np.linalg.norm(quat)
    if not np.isfinite(norm) or norm == 0:
        return math.nan
    w, x, y, z = quat / norm
    heading_x = 1 - 2 * (y * y + z * z)
    heading_y = 2 * (x * y + w * z)
    return math.atan2(heading_y, heading_x)


__all__ = [
    "check_locomotion_pass_criteria",
    "compute_locomotion_metrics",
]
