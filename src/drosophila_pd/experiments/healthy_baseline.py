"""Milestone C unperturbed locomotion baseline."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
import math
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import yaml

from drosophila_pd.anatomy.audit import (
    git_commit,
    runtime_environment,
    write_json_report,
)
from drosophila_pd.controllers.healthy_baseline import (
    CPGControllerConfig,
    build_official_cpg_controller,
)
from drosophila_pd.metrics.locomotion import (
    check_locomotion_pass_criteria,
    compute_locomotion_metrics,
)
from drosophila_pd.perturbations import (
    ActionPerturbationContext,
    ControllerPerturbationContext,
    Perturbation,
    summarize_action_transformation,
    summarize_controller_transformation,
)


DEFAULT_HEALTHY_BASELINE_CONFIG: dict[str, Any] = {
    "experiment_id": "milestone_c_unperturbed_locomotion_baseline",
    "random_seed": 0,
    "fly": {
        "name": "healthy_baseline",
        "joint_stiffness": 0.05,
        "joint_damping": 0.06,
        "passive_tarsus_stiffness": 7.5,
        "passive_tarsus_damping": 0.01,
        "add_adhesion": True,
        "adhesion_gain": 40.0,
        "colorize": False,
    },
    "actuators": {
        "type": "position",
        "gain": 45.0,
        "forcerange": [-65.0, 65.0],
        "expected_actuated_dofs": 42,
    },
    "world": {
        "type": "FlatGroundWorld",
        "spawn_position_mm": [0.0, 0.0, 0.5],
        "spawn_orientation_quat": [1.0, 0.0, 0.0, 0.0],
        "spawn_position_source": (
            "FlyGym 2.1.0 tutorial 4a_cpg_controller.ipynb uses "
            "[0, 0, 0.5] for the flat-ground CPG walking demo."
        ),
        "add_ground_contact_sensors": False,
    },
    "simulation": {
        "duration_s": 0.5,
        "timestep_s": 0.0001,
        "warmup_duration_s": 0.05,
    },
    "controller": {
        "type": "official_flygym_cpg_tripod",
        "intrinsic_frequency_hz": 12.0,
        "intrinsic_amplitude": 1.0,
        "coupling_strength": 10.0,
        "convergence_coef": 20.0,
    },
    "pass_criteria": {
        "minimum_body_height_mm": -1.0,
        "require_finite_observations": True,
        "require_finite_metrics": True,
    },
}


@dataclass(frozen=True)
class HealthyBaselineConfig:
    """Validated configuration for the Milestone C rollout."""

    data: dict[str, Any]
    controller: CPGControllerConfig

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "HealthyBaselineConfig":
        merged = _deep_merge(DEFAULT_HEALTHY_BASELINE_CONFIG, data)
        controller = CPGControllerConfig.from_mapping(merged.get("controller"))
        config = cls(data=merged, controller=controller)
        config.validate()
        return config

    def validate(self) -> None:
        _require_string("experiment_id", self.data.get("experiment_id"))
        _require_nonnegative_int("random_seed", self.random_seed)
        _require_string("fly.name", self.fly["name"])
        _require_positive("fly.joint_stiffness", self.fly["joint_stiffness"])
        _require_positive("fly.joint_damping", self.fly["joint_damping"])
        _require_positive(
            "fly.passive_tarsus_stiffness", self.fly["passive_tarsus_stiffness"]
        )
        _require_positive(
            "fly.passive_tarsus_damping", self.fly["passive_tarsus_damping"]
        )
        _require_positive("fly.adhesion_gain", self.fly["adhesion_gain"])
        if self.actuators["type"] != "position":
            raise ValueError("Milestone C currently supports position actuators only.")
        _require_positive("actuators.gain", self.actuators["gain"])
        _require_range("actuators.forcerange", self.actuators["forcerange"])
        _require_positive("simulation.duration_s", self.duration_s)
        _require_positive("simulation.timestep_s", self.timestep_s)
        _require_nonnegative_float(
            "simulation.warmup_duration_s", self.warmup_duration_s
        )
        _require_vector("world.spawn_position_mm", self.spawn_position_mm, 3)
        _require_vector("world.spawn_orientation_quat", self.spawn_orientation_quat, 4)
        if np.linalg.norm(self.spawn_orientation_quat) == 0:
            raise ValueError("world.spawn_orientation_quat must be non-zero.")

    @property
    def experiment_id(self) -> str:
        return str(self.data["experiment_id"])

    @property
    def random_seed(self) -> int:
        return int(self.data["random_seed"])

    def with_random_seed(self, seed: int) -> "HealthyBaselineConfig":
        """Return a separately validated config with one explicit seed."""

        if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
            raise ValueError("random_seed override must be a non-negative integer")
        updated = deepcopy(self.data)
        updated["random_seed"] = seed
        return HealthyBaselineConfig.from_mapping(updated)

    def with_overrides(self, overrides: Mapping[str, Any]) -> "HealthyBaselineConfig":
        """Return a separately validated config after strict dotted-path overrides."""

        if not isinstance(overrides, Mapping):
            raise ValueError("parameter overrides must be a mapping")
        updated = deepcopy(self.data)
        for raw_path, value in overrides.items():
            path = str(raw_path).strip()
            if not path:
                raise ValueError("parameter override path must not be empty")
            parts = path.split(".")
            current: Any = updated
            for part in parts[:-1]:
                if not isinstance(current, dict) or part not in current or not isinstance(current[part], dict):
                    raise ValueError(f"parameter override path does not exist: {path}")
                current = current[part]
            if not isinstance(current, dict) or parts[-1] not in current:
                raise ValueError(f"parameter override path does not exist: {path}")
            current[parts[-1]] = value
        return HealthyBaselineConfig.from_mapping(updated)

    @property
    def fly(self) -> dict[str, Any]:
        return self.data["fly"]

    @property
    def actuators(self) -> dict[str, Any]:
        return self.data["actuators"]

    @property
    def world(self) -> dict[str, Any]:
        return self.data["world"]

    @property
    def simulation(self) -> dict[str, Any]:
        return self.data["simulation"]

    @property
    def pass_criteria(self) -> dict[str, Any]:
        return self.data["pass_criteria"]

    @property
    def duration_s(self) -> float:
        return float(self.simulation["duration_s"])

    @property
    def timestep_s(self) -> float:
        return float(self.simulation["timestep_s"])

    @property
    def warmup_duration_s(self) -> float:
        return float(self.simulation["warmup_duration_s"])

    @property
    def spawn_position_mm(self) -> np.ndarray:
        return np.asarray(self.world["spawn_position_mm"], dtype=float)

    @property
    def spawn_orientation_quat(self) -> np.ndarray:
        return np.asarray(self.world["spawn_orientation_quat"], dtype=float)

    def expected_step_count(self) -> int:
        return int(round(self.duration_s / self.timestep_s))

    def expected_adhesion_actuator_count(self) -> int:
        return 6 if bool(self.fly["add_adhesion"]) else 0

    def to_report(self) -> dict[str, Any]:
        report = deepcopy(self.data)
        report["controller"] = self.controller.to_report()
        return report


def load_healthy_baseline_config(path: str | Path) -> HealthyBaselineConfig:
    """Load and validate a Milestone C YAML configuration file."""

    with Path(path).open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    if not isinstance(loaded, dict):
        raise ValueError("Configuration root must be a mapping.")
    return HealthyBaselineConfig.from_mapping(loaded)


def run_locomotion(
    config: HealthyBaselineConfig,
    *,
    repo_root: str | Path | None = None,
    perturbation: Perturbation | None = None,
    condition_id: str = "unperturbed",
    include_condition_metadata: bool = False,
    apply_config_perturbation: bool = True,
) -> dict[str, Any]:
    """Execute the FlyGym locomotion pipeline and return a compact report."""

    if perturbation is not None and apply_config_perturbation:
        config = perturbation.apply_to_config(config)

    np.random.seed(config.random_seed)

    from flygym import Simulation  # noqa: PLC0415
    from flygym.compose import FlatGroundWorld  # noqa: PLC0415
    from flygym.utils.math import Rotation3D  # noqa: PLC0415
    from flygym_demo.complex_terrain import (  # noqa: PLC0415
        LocomotionAction,
        apply_locomotion_action,
        make_locomotion_fly,
    )

    fly = make_locomotion_fly(
        name=config.fly["name"],
        joint_stiffness=float(config.fly["joint_stiffness"]),
        joint_damping=float(config.fly["joint_damping"]),
        passive_tarsus_stiffness=float(config.fly["passive_tarsus_stiffness"]),
        passive_tarsus_damping=float(config.fly["passive_tarsus_damping"]),
        actuator_gain=float(config.actuators["gain"]),
        actuator_forcerange=tuple(float(v) for v in config.actuators["forcerange"]),
        add_adhesion=bool(config.fly["add_adhesion"]),
        adhesion_gain=float(config.fly["adhesion_gain"]),
        colorize=bool(config.fly["colorize"]),
    )
    dof_order = fly.get_actuated_jointdofs_order(config.actuators["type"])

    world = FlatGroundWorld()
    world.add_fly(
        fly,
        spawn_position=config.spawn_position_mm,
        spawn_rotation=Rotation3D("quat", config.spawn_orientation_quat.tolist()),
        add_ground_contact_sensors=bool(config.world["add_ground_contact_sensors"]),
    )
    sim = Simulation(world, timestep=config.timestep_s)
    sim.reset()

    controller, preprogrammed_steps = build_official_cpg_controller(
        timestep=sim.timestep,
        random_seed=config.random_seed,
        output_dof_order=dof_order,
        config=config.controller,
    )
    pre_perturbation_controller_state = _controller_transformation_snapshot(controller)
    if perturbation is not None:
        controller = perturbation.apply_to_controller(
            controller,
            ControllerPerturbationContext(
                condition_id=condition_id,
                timestep_s=float(sim.timestep),
                random_seed=config.random_seed,
                expected_joint_angle_count=len(dof_order),
            ),
        )
    post_perturbation_controller_state = _controller_transformation_snapshot(controller)

    initial_action = LocomotionAction(
        joint_angles=preprogrammed_steps.default_pose_by_dof_order(dof_order),
        adhesion_onoff=(
            np.ones(6, dtype=bool) if bool(config.fly["add_adhesion"]) else None
        ),
    )
    apply_locomotion_action(sim, fly.name, initial_action)
    if config.warmup_duration_s > 0:
        sim.warmup(duration_s=config.warmup_duration_s)

    thorax_index = _body_segment_index(fly, "c_thorax")
    step_count = config.expected_step_count()
    thorax_positions = np.full((step_count + 1, 3), np.nan, dtype=float)
    thorax_quaternions = np.full((step_count + 1, 4), np.nan, dtype=float)
    controller_joint_angle_actions = np.full(
        (step_count, len(dof_order)), np.nan, dtype=float
    )
    joint_angle_actions = np.full((step_count, len(dof_order)), np.nan, dtype=float)
    controller_adhesion_onoff = (
        np.zeros((step_count, 6), dtype=bool)
        if bool(config.fly["add_adhesion"])
        else None
    )
    adhesion_onoff = (
        np.zeros((step_count, 6), dtype=bool)
        if bool(config.fly["add_adhesion"])
        else None
    )
    cpg_phases = np.full((step_count + 1, 6), np.nan, dtype=float)

    orientation_invalid_count = 0
    orientation_fallback_count = 0
    initial_orientation_invalid = _collect_thorax_state(
        sim,
        fly.name,
        thorax_index,
        thorax_positions,
        thorax_quaternions,
        0,
    )
    orientation_invalid_count += int(initial_orientation_invalid)
    if initial_orientation_invalid:
        # FlyGym can expose an uninitialized quaternion at t=0 immediately
        # after reset.  The declared spawn orientation is an explicit initial
        # condition, not a previous observation, so using it here does not
        # hide a later orientation failure or repeat a stale value.
        spawn_quaternion = np.asarray(config.spawn_orientation_quat, dtype=float)
        if spawn_quaternion.shape == (4,) and np.isfinite(spawn_quaternion).all():
            thorax_quaternions[0] = spawn_quaternion / np.linalg.norm(spawn_quaternion)
            orientation_fallback_count = 1
    cpg_phases[0] = controller.cpg_network.curr_phases % (2 * np.pi)

    for step_index in range(step_count):
        controller_action = controller.step()
        action = _apply_action_perturbation(
            controller_action,
            perturbation=perturbation,
            condition_id=condition_id,
            step_index=step_index,
            timestep_s=float(sim.timestep),
            random_seed=config.random_seed,
            expected_joint_angle_count=len(dof_order),
        )
        apply_locomotion_action(sim, fly.name, action)
        sim.step()

        controller_joint_angle_actions[step_index] = controller_action.joint_angles
        if controller_adhesion_onoff is not None:
            controller_adhesion_onoff[step_index] = controller_action.adhesion_onoff
        joint_angle_actions[step_index] = action.joint_angles
        if adhesion_onoff is not None:
            adhesion_onoff[step_index] = action.adhesion_onoff
        orientation_invalid_count += int(
            _collect_thorax_state(
                sim,
                fly.name,
                thorax_index,
                thorax_positions,
                thorax_quaternions,
                step_index + 1,
            )
        )
        cpg_phases[step_index + 1] = controller.cpg_network.curr_phases % (
            2 * np.pi
        )

    metrics = compute_locomotion_metrics(
        thorax_positions=thorax_positions,
        thorax_quaternions=thorax_quaternions,
        joint_angle_actions=joint_angle_actions,
        adhesion_onoff=adhesion_onoff,
        timestep_s=sim.timestep,
        requested_duration_s=config.duration_s,
        instability_height_floor_mm=float(
            config.pass_criteria["minimum_body_height_mm"]
        ),
    )
    skeleton_summary = _skeleton_summary(fly)
    actuator_summary = _actuator_summary(fly, sim)
    action_transformation_summary = summarize_action_transformation(
        controller_joint_angle_actions=controller_joint_angle_actions,
        applied_joint_angle_actions=joint_angle_actions,
        controller_adhesion_onoff=controller_adhesion_onoff,
        applied_adhesion_onoff=adhesion_onoff,
        expected_joint_angle_count=len(dof_order),
        perturbation_metadata=(
            perturbation.metadata() if perturbation is not None else None
        ),
    )
    controller_transformation_summary = summarize_controller_transformation(
        pre_controller_state=pre_perturbation_controller_state,
        post_controller_state=post_perturbation_controller_state,
        perturbation_metadata=(
            perturbation.metadata() if perturbation is not None else None
        ),
    )
    checks = check_locomotion_pass_criteria(
        metrics=metrics,
        expected_step_count=step_count,
        expected_actuated_dofs=int(config.actuators["expected_actuated_dofs"]),
        observed_actuated_dofs=actuator_summary["position_actuator_count"],
        expected_adhesion_actuators=config.expected_adhesion_actuator_count(),
        observed_adhesion_actuators=actuator_summary["adhesion_actuator_count"],
        deterministic_seed_recorded=config.random_seed is not None,
    )

    report = {
        "timestamp": datetime.now(UTC).isoformat(),
        "git_commit": git_commit(repo_root),
        **runtime_environment(),
        "experiment_id": config.experiment_id,
        "configuration": config.to_report(),
        "controller": {
            **config.controller.to_report(),
            "output_dof_count": len(dof_order),
            "initial_cpg_phases_rad": _json_float_list(cpg_phases[0]),
            "final_cpg_phases_rad": _json_float_list(cpg_phases[-1]),
        },
        "skeleton_materialization_summary": skeleton_summary,
        "actuator_summary": actuator_summary,
        "simulation_summary": {
            "world_type": "flygym.compose.world.flat_ground.FlatGroundWorld",
            "simulation_type": "flygym.simulation.Simulation",
            "timestep_s": float(sim.timestep),
            "requested_duration_s": config.duration_s,
            "executed_duration_s": metrics["executed_duration_s"],
            "step_count": step_count,
            "warmup_duration_s": config.warmup_duration_s,
            "rendering_enabled": False,
            "ground_contact_sensors_enabled": bool(
                config.world["add_ground_contact_sensors"]
            ),
            "orientation_invalid_samples": orientation_invalid_count,
            "orientation_fallback_samples": orientation_fallback_count,
            "orientation_qc_policy": (
                "invalid quaternion samples after initialization are retained as NaN; "
                "only an invalid t=0 readout may use the declared spawn orientation, "
                "and that fallback is recorded separately"
            ),
        },
        "raw_observations": {
            "stored_in_report": False,
            "summary": {
                "thorax_position_samples": int(thorax_positions.shape[0]),
                "thorax_quaternion_samples": int(thorax_quaternions.shape[0]),
                "joint_action_samples": int(joint_angle_actions.shape[0]),
                "adhesion_action_samples": (
                    int(adhesion_onoff.shape[0])
                    if adhesion_onoff is not None
                    else 0
                ),
            },
        },
        "derived_locomotion_metrics": metrics,
        "checks": checks,
        "overall_pass": all(check["pass"] for check in checks.values()),
        "scientific_scope": _locomotion_scientific_scope(perturbation),
    }
    if include_condition_metadata:
        report.update(
            {
                "condition_id": condition_id,
                "perturbation": (
                    perturbation.metadata() if perturbation is not None else None
                ),
                "controller_transformation_summary": controller_transformation_summary,
                "action_transformation_summary": action_transformation_summary,
            }
        )
    sim.close()
    return report


def run_healthy_baseline(
    config: HealthyBaselineConfig, *, repo_root: str | Path | None = None
) -> dict[str, Any]:
    """Execute the canonical unperturbed baseline and return a report."""

    return run_locomotion(
        config,
        repo_root=repo_root,
        perturbation=None,
        condition_id="unperturbed",
        include_condition_metadata=False,
    )


def build_healthy_baseline_unavailable_report(
    error: BaseException,
    *,
    config: HealthyBaselineConfig,
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    """Build a report for environments where FlyGym execution is unavailable."""

    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "git_commit": git_commit(repo_root),
        **runtime_environment(),
        "experiment_id": config.experiment_id,
        "configuration": config.to_report(),
        "overall_pass": False,
        "local_execution": "NOT VERIFIED",
        "error_type": type(error).__name__,
        "error": str(error),
        "scientific_scope": (
            "Milestone C was not executed in this environment. No locomotion "
            "baseline PASS is claimed."
        ),
    }


def _actuator_summary(fly: Any, sim: Any) -> dict[str, Any]:
    return {
        "actuator_type": "position",
        "position_actuator_count": len(fly.get_actuated_jointdofs_order("position")),
        "adhesion_actuator_count": len(getattr(fly, "leg_to_adhesionactuator", {})),
        "compiled_mj_model_nu": int(sim.mj_model.nu),
    }


def _body_segment_index(fly: Any, body_segment_name: str) -> int:
    body_segment_class = type(fly).BODY_SEGMENT_CLASS
    body_segment = body_segment_class(body_segment_name)
    return fly.get_bodysegs_order().index(body_segment)


def _collect_thorax_state(
    sim: Any,
    fly_name: str,
    thorax_index: int,
    positions: np.ndarray,
    quaternions: np.ndarray,
    sample_index: int,
) -> bool:
    positions[sample_index] = sim.get_body_positions(fly_name)[thorax_index]
    observed_quaternion = np.asarray(
        sim.get_body_rotations(fly_name)[thorax_index], dtype=float
    )
    invalid = (
        observed_quaternion.shape != (4,)
        or not np.isfinite(observed_quaternion).all()
        or float(np.linalg.norm(observed_quaternion)) <= 1e-12
    )
    if invalid:
        quaternions[sample_index] = np.nan
        return True
    quaternions[sample_index] = observed_quaternion
    return False


def _deep_merge(defaults: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(defaults)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _locomotion_scientific_scope(perturbation: Perturbation | None) -> str:
    if perturbation is None:
        return (
            "Milestone C validates an unperturbed deterministic FlyGym locomotion "
            "simulation baseline for future software comparisons. It is not a "
            "Parkinson's disease model and is not biological validation."
        )
    return (
        "This condition report records a controlled simulation perturbation "
        "condition for software comparison. It is not a Parkinson's disease model "
        "and is not biological validation."
    )


def _apply_action_perturbation(
    action: Any,
    *,
    perturbation: Perturbation | None,
    condition_id: str,
    step_index: int,
    timestep_s: float,
    random_seed: int,
    expected_joint_angle_count: int,
) -> Any:
    if perturbation is None:
        return action
    return perturbation.apply_to_action(
        action,
        ActionPerturbationContext(
            condition_id=condition_id,
            step_index=step_index,
            time_s=step_index * timestep_s,
            timestep_s=timestep_s,
            random_seed=random_seed,
            expected_joint_angle_count=expected_joint_angle_count,
        ),
    )


def _controller_transformation_snapshot(controller: Any) -> dict[str, Any]:
    cpg_network = getattr(controller, "cpg_network", None)
    coupling_weights = getattr(cpg_network, "coupling_weights", None)
    if coupling_weights is None:
        coupling_weights = np.empty((0, 0), dtype=float)
    return {
        "cpg_coupling_weights": np.asarray(coupling_weights, dtype=float).copy(),
    }


def _json_float_list(values: np.ndarray) -> list[float | None]:
    result = []
    for value in np.asarray(values, dtype=float).ravel():
        as_float = float(value)
        result.append(as_float if math.isfinite(as_float) else None)
    return result


def _require_nonnegative_float(name: str, value: Any) -> None:
    if float(value) < 0:
        raise ValueError(f"{name} must be non-negative.")


def _require_nonnegative_int(name: str, value: Any) -> None:
    if int(value) < 0:
        raise ValueError(f"{name} must be non-negative.")


def _require_positive(name: str, value: Any) -> None:
    if float(value) <= 0:
        raise ValueError(f"{name} must be positive.")


def _require_range(name: str, value: Any) -> None:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f"{name} must contain exactly two values.")
    low, high = (float(item) for item in value)
    if low >= high:
        raise ValueError(f"{name} lower bound must be less than upper bound.")


def _require_string(name: str, value: Any) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string.")


def _require_vector(name: str, value: Any, length: int) -> None:
    array = np.asarray(value, dtype=float)
    if array.shape != (length,) or not np.isfinite(array).all():
        raise ValueError(f"{name} must be a finite vector of length {length}.")


def _skeleton_summary(fly: Any) -> dict[str, Any]:
    skeleton = fly.skeleton
    jointdofs = fly.get_jointdofs_order()
    return {
        "fly_type": f"{type(fly).__module__}.{type(fly).__name__}",
        "skeleton_is_materialized": skeleton is not None,
        "skeleton_type": (
            f"{type(skeleton).__module__}.{type(skeleton).__name__}"
            if skeleton is not None
            else None
        ),
        "joint_preset": "JointPreset.LEGS_ONLY",
        "axis_order": "AxisOrder.YAW_PITCH_ROLL",
        "jointdof_count": len(jointdofs),
        "mjcf_joint_mapping_count": len(getattr(fly, "jointdof_to_mjcfjoint", {})),
        "neutral_angle_mapping_count": len(
            getattr(fly, "jointdof_to_neutralangle", {})
        ),
    }


__all__ = [
    "DEFAULT_HEALTHY_BASELINE_CONFIG",
    "HealthyBaselineConfig",
    "build_healthy_baseline_unavailable_report",
    "load_healthy_baseline_config",
    "run_healthy_baseline",
    "run_locomotion",
    "write_json_report",
]
