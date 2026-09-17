"""Brain-driven perturbation: DN spike rates -> CPG scale -> NeuroMechFly action.

Gap 2 & Gap 3 bridge consumer. Reads a bridge_scales.json produced by
fly-brain/code/brain_body_bridge.py and applies composite interventions:

- Symmetrical or Asymmetric motor action scaling (left vs right descending drive)
- Inter-leg CPG coupling weight scaling

This composes the brain-side output (forward/turn DN rate ratios and bilateral
descending activity) into the body-side perturbation framework.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .base import (
    ActionPerturbationContext,
    CPGCouplingScalePerturbation,
    ControllerPerturbationContext,
    GlobalActionScalePerturbation,
    Perturbation,
    _copy_action,
    _validate_joint_angles,
)


@dataclass(frozen=True)
class AsymmetricActionScalePerturbation:
    """Scale joint-angle commands with distinct left-vs-right bilateral factors."""

    left_scale: float = 1.0
    right_scale: float = 1.0
    name: str = "asymmetric_action_scale"
    config_id: str | None = None

    def __post_init__(self) -> None:
        left_scale = float(self.left_scale)
        right_scale = float(self.right_scale)
        if not np.isfinite(left_scale) or left_scale < 0:
            raise ValueError("left_scale must be finite and non-negative.")
        if not np.isfinite(right_scale) or right_scale < 0:
            raise ValueError("right_scale must be finite and non-negative.")
        object.__setattr__(self, "left_scale", left_scale)
        object.__setattr__(self, "right_scale", right_scale)

    @property
    def perturbation_type(self) -> str:
        return "asymmetric_action_scale"

    def apply_to_config(self, config: Any) -> Any:
        return config

    def apply_to_controller(
        self, controller: Any, context: ControllerPerturbationContext
    ) -> Any:
        return controller

    def apply_to_action(self, action: Any, context: ActionPerturbationContext) -> Any:
        joint_angles = _validate_joint_angles(
            action.joint_angles, context.expected_joint_angle_count
        )
        scaled_angles = joint_angles.copy()
        half_dofs = context.expected_joint_angle_count // 2
        # First half corresponds to Left legs (LF, LM, LH)
        scaled_angles[:half_dofs] *= self.left_scale
        # Second half corresponds to Right legs (RF, RM, RH)
        scaled_angles[half_dofs:] *= self.right_scale
        return _copy_action(action, joint_angles=scaled_angles)

    def metadata(self) -> dict[str, Any]:
        return {
            "type": self.perturbation_type,
            "name": self.name,
            "config_id": self.config_id,
            "parameters": {
                "left_scale": self.left_scale,
                "right_scale": self.right_scale,
            },
            "intervention_target": "controller_joint_angle_commands_bilateral",
            "intervention_stage": "post_controller_pre_simulation_action",
            "deterministic": True,
            "description": (
                "Bilateral motor perturbation applying distinct left and right scaling "
                "to controller joint-angle outputs."
            ),
        }


@dataclass(frozen=True)
class BrainDrivenPerturbation:
    """Composite perturbation driven by brain-side DN spike rate ratios.

    Supports both isotropic scaling (motor_scale) and bilateral lateralized scaling
    (left_motor_scale, right_motor_scale) derived from left vs right Descending Neurons.
    """

    motor_scale: float = 1.0
    coupling_scale: float = 1.0
    left_motor_scale: float | None = None
    right_motor_scale: float | None = None
    scales_json_path: Path | None = None
    name: str = "brain_driven"
    config_id: str | None = None
    model: str = "unknown"
    biological_mechanism: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        motor_scale = float(self.motor_scale)
        coupling_scale = float(self.coupling_scale)
        left_scale = (
            float(self.left_motor_scale)
            if self.left_motor_scale is not None
            else motor_scale
        )
        right_scale = (
            float(self.right_motor_scale)
            if self.right_motor_scale is not None
            else motor_scale
        )
        scales = {
            "motor_scale": motor_scale,
            "coupling_scale": coupling_scale,
            "left_motor_scale": left_scale,
            "right_motor_scale": right_scale,
        }
        if any(not np.isfinite(value) or value < 0 for value in scales.values()):
            raise ValueError("All motor and coupling scales must be finite and non-negative.")

        object.__setattr__(self, "motor_scale", motor_scale)
        object.__setattr__(self, "coupling_scale", coupling_scale)
        object.__setattr__(self, "left_motor_scale", left_scale)
        object.__setattr__(self, "right_motor_scale", right_scale)
        if self.scales_json_path is not None:
            object.__setattr__(
                self, "scales_json_path", Path(self.scales_json_path)
            )

    @classmethod
    def from_json(cls, scales_json_path: str | Path, **kwargs: Any) -> "BrainDrivenPerturbation":
        """Load scales and biological metadata from a bridge_scales.json file."""
        path = Path(scales_json_path)
        if not path.is_file():
            raise FileNotFoundError(f"Bridge scales JSON not found: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        motor = float(data.get("motor_scale", 1.0))
        left_motor = data.get("left_motor_scale", motor)
        right_motor = data.get("right_motor_scale", motor)

        return cls(
            motor_scale=motor,
            coupling_scale=float(data.get("coupling_scale", 1.0)),
            left_motor_scale=float(left_motor) if left_motor is not None else motor,
            right_motor_scale=float(right_motor) if right_motor is not None else motor,
            scales_json_path=path,
            model=str(data.get("model", "unknown")),
            name=kwargs.pop("name", f"brain_driven_{data.get('model', 'unknown')}"),
            config_id=kwargs.pop("config_id", None),
            biological_mechanism=data.get("biological_mechanism"),
            **kwargs,
        )

    @property
    def is_asymmetric(self) -> bool:
        return self.left_motor_scale != self.right_motor_scale

    @property
    def perturbation_type(self) -> str:
        return "brain_driven"

    @property
    def _action_perturbation(self) -> Perturbation:
        if self.is_asymmetric:
            return AsymmetricActionScalePerturbation(
                left_scale=float(
                    self.left_motor_scale
                    if self.left_motor_scale is not None
                    else self.motor_scale
                ),
                right_scale=float(
                    self.right_motor_scale
                    if self.right_motor_scale is not None
                    else self.motor_scale
                ),
                name=f"{self.name}_asym_motor",
                config_id=self.config_id,
            )
        return GlobalActionScalePerturbation(
            scale=self.motor_scale,
            name=f"{self.name}_motor",
            config_id=self.config_id,
        )

    @property
    def _controller_perturbation(self) -> CPGCouplingScalePerturbation:
        return CPGCouplingScalePerturbation(
            scale=self.coupling_scale,
            name=f"{self.name}_coupling",
            config_id=self.config_id,
        )

    def apply_to_config(self, config: Any) -> Any:
        return config

    def apply_to_controller(
        self, controller: Any, context: ControllerPerturbationContext
    ) -> Any:
        return self._controller_perturbation.apply_to_controller(controller, context)

    def apply_to_action(self, action: Any, context: ActionPerturbationContext) -> Any:
        return self._action_perturbation.apply_to_action(action, context)

    def metadata(self) -> dict[str, Any]:
        meta: dict[str, Any] = {
            "type": "composite",
            "name": self.name,
            "config_id": self.config_id,
            "parameters": {
                "motor_scale": self.motor_scale,
                "left_motor_scale": self.left_motor_scale,
                "right_motor_scale": self.right_motor_scale,
                "coupling_scale": self.coupling_scale,
                "is_asymmetric": self.is_asymmetric,
                "model": self.model,
                "scales_json_path": str(self.scales_json_path) if self.scales_json_path else None,
            },
            "intervention_target": "brain_driven_motor_and_coordination",
            "intervention_stage": "controller_and_action_composite",
            "deterministic": True,
            "description": (
                "Brain-driven composite perturbation translating descending neuron (DN) "
                "population dynamics into biomechanical action scaling and CPG coupling modulation."
            ),
            "source": "bridge_scales.json from fly-brain brain_body_bridge.py",
            "components": [
                self._action_perturbation.metadata(),
                self._controller_perturbation.metadata(),
            ],
        }
        if self.biological_mechanism is not None:
            meta["biological_mechanism"] = self.biological_mechanism
        return meta


__all__ = [
    "AsymmetricActionScalePerturbation",
    "BrainDrivenPerturbation",
]
