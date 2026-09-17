from __future__ import annotations

from pathlib import Path
import sys

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from drosophila_pd.metrics.locomotion import (  # noqa: E402
    check_locomotion_pass_criteria,
    compute_locomotion_metrics,
)


def test_compute_locomotion_metrics_reports_displacement_and_speed():
    positions = np.array(
        [
            [0.0, 0.0, 1.0],
            [0.3, 0.4, 1.1],
            [0.6, 0.8, 1.2],
        ]
    )
    quaternions = np.tile(np.array([[1.0, 0.0, 0.0, 0.0]]), (3, 1))
    actions = np.ones((2, 42)) * 0.25
    adhesion = np.array(
        [
            [True, False, True, False, True, False],
            [False, False, True, True, True, False],
        ]
    )

    metrics = compute_locomotion_metrics(
        thorax_positions=positions,
        thorax_quaternions=quaternions,
        joint_angle_actions=actions,
        adhesion_onoff=adhesion,
        timestep_s=0.1,
        requested_duration_s=0.2,
        instability_height_floor_mm=-1.0,
    )

    assert metrics["step_count"] == 2
    assert metrics["planar_displacement_mm"] == 1.0
    assert metrics["planar_path_length_mm"] == 1.0
    assert metrics["trajectory_efficiency"] == 1.0
    assert metrics["mean_planar_speed_mm_s"] == 5.0
    assert metrics["mean_planar_displacement_speed_mm_s"] == 5.0
    assert metrics["mean_planar_path_speed_mm_s"] == 5.0
    assert metrics["metric_definition_version"] == "locomotion-metrics-2"
    assert metrics["body_height_mm"]["min"] == 1.0
    assert metrics["observations_are_finite"] is True
    assert metrics["controller_action_summary"]["adhesion"]["available"] is True
    assert metrics["controller_action_summary"]["adhesion"]["transition_count_by_leg"][
        0
    ] == 1


def test_nonfinite_observations_fail_finite_observation_check():
    positions = np.array(
        [
            [0.0, 0.0, 1.0],
            [np.nan, 0.0, 1.0],
        ]
    )
    quaternions = np.tile(np.array([[1.0, 0.0, 0.0, 0.0]]), (2, 1))
    actions = np.zeros((1, 42))

    metrics = compute_locomotion_metrics(
        thorax_positions=positions,
        thorax_quaternions=quaternions,
        joint_angle_actions=actions,
        adhesion_onoff=None,
        timestep_s=0.1,
        requested_duration_s=0.1,
        instability_height_floor_mm=-1.0,
    )
    checks = check_locomotion_pass_criteria(
        metrics=metrics,
        expected_step_count=1,
        expected_actuated_dofs=42,
        observed_actuated_dofs=42,
        expected_adhesion_actuators=0,
        observed_adhesion_actuators=0,
        deterministic_seed_recorded=True,
    )

    assert metrics["observations_are_finite"] is False
    assert checks["required_observations_finite"]["pass"] is False


def test_body_height_check_records_below_floor_semantics():
    positions = np.array(
        [
            [0.0, 0.0, 1.0],
            [0.1, 0.0, 1.1],
        ]
    )
    quaternions = np.tile(np.array([[1.0, 0.0, 0.0, 0.0]]), (2, 1))
    actions = np.zeros((1, 42))

    metrics = compute_locomotion_metrics(
        thorax_positions=positions,
        thorax_quaternions=quaternions,
        joint_angle_actions=actions,
        adhesion_onoff=None,
        timestep_s=0.1,
        requested_duration_s=0.1,
        instability_height_floor_mm=-1.0,
    )
    checks = check_locomotion_pass_criteria(
        metrics=metrics,
        expected_step_count=1,
        expected_actuated_dofs=42,
        observed_actuated_dofs=42,
        expected_adhesion_actuators=0,
        observed_adhesion_actuators=0,
        deterministic_seed_recorded=True,
    )

    assert metrics["body_height_below_floor"] is False
    assert checks["body_height_below_numerical_floor"] == {
        "expected": False,
        "observed": False,
        "pass": True,
    }
    assert "body_height_above_numerical_floor" not in checks


def test_path_speed_is_distinct_from_displacement_speed_for_a_looping_path():
    positions = np.array(
        [
            [0.0, 0.0, 1.0],
            [1.0, 0.0, 1.0],
            [0.0, 0.0, 1.0],
        ]
    )
    quaternions = np.tile(np.array([[1.0, 0.0, 0.0, 0.0]]), (3, 1))
    actions = np.zeros((2, 42))

    metrics = compute_locomotion_metrics(
        thorax_positions=positions,
        thorax_quaternions=quaternions,
        joint_angle_actions=actions,
        adhesion_onoff=None,
        timestep_s=0.1,
        requested_duration_s=0.2,
        instability_height_floor_mm=-1.0,
    )

    assert metrics["planar_displacement_mm"] == 0.0
    assert metrics["planar_path_length_mm"] == 2.0
    assert metrics["mean_planar_displacement_speed_mm_s"] == 0.0
    assert metrics["mean_planar_path_speed_mm_s"] == 10.0


def test_metric_shape_validation_rejects_missing_initial_sample():
    positions = np.zeros((2, 3))
    quaternions = np.zeros((2, 4))
    actions = np.zeros((2, 42))

    try:
        compute_locomotion_metrics(
            thorax_positions=positions,
            thorax_quaternions=quaternions,
            joint_angle_actions=actions,
            adhesion_onoff=None,
            timestep_s=0.1,
            requested_duration_s=0.2,
            instability_height_floor_mm=-1.0,
        )
    except ValueError as exc:
        assert "one initial sample" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
