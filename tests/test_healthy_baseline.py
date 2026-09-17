from __future__ import annotations

from importlib import import_module
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import sys

import numpy as np
import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from drosophila_pd.controllers.healthy_baseline import CPGControllerConfig  # noqa: E402
from drosophila_pd.experiments.healthy_baseline import (  # noqa: E402
    DEFAULT_HEALTHY_BASELINE_CONFIG,
    HealthyBaselineConfig,
    build_healthy_baseline_unavailable_report,
    load_healthy_baseline_config,
    run_healthy_baseline,
)
from drosophila_pd.experiments import healthy_baseline as healthy_baseline_module  # noqa: E402


def test_default_config_records_official_cpg_baseline_choices():
    config = HealthyBaselineConfig.from_mapping({})

    assert config.experiment_id == "milestone_c_unperturbed_locomotion_baseline"
    assert config.random_seed == 0
    assert config.duration_s == 0.5
    assert config.timestep_s == 0.0001
    assert config.expected_step_count() == 5000
    assert config.spawn_position_mm.tolist() == [0.0, 0.0, 0.5]
    assert config.controller.controller_type == "official_flygym_cpg_tripod"
    assert config.actuators["expected_actuated_dofs"] == 42


def test_yaml_config_loads_and_validates():
    config = load_healthy_baseline_config(
        REPO_ROOT / "configs" / "experiments" / "healthy_baseline.yaml"
    )

    assert config.to_report()["world"]["type"] == "FlatGroundWorld"
    assert "4a_cpg_controller" in config.to_report()["world"]["spawn_position_source"]


def test_config_validation_rejects_invalid_controller_type():
    bad = {"controller": {"type": "invented_controller"}}

    with pytest.raises(ValueError, match="official FlyGym tripod CPG"):
        HealthyBaselineConfig.from_mapping(bad)


def test_config_validation_rejects_invalid_spawn_orientation():
    bad = {"world": {"spawn_orientation_quat": [0.0, 0.0, 0.0, 0.0]}}

    with pytest.raises(ValueError, match="non-zero"):
        HealthyBaselineConfig.from_mapping(bad)


def test_cpg_controller_config_rejects_nonpositive_parameters():
    with pytest.raises(ValueError, match="intrinsic_frequency_hz"):
        CPGControllerConfig.from_mapping({"intrinsic_frequency_hz": 0.0})


def test_unavailable_report_never_claims_pass():
    config = HealthyBaselineConfig.from_mapping(DEFAULT_HEALTHY_BASELINE_CONFIG)

    report = build_healthy_baseline_unavailable_report(
        ModuleNotFoundError("No module named 'flygym'"),
        config=config,
        repo_root=REPO_ROOT,
    )

    assert report["overall_pass"] is False
    assert report["local_execution"] == "NOT VERIFIED"
    assert report["git_commit"] is not None
    assert report["python_version"] is not None
    assert report["configuration"]["controller"]["type"] == "official_flygym_cpg_tripod"
    assert "No locomotion baseline PASS is claimed" in report["scientific_scope"]


def test_invalid_orientation_is_retained_as_nan_instead_of_reusing_previous_sample():
    class SimulationStub:
        def get_body_positions(self, _name):
            return [[0.0, 0.0, 1.0]]

        def get_body_rotations(self, _name):
            return [[0.0, 0.0, 0.0, 0.0]]

    positions = np.full((1, 3), np.nan)
    quaternions = np.full((1, 4), np.nan)

    invalid = healthy_baseline_module._collect_thorax_state(
        SimulationStub(), "fly", 0, positions, quaternions, 0
    )

    assert invalid is True
    assert not np.isfinite(quaternions).any()


def test_healthy_baseline_integration_with_real_flygym_if_available():
    _skip_unless_exact_colab_like_runtime()
    config = HealthyBaselineConfig.from_mapping(
        {
            "simulation": {
                "duration_s": 0.002,
                "warmup_duration_s": 0.0,
            }
        }
    )

    report = run_healthy_baseline(config, repo_root=REPO_ROOT)

    assert report["overall_pass"]
    assert report["simulation_summary"]["step_count"] == 20
    assert report["actuator_summary"]["position_actuator_count"] == 42
    assert report["simulation_summary"]["rendering_enabled"] is False


def _skip_unless_exact_colab_like_runtime() -> None:
    try:
        flygym_version = version("flygym")
        mujoco_version = version("mujoco")
        import_module("flygym_demo")
    except (ModuleNotFoundError, PackageNotFoundError):
        pytest.skip("FlyGym locomotion integration is verified in Colab.")

    if sys.version_info[:2] != (3, 12):
        pytest.skip("Milestone C integration expects Python 3.12.")
    if flygym_version != "2.1.0" or mujoco_version != "3.9.0":
        pytest.skip("Milestone C integration expects FlyGym 2.1.0 and MuJoCo 3.9.0.")
