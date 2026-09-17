from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from drosophila_pd.flygym_adapter import (
    FlyBuilder,
    FlyGymAdapter,
    FlyGymConfig,
    FlyGymRuntime,
    FlyGymUnavailableError,
    RolloutRecorder,
    RuntimeState,
    WorldBuilder,
    export_rollout,
)
from drosophila_pd.viewer_export import export_viewer_pose
from drosophila_pd.viewer_export import validate_pose_document


REPO_ROOT = Path(__file__).resolve().parents[1]


class _SimulationStub:
    """API-shaped stub for software contract tests, not scientific data."""

    def __init__(self) -> None:
        self.mj_data = SimpleNamespace(time=0.0)
        self.mj_model = SimpleNamespace(opt=SimpleNamespace(timestep=0.1))
        self.steps = 0

    def step(self) -> None:
        self.steps += 1
        self.mj_data.time = self.steps * 0.1

    def reset(self) -> None:
        self.steps = 0
        self.mj_data.time = 0.0

    def get_body_positions(self, _name: str) -> np.ndarray:
        return np.asarray([[float(self.steps), 0.0, 0.5], [0.0, 0.0, 0.0]])

    def get_body_rotations(self, _name: str) -> np.ndarray:
        return np.asarray([[1.0, 0.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0]])

    def get_joint_angles(self, _name: str) -> np.ndarray:
        return np.asarray([float(self.steps)])

    def get_joint_velocities(self, _name: str) -> np.ndarray:
        return np.asarray([float(self.steps)])

    def get_ground_contact_info(self, _name: str):
        return (
            np.asarray([1.0]),
            np.asarray([[0.0, 0.0, 1.0]]),
            np.asarray([[0.0, 0.0, 0.0]]),
            np.asarray([[0.0, 0.0, 0.0]]),
            np.asarray([[0.0, 0.0, 1.0]]),
            np.asarray([[1.0, 0.0, 0.0]]),
        )


class _InvalidFirstOrientationSimulationStub(_SimulationStub):
    """Stub that exposes an invalid first quaternion for recorder regression."""

    def __init__(self, first_orientation: list[float]) -> None:
        super().__init__()
        self.first_orientation = first_orientation

    def get_body_rotations(self, _name: str) -> np.ndarray:
        if self.steps == 0:
            return np.asarray([self.first_orientation, [1.0, 0.0, 0.0, 0.0]])
        return np.asarray([[0.5, 0.5, 0.5, 0.5], [1.0, 0.0, 0.0, 0.0]])


class _InvalidLaterOrientationSimulationStub(_SimulationStub):
    """Stub that exposes a valid first quaternion followed by invalid samples."""

    def get_body_rotations(self, _name: str) -> np.ndarray:
        if self.steps == 0:
            return np.asarray([[0.5, 0.5, 0.5, 0.5], [1.0, 0.0, 0.0, 0.0]])
        return np.asarray([[float("nan"), 0.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0]])


def test_configuration_and_yaml_contract() -> None:
    assert FlyGymConfig.from_mapping({}).simulation.timestep == 0.0001
    config = FlyGymConfig.from_yaml(REPO_ROOT / "configs/v2/flygym/default.yaml")

    assert config.fly.factory == "canonical_locomotion"
    assert config.world.kind == "flat"
    assert config.simulation.timestep == 0.0001
    assert config.metadata["flygym_version"] == "2.1.0"


def test_builders_are_fluent_and_do_not_import_flygym_until_build(monkeypatch: pytest.MonkeyPatch) -> None:
    fly_builder = (
        FlyBuilder()
        .healthy()
        .position([1.0, 2.0, 0.5])
        .orientation([1.0, 0.0, 0.0, 0.0])
        .pose({"position": [1.0, 2.0, 0.5]})
    )
    assert fly_builder.spawn_position == (1.0, 2.0, 0.5)
    assert WorldBuilder().blocks(rand_seed=3)._config.kind == "blocks"

    import sys
    monkeypatch.setitem(sys.modules, "flygym", None)
    with pytest.raises(FlyGymUnavailableError):
        fly_builder.build()


def test_adapter_facade_delegates_renderer_creation() -> None:
    simulation = SimpleNamespace(
        set_renderer=lambda cameras, **kwargs: {"cameras": cameras, "kwargs": kwargs}
    )

    renderer = FlyGymAdapter().create_renderer(simulation, cameras="track")

    assert renderer["cameras"] == "track"
    assert renderer["kwargs"]["output_fps"] == 25


def test_runtime_state_machine_is_synchronous_and_bounded() -> None:
    simulation = _SimulationStub()
    recorder = RolloutRecorder(
        simulation,
        "fly",
        timestep=0.1,
        com_provider=lambda _simulation, _fly: [0.0, 0.0, 0.5],
    )
    runtime = FlyGymRuntime(simulation, recorder=recorder, max_steps=2)

    assert runtime.state is RuntimeState.STOPPED
    runtime.run()

    assert runtime.state is RuntimeState.STOPPED
    assert not runtime.is_running
    assert runtime.current_step == 2
    assert runtime.current_time == 0.2
    assert recorder.rollout.frame_count == 3
    assert recorder.rollout.frames[-1].joint_acceleration is not None

    runtime.reset()
    assert runtime.current_step == 0
    assert recorder.rollout.frame_count == 1


def test_runtime_pause_and_resume() -> None:
    simulation = _SimulationStub()
    runtime = FlyGymRuntime(simulation)
    runtime.step()
    runtime.pause()
    assert runtime.state is RuntimeState.PAUSED
    with pytest.raises(RuntimeError, match="paused"):
        runtime.step()
    runtime.resume()
    runtime.step()
    runtime.stop()
    assert runtime.state is RuntimeState.STOPPED
    assert simulation.steps == 2


def test_rollout_export_writes_all_canonical_formats(tmp_path: Path) -> None:
    simulation = _SimulationStub()
    recorder = RolloutRecorder(
        simulation,
        "fly",
        timestep=0.1,
        camera_metadata={"cameras": ["track"]},
        simulation_metadata={"timestep_s": 0.1},
        com_provider=lambda _simulation, _fly: [0.0, 0.0, 0.5],
    )
    recorder.record()
    simulation.step()
    recorder.record()

    exported = export_rollout(recorder.rollout, tmp_path / "Healthy_001")

    assert set(exported.files) == {"rollout_json", "rollout_csv", "rollout_npz", "metadata", "manifest"}
    for path in exported.files.values():
        assert Path(path).is_file()
        assert Path(path).stat().st_size > 0
    assert exported.manifest["frame_count"] == 2
    assert exported.manifest["files"]["rollout_npz"]["sha256"]


def test_recorder_initializes_zero_first_quaternion_and_viewer_export_succeeds(tmp_path: Path) -> None:
    simulation = _InvalidFirstOrientationSimulationStub([0.0, 0.0, 0.0, 0.0])
    recorder = RolloutRecorder(
        simulation,
        "fly",
        timestep=0.1,
        com_provider=lambda _simulation, _fly: [0.0, 0.0, 0.5],
    )
    recorder.record()
    simulation.step()
    recorder.record()

    exported = export_rollout(recorder.rollout, tmp_path / "Healthy_001")
    first_orientation = np.asarray(recorder.rollout.frames[0].orientation, dtype=float)

    assert np.linalg.norm(first_orientation) > 0
    assert np.allclose(first_orientation, [1.0, 0.0, 0.0, 0.0])

    arrays = np.load(exported.files["rollout_npz"])
    assert np.linalg.norm(arrays["orientation"][0]) > 0
    rollout_json = json.loads(Path(exported.files["rollout_json"]).read_text(encoding="utf-8"))
    json_orientation = np.asarray(rollout_json["frames"][0]["orientation"], dtype=float)
    assert np.linalg.norm(json_orientation) > 0
    assert np.allclose(json_orientation, [1.0, 0.0, 0.0, 0.0])

    viewer_result = export_viewer_pose(tmp_path / "Healthy_001", tmp_path / "viewer_pose.json")
    assert viewer_result.validation.overall_pass is True
    assert viewer_result.document["frames"][0]["orientation"] == [0.0, 0.0, 0.0, 1.0]


def test_rollout_to_viewer_pipeline_uses_adapter_npz_without_manual_renaming(tmp_path: Path) -> None:
    simulation = _InvalidFirstOrientationSimulationStub([0.0, 0.0, 0.0, 0.0])
    recorder = RolloutRecorder(
        simulation,
        "fly",
        timestep=0.1,
        com_provider=lambda _simulation, _fly: [0.0, 0.0, 0.5],
    )
    recorder.record()
    simulation.step()
    recorder.record()

    dataset = tmp_path / "datasets" / "healthy" / "Healthy_001"
    exported = export_rollout(recorder.rollout, dataset)
    assert Path(exported.files["rollout_npz"]).name == "rollout.npz"
    assert not (dataset / "rollout_arrays.npz").exists()

    result = export_viewer_pose("Healthy_001", tmp_path / "viewer_pose.json", search_roots=[tmp_path / "datasets"])

    assert result.source_files[1].name == "rollout.npz"
    assert result.validation.overall_pass is True
    assert validate_pose_document(result.document).overall_pass is True
    orientations = np.asarray([frame["orientation"] for frame in result.document["frames"]], dtype=float)
    assert np.allclose(np.linalg.norm(orientations, axis=1), 1.0)


def test_recorder_reuses_previous_valid_quaternion_for_later_invalid_orientation() -> None:
    simulation = _InvalidLaterOrientationSimulationStub()
    recorder = RolloutRecorder(simulation, "fly", timestep=0.1)

    first = recorder.record()
    simulation.step()
    second = recorder.record()

    assert np.allclose(first.orientation, [0.5, 0.5, 0.5, 0.5])
    assert np.allclose(second.orientation, first.orientation)


def test_recorder_sanitizes_non_finite_first_quaternion_to_identity() -> None:
    recorder = RolloutRecorder(_SimulationStub(), "fly", timestep=0.1)

    orientation = recorder._sanitize_orientation(np.asarray([float("nan"), 0.0, 0.0, 0.0]))

    assert np.allclose(orientation, [1.0, 0.0, 0.0, 0.0])
    assert np.allclose(recorder._previous_orientation, [1.0, 0.0, 0.0, 0.0])


def test_recorder_normalizes_valid_quaternion_samples() -> None:
    recorder = RolloutRecorder(_SimulationStub(), "fly", timestep=0.1)

    orientation = recorder._sanitize_orientation(np.asarray([2.0, 0.0, 0.0, 0.0]))

    assert np.allclose(orientation, [1.0, 0.0, 0.0, 0.0])
