#!/usr/bin/env python
"""Batch: run brain-driven locomotion experiments with Extended 3D Video Rendering.

Supports configurable simulation duration and slow-motion video playback for clear
visual inspection of Parkinson gait phenotypes and robust bout statistics.

Usage on Colab:
    xvfb-run -a python scripts/run_brain_driven_with_video.py \
        --baseline-config configs/experiments/healthy_baseline.yaml \
        --bridge-dir data/bridge_scales \
        --output-dir results/brain_driven/videos \
        --duration 3.0 \
        --playback-speed 0.1 \
        --fps 25
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import UTC, datetime
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from drosophila_pd.anatomy.audit import git_commit, runtime_environment
from drosophila_pd.experiments.healthy_baseline import (
    HealthyBaselineConfig,
    _actuator_summary,
    _apply_action_perturbation,
    _body_segment_index,
    _collect_thorax_state,
    _controller_transformation_snapshot,
    _locomotion_scientific_scope,
    _skeleton_summary,
    build_official_cpg_controller,
    check_locomotion_pass_criteria,
    load_healthy_baseline_config,
)
from drosophila_pd.metrics.locomotion import compute_locomotion_metrics
from drosophila_pd.metrics.comparison import compare_locomotion_reports
from drosophila_pd.perturbations import (
    BrainDrivenPerturbation,
    ControllerPerturbationContext,
    Perturbation,
    summarize_action_transformation,
    summarize_controller_transformation,
)


def run_locomotion_with_video_capture(
    config: HealthyBaselineConfig,
    *,
    perturbation: Perturbation | None = None,
    condition_id: str = "unperturbed",
    video_output_path: Path | None = None,
    output_fps: int = 25,
    playback_speed: float = 0.1,
    duration_s: float | None = None,
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    """Execute locomotion with 3D tracking video rendering and save to MP4."""

    # Override duration if provided
    if duration_s is not None and duration_s > 0:
        config.data["simulation"]["duration_s"] = float(duration_s)

    np.random.seed(config.random_seed)

    from flygym import Simulation
    from flygym.compose import FlatGroundWorld
    from flygym.utils.math import Rotation3D
    from flygym_demo.complex_terrain import (
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

    # Attach tracking camera
    cam_name = f"{fly.name}/trackcam"
    if video_output_path is not None and hasattr(fly, "add_tracking_camera"):
        try:
            fly.add_tracking_camera(name="trackcam")
        except Exception as e:
            print(f"    [WARN] Failed to add tracking camera: {e}")

    world = FlatGroundWorld()
    world.add_fly(
        fly,
        spawn_position=config.spawn_position_mm,
        spawn_rotation=Rotation3D("quat", config.spawn_orientation_quat.tolist()),
        add_ground_contact_sensors=bool(config.world["add_ground_contact_sensors"]),
    )
    sim = Simulation(world, timestep=config.timestep_s)

    # Set up rendering
    rendering_enabled = False
    if video_output_path is not None and hasattr(sim, "set_renderer"):
        try:
            sim.set_renderer(
                cameras=cam_name,
                camera_res=(480, 640),
                playback_speed=playback_speed,
                output_fps=output_fps,
                buffer_frames=True,
            )
            rendering_enabled = True
        except Exception as err:
            print(f"    [WARN] Could not initialize renderer: {err}")

    sim.reset()

    controller, preprogrammed_steps = build_official_cpg_controller(
        timestep=sim.timestep,
        random_seed=config.random_seed,
        output_dof_order=dof_order,
        config=config.controller,
    )
    pre_controller_state = _controller_transformation_snapshot(controller)
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
    post_controller_state = _controller_transformation_snapshot(controller)

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

    _collect_thorax_state(
        sim, fly.name, thorax_index, thorax_positions, thorax_quaternions, 0
    )

    # Initial frame capture
    if rendering_enabled and hasattr(sim, "renderer") and sim.renderer is not None:
        try:
            sim.renderer.render_as_needed(sim.mj_data)
        except Exception:
            pass

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

        # Capture frame for video
        if rendering_enabled and hasattr(sim, "renderer") and sim.renderer is not None:
            try:
                sim.renderer.render_as_needed(sim.mj_data)
            except Exception:
                pass

        controller_joint_angle_actions[step_index] = controller_action.joint_angles
        if controller_adhesion_onoff is not None:
            controller_adhesion_onoff[step_index] = controller_action.adhesion_onoff
        joint_angle_actions[step_index] = action.joint_angles
        if adhesion_onoff is not None:
            adhesion_onoff[step_index] = action.adhesion_onoff

        _collect_thorax_state(
            sim, fly.name, thorax_index, thorax_positions, thorax_quaternions, step_index + 1
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
        pre_controller_state=pre_controller_state,
        post_controller_state=post_controller_state,
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

    # Save video if renderer was active
    video_saved = False
    if rendering_enabled and video_output_path is not None and hasattr(sim, "renderer") and sim.renderer is not None:
        try:
            video_output_path.parent.mkdir(parents=True, exist_ok=True)
            sim.renderer.save_video(str(video_output_path))
            video_saved = True
            print(f"    [VIDEO] Saved: {video_output_path.name} (Duration: {config.duration_s}s)")
        except Exception as err:
            print(f"    [WARN] Failed to save video: {err}")

    report = {
        "timestamp": datetime.now(UTC).isoformat(),
        "git_commit": git_commit(repo_root),
        "environment": runtime_environment(),
        "experiment_id": config.experiment_id,
        "configuration": config.to_report(),
        "skeleton": _skeleton_summary(fly),
        "actuators": actuator_summary,
        "features": {
            "rendering_enabled": rendering_enabled,
            "video_saved": video_saved,
            "video_path": str(video_output_path) if video_saved else None,
            "ground_contact_sensors_enabled": bool(
                config.world["add_ground_contact_sensors"]
            ),
        },
        "raw_observations": {
            "stored_in_report": False,
            "summary": {
                "thorax_position_samples": int(thorax_positions.shape[0]),
                "thorax_quaternion_samples": int(thorax_quaternions.shape[0]),
                "joint_action_samples": int(joint_angle_actions.shape[0]),
            },
        },
        "derived_locomotion_metrics": metrics,
        "checks": checks,
        "overall_pass": all(check["pass"] for check in checks.values()),
        "scientific_scope": _locomotion_scientific_scope(perturbation),
        "condition_id": condition_id,
        "perturbation": (
            perturbation.metadata() if perturbation is not None else None
        ),
        "controller_transformation_summary": controller_transformation_summary,
        "action_transformation_summary": action_transformation_summary,
    }

    sim.close()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run brain-driven locomotion with Extended 3D Video Rendering."
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=["pink1", "parkin", "lrrk2", "dj1", "complexI", "pink1_age25", "pink1_parkin_OE_age25"],
        help="Models to run.",
    )
    parser.add_argument(
        "--baseline-config",
        type=Path,
        default=REPO_ROOT / "configs" / "experiments" / "healthy_baseline.yaml",
    )
    parser.add_argument(
        "--bridge-dir",
        type=Path,
        default=REPO_ROOT / "data" / "bridge_scales",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "results" / "brain_driven" / "videos",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=3.0,
        help="Simulation duration in seconds (default: 3.0s for clear behavior observation).",
    )
    parser.add_argument(
        "--playback-speed",
        type=float,
        default=0.1,
        help="Video playback speed multiplier (0.1 = 10x Slow-Motion).",
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=25,
        help="Video frame rate.",
    )
    args = parser.parse_args()

    baseline_config = load_healthy_baseline_config(args.baseline_config)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("BRAIN-DRIVEN LOCOMOTION — EXTENDED 3D VIDEO RENDERING PIPELINE")
    print(f"  Models: {args.models}")
    print(f"  Simulation Duration: {args.duration}s (Physical simulated time)")
    print(f"  Playback Speed: {args.playback_speed}x (Slow Motion)")
    print(f"  Output Directory: {args.output_dir}")
    print("=" * 70)

    # 1. Render Healthy Baseline Video once
    baseline_video = args.output_dir / "healthy_baseline.mp4"
    print(f"\n[1/2] Rendering Healthy Baseline ({args.duration}s) -> {baseline_video.name}...")
    baseline_report = run_locomotion_with_video_capture(
        baseline_config,
        condition_id="baseline",
        video_output_path=baseline_video,
        output_fps=args.fps,
        playback_speed=args.playback_speed,
        duration_s=args.duration,
    )

    # 2. Render Perturbed Parkinson Models
    print(f"\n[2/2] Rendering {len(args.models)} Parkinson Models ({args.duration}s each)...")
    for index, model in enumerate(args.models, start=1):
        scales_json = args.bridge_dir / f"{model}_bridge_scales.json"
        output_json = args.output_dir / f"{model}_locomotion.json"
        video_file = args.output_dir / f"{model}_perturbed.mp4"

        if not scales_json.is_file():
            print(f"  [{index}/{len(args.models)}] SKIP {model}: Missing {scales_json}")
            continue

        print(f"\n  [{index}/{len(args.models)}] Model: {model}")
        perturbation = BrainDrivenPerturbation.from_json(scales_json, name=f"brain_driven_{model}")
        print(f"    motor_scale={perturbation.motor_scale:.4f}, coupling_scale={perturbation.coupling_scale:.4f}")

        perturbed_report = run_locomotion_with_video_capture(
            baseline_config,
            perturbation=perturbation,
            condition_id="perturbed",
            video_output_path=video_file,
            output_fps=args.fps,
            playback_speed=args.playback_speed,
            duration_s=args.duration,
        )

        comparison = compare_locomotion_reports(baseline_report, perturbed_report)
        paired_report = {
            "experiment_id": f"milestone_d_{model}",
            "timestamp": datetime.now(UTC).isoformat(),
            "model": model,
            "duration_s": args.duration,
            "perturbation": perturbation.metadata(),
            "baseline": baseline_report,
            "perturbed": perturbed_report,
            "comparison": comparison,
            "overall_pass": bool(baseline_report["overall_pass"] and perturbed_report["overall_pass"]),
        }
        output_json.write_text(json.dumps(paired_report, indent=2), encoding="utf-8")
        status = "PASS" if paired_report["overall_pass"] else "FAIL"
        print(f"    [{status}] Wrote report: {output_json.name}")

    print("\n" + "=" * 70)
    print(f"  All extended videos and reports generated in: {args.output_dir}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
