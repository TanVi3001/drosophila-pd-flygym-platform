"""Tests for Gap 3: Extended Bout, Pause and Turning Metrics."""

import numpy as np
import pytest

from drosophila_pd.metrics.locomotion import compute_locomotion_metrics
from drosophila_pd.metrics.comparison import compare_locomotion_reports


def test_locomotion_metrics_computes_bouts_and_turning():
    n_samples = 101
    timestep_s = 0.01

    # Linear forward motion
    positions = np.zeros((n_samples, 3))
    positions[:, 0] = np.linspace(0.0, 10.0, n_samples)  # 10 mm forward
    positions[:, 2] = 0.95  # Height 0.95 mm

    # Stationary quaternions
    quaternions = np.zeros((n_samples, 4))
    quaternions[:, 0] = 1.0  # Identity quat (w=1, x=0, y=0, z=0)

    # Actions
    actions = np.zeros((n_samples - 1, 42))

    metrics = compute_locomotion_metrics(
        thorax_positions=positions,
        thorax_quaternions=quaternions,
        joint_angle_actions=actions,
        adhesion_onoff=None,
        timestep_s=timestep_s,
        requested_duration_s=1.0,
        instability_height_floor_mm=-1.0,
    )

    assert "walking_duty_cycle" in metrics
    assert "walking_bout_count" in metrics
    assert "pause_bout_count" in metrics
    assert "walking_duration_s" in metrics
    assert "pause_duration_s" in metrics
    assert "cumulative_turning_rad" in metrics
    assert "left_right_asymmetry" in metrics
    assert "yaw_rate_mean_rad_s" in metrics

    # Continuous movement -> duty cycle should be 1.0
    assert metrics["walking_duty_cycle"] == 1.0
    assert metrics["walking_bout_count"] == 1
    assert metrics["pause_bout_count"] == 0
    assert metrics["cumulative_turning_rad"] == 0.0


def test_comparison_includes_extended_scalars():
    baseline_metrics = {
        "planar_displacement_mm": 10.0,
        "mean_planar_speed_mm_s": 10.0,
        "heading_yaw_change_rad": 0.0,
        "body_height_mm": {"min": 0.9, "mean": 0.95, "max": 1.0},
        "controller_action_summary": {
            "joint_angle_action": {"mean": 0.5},
            "joint_angle_action_abs": {"mean": 0.5},
            "adhesion": {"available": False, "duty_factor_by_leg": None, "transition_count_by_leg": None},
        },
        "walking_duty_cycle": 1.0,
        "pause_bout_count": 0,
        "cumulative_turning_rad": 0.1,
    }
    perturbed_metrics = {
        "planar_displacement_mm": 8.0,
        "mean_planar_speed_mm_s": 8.0,
        "heading_yaw_change_rad": 0.2,
        "body_height_mm": {"min": 0.85, "mean": 0.90, "max": 0.95},
        "controller_action_summary": {
            "joint_angle_action": {"mean": 0.4},
            "joint_angle_action_abs": {"mean": 0.4},
            "adhesion": {"available": False, "duty_factor_by_leg": None, "transition_count_by_leg": None},
        },
        "walking_duty_cycle": 0.8,
        "pause_bout_count": 2,
        "cumulative_turning_rad": 0.3,
    }

    base_report = {"derived_locomotion_metrics": baseline_metrics}
    pert_report = {"derived_locomotion_metrics": perturbed_metrics}

    comparison = compare_locomotion_reports(base_report, pert_report)
    scalars = comparison["scalars"]

    assert "walking_duty_cycle" in scalars
    assert scalars["walking_duty_cycle"]["absolute_delta"] == pytest.approx(-0.2)
    assert "pause_bout_count" in scalars
    assert scalars["pause_bout_count"]["absolute_delta"] == 2
    assert "cumulative_turning_rad" in scalars
    assert scalars["cumulative_turning_rad"]["absolute_delta"] == pytest.approx(0.2)
