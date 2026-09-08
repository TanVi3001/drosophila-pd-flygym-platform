"""Run the external FlyWire brain with the repository FlyGym pipeline.

This is an optional integration runner for the separate ``phase-A-clean``
brain-body source. It does not generate observations from video or summary
reports. Every output is produced by a real BrainEngine step and a real
FlyGym/MuJoCo step.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Sequence

import numpy as np


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
SCRIPT_PATH = Path(__file__).resolve()
DEFAULT_BRAIN_ROOT = REPOSITORY_ROOT.parent / "phase-A-clean"
DEFAULT_DISEASE_CONFIG = REPOSITORY_ROOT / "configs" / "parkinson" / "computational_pd_like_demo.yaml"


class BrainBodyRunError(RuntimeError):
    """Raised when the real brain-body integration cannot be completed."""


def _resolve(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def _brain_root(args: argparse.Namespace) -> Path:
    configured = args.brain_root or os.environ.get("FLY_BRAIN_ROOT")
    return _resolve(configured or DEFAULT_BRAIN_ROOT)


def _brain_python(root: Path, configured: str | Path | None) -> Path:
    if configured:
        return _resolve(configured)
    candidates = (
        root / ".venv" / "Scripts" / "python.exe",
        root / ".venv" / "bin" / "python",
    )
    return next((path for path in candidates if path.is_file()), Path(sys.executable))


def _torch_cuda_available() -> bool:
    try:
        import torch
    except (ImportError, OSError):
        return False
    return bool(torch.cuda.is_available())


def _torch_available() -> bool:
    try:
        import torch
    except (ImportError, OSError):
        return False
    return True


def _maybe_reexec(args: argparse.Namespace, argv: Sequence[str]) -> None:
    """Re-run under the brain source environment when it owns CUDA Torch."""

    if os.environ.get("DPD_BRAIN_BODY_REEXEC") == "1":
        return
    root = _brain_root(args)
    # Missing source must return the normal validation status below. Do not
    # attempt an environment handoff for a path that cannot run anything.
    if not root.is_dir():
        return
    runtime_python = _brain_python(root, args.brain_python)
    current_python = _resolve(sys.executable)
    if runtime_python.resolve() == current_python:
        return
    needs_brain_runtime = not _torch_available() or (
        args.device != "cpu" and not _torch_cuda_available()
    )
    if runtime_python.is_file() and needs_brain_runtime:
        env = os.environ.copy()
        env["DPD_BRAIN_BODY_REEXEC"] = "1"
        result = subprocess.run(
            [str(runtime_python), str(SCRIPT_PATH), *argv],
            cwd=REPOSITORY_ROOT,
            env=env,
            check=False,
        )
        raise SystemExit(result.returncode)


def _git_commit(root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    value = result.stdout.strip()
    return value if result.returncode == 0 and value else None


def _git_worktree_dirty(root: Path) -> bool | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    return None if result.returncode != 0 else bool(result.stdout.strip())


def _load_layer(path: Path, condition: str, seed: int):
    if condition == "healthy":
        return None, None
    from drosophila_pd.experiments.calibration_runner import load_calibration_conditions

    conditions = load_calibration_conditions(path)
    selected = next((item for item in conditions if item.condition_id == condition), None)
    if selected is None:
        available = ", ".join(item.condition_id for item in conditions)
        raise BrainBodyRunError(
            f"Condition {condition!r} was not found in {path}. Available: {available}"
        )
    return replace(selected.layer, random_seed=seed), selected.description


def _require_brain_files(root: Path) -> None:
    required = (
        root / "brain_body_bridge.py",
        root / "code" / "run_pytorch.py",
        root / "data" / "2025_Completeness_783.csv",
        root / "data" / "2025_Connectivity_783.parquet",
        root / "data" / "plastic_weights.pt",
    )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise BrainBodyRunError(
            "The external brain source is incomplete. Missing: " + ", ".join(missing)
        )


def _source_imports(root: Path) -> dict[str, Any]:
    # The phase-A environment may also contain an editable package with the
    # same project name. Keep this repository's source first so all downstream
    # artifacts use the current recorder/export/analysis implementations.
    source_text = str(SOURCE_ROOT)
    if source_text in sys.path:
        sys.path.remove(source_text)
    sys.path.insert(0, source_text)
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    try:
        from brain_body_bridge import BrainBodyBridge, BrainEngine, DNRateDecoder, STIMULI
    except (ImportError, ModuleNotFoundError) as exc:
        raise BrainBodyRunError(
            "Unable to import the phase-A brain-body source. Run with its Python "
            f"environment and check the source at {root}: {exc}"
        ) from exc
    return {
        "BrainBodyBridge": BrainBodyBridge,
        "BrainEngine": BrainEngine,
        "DNRateDecoder": DNRateDecoder,
        "STIMULI": STIMULI,
    }


def _run_simulation(
    *,
    root: Path,
    output: Path,
    condition: str,
    seed: int,
    steps: int,
    stimulus: str,
    device: str,
    disease_config: Path,
    artifact_profile: str = "LEGACY",
) -> dict[str, Any]:
    if str(SOURCE_ROOT) not in sys.path:
        sys.path.insert(0, str(SOURCE_ROOT))
    imports = _source_imports(root)
    import torch

    if device == "cuda" and not torch.cuda.is_available():
        raise BrainBodyRunError("CUDA was requested, but Torch cannot access a CUDA device.")
    torch.manual_seed(seed)
    np.random.seed(seed)

    from flygym import Simulation
    from flygym.compose import ActuatorType, FlatGroundWorld
    from flygym.utils.math import Rotation3D
    from flygym_demo.complex_terrain import (
        HybridControllerObservation,
        HybridTurningController,
        PreprogrammedSteps,
        apply_locomotion_action,
        make_locomotion_fly,
        make_tripod_cpg_network,
    )
    from drosophila_pd.flygym_adapter import (
        MEMORY_SAFE_ARTIFACT_PROFILE,
        RolloutRecorder,
        export_memory_safe_rollout,
        export_rollout,
        refresh_memory_safe_manifest,
    )
    from drosophila_pd.perturbations import (
        ActionPerturbationContext,
        ControllerPerturbationContext,
    )

    layer, condition_description = _load_layer(disease_config, condition, seed)
    stimuli = imports["STIMULI"]
    if stimulus not in stimuli:
        raise BrainBodyRunError(
            f"Unknown stimulus {stimulus!r}. Choose one of: {', '.join(stimuli)}"
        )

    brain = imports["BrainEngine"](device=device)
    brain.set_stimulus(stimulus)
    decoder = imports["DNRateDecoder"](window_ms=50.0, dt_ms=0.1, max_rate=200.0)
    bridge = imports["BrainBodyBridge"](decoder)

    fly = make_locomotion_fly(name="nmf", add_adhesion=True, colorize=False)
    world = FlatGroundWorld(half_size=100)
    world.add_fly(
        fly,
        spawn_position=np.array([0.0, 0.0, 0.0]),
        spawn_rotation=Rotation3D("quat", [1.0, 0.0, 0.0, 0.0]),
        add_ground_contact_sensors=True,
    )
    simulation = Simulation(world, timestep=1e-4)
    recorder = None
    started = time.perf_counter()
    try:
        simulation.reset()
        # FlyGym resets qpos/qvel but does not always refresh derived MuJoCo
        # fields (xpos, xquat, subtree_com) until the first physics step.
        # Forward kinematics here gives the recorder a valid t=0 pose without
        # advancing time or changing the rollout's physical dynamics.
        import mujoco

        mujoco.mj_forward(simulation.mj_model, simulation.mj_data)
        dof_order = fly.get_actuated_jointdofs_order(ActuatorType.POSITION)
        controller = HybridTurningController(
            timestep=simulation.timestep,
            cpg_network=make_tripod_cpg_network(simulation.timestep, seed=seed),
            preprogrammed_steps=PreprogrammedSteps(),
            output_dof_order=dof_order,
        )
        controller.reset(seed=seed)
        if layer is not None:
            controller = layer.apply_to_controller(
                controller,
                ControllerPerturbationContext(
                    condition_id=condition,
                    timestep_s=float(simulation.timestep),
                    random_seed=seed,
                    expected_joint_angle_count=len(dof_order),
                ),
            )

        source_commit = _git_commit(root)
        metadata = {
            "dataset_id": f"brain_body_{condition}_seed_{seed}",
            "condition_id": condition,
            "condition_description": condition_description,
            "source": "phase-A-clean brain_body_bridge.py + FlyGym/MuJoCo",
            "brain_source_root": str(root),
            "brain_source_commit": source_commit,
            "brain_source_worktree_dirty": _git_worktree_dirty(root),
            "brain_checkpoint_sha256": _sha256(root / "data" / "plastic_weights.pt"),
            "repository_commit": _git_commit(REPOSITORY_ROOT),
            "repository_worktree_dirty": _git_worktree_dirty(REPOSITORY_ROOT),
            "brain_device": str(brain.device),
            "brain_neuron_count": int(brain.num_neurons),
            "brain_synapse_count": int(brain.model.weights._nnz()),
            "stimulus": stimulus,
            "random_seed": seed,
            "timestep_s": float(simulation.timestep),
            "scientific_scope": (
                "Real brain-body computational locomotion rollout. The condition "
                "is not biological Parkinson validation or clinical evidence."
            ),
        }
        recorder = RolloutRecorder(
            simulation,
            fly.name,
            fly=fly,
            timestep=float(simulation.timestep),
            simulation_metadata=metadata,
        )
        recorder.record()
        action_history: list[Any] = []
        print(
            f"Running {condition}: {steps} FlyGym steps, stimulus={stimulus}, "
            f"brain_device={brain.device}",
            flush=True,
        )
        for step_index in range(steps):
            brain.step()
            decoder.update(brain.get_dn_spikes())
            drive = bridge.compute_drive(dt=float(simulation.timestep))
            controller_action = controller.step(
                drive, HybridControllerObservation.from_sim(simulation, fly.name)
            )
            action = controller_action
            if layer is not None:
                action = layer.apply_to_action(
                    controller_action,
                    ActionPerturbationContext(
                        condition_id=condition,
                        step_index=step_index,
                        time_s=step_index * float(simulation.timestep),
                        timestep_s=float(simulation.timestep),
                        random_seed=seed,
                        expected_joint_angle_count=len(dof_order),
                        action_history=tuple(action_history),
                    ),
                )
            action_history.append(controller_action)
            apply_locomotion_action(simulation, fly.name, action)
            simulation.step()
            recorder.record()
            if (step_index + 1) % max(steps // 5, 1) == 0:
                print(f"Progress: {step_index + 1}/{steps}", flush=True)

        frame_count = recorder.rollout.frame_count
        if artifact_profile == MEMORY_SAFE_ARTIFACT_PROFILE:
            exported = export_memory_safe_rollout(recorder.rollout, output)
            action_history.clear()
            recorder.rollout.frames.clear()
            del action_history
            from drosophila_pd.analysis import analyze_memory_safe_rollout

            analysis = analyze_memory_safe_rollout(output, output)
            duration = time.perf_counter() - started
            scalar_metrics = analysis.metrics["scalar_metrics"]
            summary = {
                "created_at": datetime.now(UTC).isoformat(),
                "condition": condition,
                "seed": seed,
                "steps": steps,
                "frame_count": frame_count,
                "brain_device": str(brain.device),
                "brain_neuron_count": int(brain.num_neurons),
                "brain_synapse_count": int(brain.model.weights._nnz()),
                "thorax_displacement_xy_mm": scalar_metrics["thorax_displacement_xy_mm"],
                "duration_wall_s": duration,
                "artifact_profile": MEMORY_SAFE_ARTIFACT_PROFILE,
                "rollout_files": exported.files,
                "analysis_files": {key: str(value) for key, value in analysis.files.items()},
                "biomarker_status": "SKIPPED_OPTIONAL_POSTPROCESS",
                "viewer_export": "SKIPPED_NOT_REQUIRED_FOR_GATE24E_PRIMARY_VALIDATION",
                "viewer_is_scientific_metric": False,
                "video": False,
                "full_frame_rollout_json": False,
                "scientific_scope": metadata["scientific_scope"],
            }
            (output / "brain_body_summary.json").write_text(
                json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8"
            )
            refresh_memory_safe_manifest(output)
            return summary

        exported = export_rollout(recorder.rollout, output)
        from drosophila_pd.analysis import analyze_rollout
        from drosophila_pd.biomarkers import write_biomarker_report
        from drosophila_pd.viewer_export import export_viewer_pose, validate_pose_document

        analysis = analyze_rollout(output, output)
        biomarkers = write_biomarker_report(output, output / "biomarkers")
        pose_result = export_viewer_pose(output, output / "viewer_pose.json")
        validate_pose_document(pose_result.document)
        from build_viewer_bundle import build_bundle

        bundle_dir, bundle_archive, _ = build_bundle(
            output / "viewer_pose.json",
            output=output / "viewer_bundle.zip",
            web_root=REPOSITORY_ROOT / "web",
        )
        if not bundle_dir.is_dir() or not bundle_archive.is_file():
            raise BrainBodyRunError("Viewer bundle was not created.")
        duration = time.perf_counter() - started
        positions = np.asarray([frame.thorax for frame in recorder.rollout.frames], dtype=float)
        displacement = float(np.linalg.norm(positions[-1, :2] - positions[0, :2]))
        summary = {
            "created_at": datetime.now(UTC).isoformat(),
            "condition": condition,
            "seed": seed,
            "steps": steps,
            "frame_count": recorder.rollout.frame_count,
            "brain_device": str(brain.device),
            "brain_neuron_count": int(brain.num_neurons),
            "brain_synapse_count": int(brain.model.weights._nnz()),
            "thorax_displacement_xy_mm": displacement,
            "duration_wall_s": duration,
            "rollout_files": exported.files,
            "analysis_files": {key: str(value) for key, value in analysis.files.items()},
            "biomarker_count": len(biomarkers.biomarkers),
            "viewer_pose": str(output / "viewer_pose.json"),
            "viewer_bundle": str(bundle_archive),
            "scientific_scope": metadata["scientific_scope"],
        }
        (output / "brain_body_summary.json").write_text(
            json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8"
        )
        return summary
    finally:
        close = getattr(simulation, "close", None)
        if callable(close):
            close()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_final_manifest(output: Path) -> None:
    files = {}
    for path in sorted(output.rglob("*")):
        if path.is_file() and path.name not in {"brain_body_manifest.json"}:
            files[str(path.relative_to(output)).replace("\\", "/")] = {
                "byte_size": path.stat().st_size,
                "sha256": _sha256(path),
            }
    manifest = {
        "schema_version": "brain-body-run-1",
        "created_at": datetime.now(UTC).isoformat(),
        "files": files,
        "scientific_scope": (
            "Artifact inventory for a real brain-body computational locomotion run; "
            "not biological Parkinson validation."
        ),
    }
    (output / "brain_body_manifest.json").write_text(
        json.dumps(manifest, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )


def _write_comparison_if_requested(output: Path, args_compare: Path | None) -> None:
    """Compare analysis metrics without creating or changing simulation data."""

    if args_compare is None:
        return
    baseline_path = args_compare / "metrics" / "metrics.json"
    condition_path = output / "metrics" / "metrics.json"
    if not baseline_path.is_file() or not condition_path.is_file():
        raise BrainBodyRunError("Comparison requires metrics/metrics.json in both runs.")
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    condition = json.loads(condition_path.read_text(encoding="utf-8"))
    baseline_metrics = baseline.get("scalar_metrics", {})
    condition_metrics = condition.get("scalar_metrics", {})
    rows = []
    for key in sorted(set(baseline_metrics) | set(condition_metrics)):
        left = baseline_metrics.get(key)
        right = condition_metrics.get(key)
        if isinstance(left, (int, float)) and isinstance(right, (int, float)):
            rows.append({"metric": key, "baseline": left, "condition": right, "delta": right - left})
    payload = {
        "baseline": str(args_compare),
        "condition": str(output),
        "rows": rows,
        "scientific_scope": "Computational metric comparison only; no biological interpretation.",
    }
    (output / "comparison.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    lines = [
        "# Brain-Body Metric Comparison",
        "",
        "This is a computational locomotion comparison. It is not biological validation or a clinical result.",
        "",
        "| Metric | Baseline | Condition | Delta |",
        "| --- | ---: | ---: | ---: |",
    ]
    lines.extend(f"| `{row['metric']}` | `{row['baseline']}` | `{row['condition']}` | `{row['delta']}` |" for row in rows)
    (output / "comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brain-root", type=Path, default=None, help="Root of the checked-out phase-A brain source.")
    parser.add_argument("--brain-python", type=Path, default=None, help="Python executable for the brain source environment.")
    parser.add_argument("--condition", choices=("healthy", "computational_pd_like_demo"), default="healthy")
    parser.add_argument("--disease-config", type=Path, default=DEFAULT_DISEASE_CONFIG)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--steps", type=int, default=1000)
    parser.add_argument("--stimulus", default="p9")
    parser.add_argument("--device", choices=("auto", "cuda", "cpu"), default="auto")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--compare-to", type=Path, default=None, help="Optional healthy run directory for metric comparison.")
    parser.add_argument(
        "--artifact-profile",
        choices=("LEGACY", "GATE24E_MEMORY_SAFE"),
        default="LEGACY",
        help="Artifact profile; legacy remains the default.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    args = parser.parse_args(raw_argv)
    if args.steps <= 0:
        parser.error("--steps must be positive")
    if args.seed < 0:
        parser.error("--seed must be non-negative")
    _maybe_reexec(args, raw_argv)
    if str(SOURCE_ROOT) not in sys.path:
        sys.path.insert(0, str(SOURCE_ROOT))
    root = _brain_root(args)
    output = _resolve(args.output)
    disease_config = _resolve(args.disease_config)
    if not root.is_dir():
        print(f"ERROR: brain source not found: {root}", file=sys.stderr)
        return 2
    try:
        _require_brain_files(root)
        output.mkdir(parents=True, exist_ok=True)
        selected_device = "cuda" if args.device == "auto" and _torch_cuda_available() else args.device
        if selected_device == "auto":
            selected_device = "cpu"
        summary = _run_simulation(
            root=root,
            output=output,
            condition=args.condition,
            seed=args.seed,
            steps=args.steps,
            stimulus=args.stimulus,
            device=selected_device,
            disease_config=disease_config,
            artifact_profile=args.artifact_profile,
        )
        if args.compare_to is not None:
            _write_comparison_if_requested(output, _resolve(args.compare_to))
        _write_final_manifest(output)
    except (BrainBodyRunError, ImportError, ModuleNotFoundError, OSError, TypeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2, allow_nan=False))
    print(f"READY: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
