"""Tests for upgraded Brain-to-Body Bridge (Gap 2)."""

from dataclasses import dataclass
import json
from pathlib import Path
import numpy as np
import pytest

from drosophila_pd.perturbations import (
    ActionPerturbationContext,
    AsymmetricActionScalePerturbation,
    BrainDrivenPerturbation,
)


@dataclass
class FakeAction:
    joint_angles: np.ndarray
    adhesion_onoff: np.ndarray | None = None


def _context(expected_joint_angle_count: int = 42) -> ActionPerturbationContext:
    return ActionPerturbationContext(
        condition_id="test",
        step_index=0,
        time_s=0.0,
        timestep_s=0.0001,
        random_seed=0,
        expected_joint_angle_count=expected_joint_angle_count,
    )


def test_brain_driven_symmetric_bridge(tmp_path: Path):
    scales_file = tmp_path / "test_symmetric_scales.json"
    scales_file.write_text(
        json.dumps({
            "model": "test_sym",
            "motor_scale": 1.15,
            "coupling_scale": 0.85,
            "biological_mechanism": {"gene_mutation": "Test Mutation"},
        }),
        encoding="utf-8",
    )

    pert = BrainDrivenPerturbation.from_json(scales_file)
    assert pert.motor_scale == 1.15
    assert pert.left_motor_scale == 1.15
    assert pert.right_motor_scale == 1.15
    assert pert.coupling_scale == 0.85
    assert not pert.is_asymmetric
    assert pert.biological_mechanism == {"gene_mutation": "Test Mutation"}

    # Test action transformation on 42 DOFs
    ctx = _context(expected_joint_angle_count=42)
    dummy_angles = np.ones(42, dtype=float)
    action = FakeAction(joint_angles=dummy_angles, adhesion_onoff=np.ones(6))
    out_action = pert.apply_to_action(action, ctx)

    np.testing.assert_allclose(out_action.joint_angles, dummy_angles * 1.15)


def test_brain_driven_asymmetric_bridge(tmp_path: Path):
    scales_file = tmp_path / "test_asymmetric_scales.json"
    scales_file.write_text(
        json.dumps({
            "model": "test_asym",
            "motor_scale": 1.0,
            "left_motor_scale": 1.2,
            "right_motor_scale": 0.8,
            "coupling_scale": 0.75,
        }),
        encoding="utf-8",
    )

    pert = BrainDrivenPerturbation.from_json(scales_file)
    assert pert.is_asymmetric
    assert pert.left_motor_scale == 1.2
    assert pert.right_motor_scale == 0.8

    ctx = _context(expected_joint_angle_count=42)
    dummy_angles = np.ones(42, dtype=float)
    action = FakeAction(joint_angles=dummy_angles, adhesion_onoff=np.ones(6))
    out_action = pert.apply_to_action(action, ctx)

    # First 21 (Left legs: LF, LM, LH) scaled by 1.2
    np.testing.assert_allclose(out_action.joint_angles[:21], np.ones(21) * 1.2)
    # Next 21 (Right legs: RF, RM, RH) scaled by 0.8
    np.testing.assert_allclose(out_action.joint_angles[21:], np.ones(21) * 0.8)


def test_asymmetric_perturbation_metadata():
    pert = AsymmetricActionScalePerturbation(left_scale=1.1, right_scale=0.9)
    meta = pert.metadata()
    assert meta["type"] == "asymmetric_action_scale"
    assert meta["parameters"]["left_scale"] == 1.1
    assert meta["parameters"]["right_scale"] == 0.9


def test_brain_driven_rejects_nonfinite_scales():
    with pytest.raises(ValueError, match="finite and non-negative"):
        BrainDrivenPerturbation(motor_scale=float("nan"))


def test_brain_driven_preserves_explicit_zero_bilateral_scale():
    pert = BrainDrivenPerturbation(
        motor_scale=0.8,
        left_motor_scale=0.0,
        right_motor_scale=0.25,
    )
    action = FakeAction(joint_angles=np.ones(42), adhesion_onoff=np.ones(6))

    out_action = pert.apply_to_action(action, _context())

    np.testing.assert_allclose(out_action.joint_angles[:21], 0.0)
    np.testing.assert_allclose(out_action.joint_angles[21:], 0.25)
