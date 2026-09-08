"""Regression tests for the explicit Gate24 memory-safe artifact profile."""

from __future__ import annotations

import json
from pathlib import Path
import tracemalloc

import numpy as np

from drosophila_pd.analysis import analyze_memory_safe_rollout
from drosophila_pd.flygym_adapter import (
    MEMORY_SAFE_ARTIFACT_PROFILE,
    ObservationFrame,
    RolloutData,
    export_memory_safe_rollout,
    export_rollout,
)


def _rollout(frame_count: int = 24) -> RolloutData:
    frames = []
    for index in range(frame_count):
        position = np.asarray([index * 0.2, (index % 3) * 0.05, 0.5], dtype=np.float64)
        frames.append(
            ObservationFrame(
                timestamp_s=index * 0.1,
                step=index,
                thorax=position,
                com=position + [0.0, 0.0, 0.1],
                orientation=np.asarray([1.0, 0.0, 0.0, 0.0]),
                body_positions=np.asarray([position, position + [0.1, 0.0, 0.0]]),
                body_orientations=np.asarray([[1.0, 0.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0]]),
                joint_positions=np.asarray([index * 0.01, -index * 0.01]),
                joint_velocity=np.asarray([0.1, -0.1]),
                joint_acceleration=np.asarray([0.0, 0.0]),
                contact={"found": np.asarray([index % 2, (index + 1) % 2], dtype=np.float64)},
                actuator={"angles": np.asarray([index * 0.01, 0.0], dtype=np.float64)},
            )
        )
    return RolloutData(
        frames=frames,
        metadata={"dataset_id": "synthetic_gate24e", "timestep_s": 0.1},
    )


def test_memory_safe_export_never_calls_full_frame_serializers(tmp_path: Path, monkeypatch) -> None:
    rollout = _rollout()

    def fail(*_args, **_kwargs):
        raise AssertionError("full rollout/frame serialization was called")

    monkeypatch.setattr(rollout, "to_dict", fail)
    for frame in rollout.frames:
        monkeypatch.setattr(frame, "to_dict", fail)

    exported = export_memory_safe_rollout(rollout, tmp_path / "safe")

    assert set(exported.files) == {"rollout_npz", "metadata", "rollout_index", "manifest"}
    assert not (tmp_path / "safe" / "rollout.json").exists()
    assert not (tmp_path / "safe" / "rollout.csv").exists()
    index = json.loads((tmp_path / "safe" / "rollout_index.json").read_text(encoding="utf-8"))
    assert index["artifact_profile"] == MEMORY_SAFE_ARTIFACT_PROFILE
    assert index["full_frame_rollout_json"] is False


def test_memory_safe_npz_is_semantically_equivalent_to_legacy_npz(tmp_path: Path) -> None:
    rollout = _rollout()
    legacy = export_rollout(rollout, tmp_path / "legacy")
    safe = export_memory_safe_rollout(rollout, tmp_path / "safe")

    with np.load(legacy.files["rollout_npz"], allow_pickle=False) as expected:
        with np.load(safe.files["rollout_npz"], allow_pickle=False) as actual:
            assert set(expected.files) == set(actual.files)
            for name in expected.files:
                np.testing.assert_array_equal(actual[name], expected[name])


def test_memory_safe_analysis_keeps_locked_primary_metrics(tmp_path: Path) -> None:
    rollout = _rollout()
    safe = export_memory_safe_rollout(rollout, tmp_path / "safe")
    result = analyze_memory_safe_rollout(tmp_path / "safe")

    positions = np.asarray([frame.thorax for frame in rollout.frames], dtype=float)
    time_s = np.asarray([frame.timestamp_s for frame in rollout.frames], dtype=float)
    speed = np.linalg.norm(np.diff(positions[:, :2], axis=0), axis=1) / np.diff(time_s)
    assert result.metrics["median_planar_speed_mm_s"] == float(np.median(speed))
    assert result.metrics["distance_traveled_mm"] == float(np.sum(np.linalg.norm(np.diff(positions[:, :2], axis=0), axis=1)))
    assert Path(safe.files["rollout_npz"]).is_file()
    assert Path(result.files["metrics_json"]).is_file()


def test_memory_safe_export_has_bounded_python_side_peak(tmp_path: Path) -> None:
    rollout = _rollout(frame_count=300)
    tracemalloc.start()
    export_memory_safe_rollout(rollout, tmp_path / "safe")
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # This is a structural CI guard for the synthetic fixture, not a claim
    # about the full GPU rollout's resident memory.
    assert peak < 32 * 1024 * 1024


def test_runner_keeps_legacy_default_and_exposes_explicit_profile() -> None:
    from scripts.run_brain_body_rollout import build_parser

    assert build_parser().parse_args(["--output", "out"]).artifact_profile == "LEGACY"
    assert (
        build_parser().parse_args(["--output", "out", "--artifact-profile", "GATE24E_MEMORY_SAFE"]).artifact_profile
        == "GATE24E_MEMORY_SAFE"
    )


def test_simulation_action_contract_precedes_memory_safe_postprocess() -> None:
    source = (Path(__file__).resolve().parents[1] / "scripts" / "run_brain_body_rollout.py").read_text(encoding="utf-8")
    loop_start = source.index("for step_index in range(steps):")
    order = [
        source.index("brain.step()", loop_start),
        source.index("controller.step(", loop_start),
        source.index("apply_locomotion_action(simulation, fly.name, action)", loop_start),
        source.index("simulation.step()", loop_start),
        source.index("recorder.record()", source.index("simulation.step()", loop_start)),
        source.index("export_memory_safe_rollout", source.index("simulation.step()", loop_start)),
    ]
    assert order == sorted(order)
