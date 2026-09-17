"""Regression tests for real research dataset generation orchestration."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "generate_research_dataset",
    ROOT / "scripts" / "generate_research_dataset.py",
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def _complete_markers(path: Path) -> None:
    path.mkdir(parents=True)
    (path / "rollout.json").write_text(json.dumps({"frames": [{"thorax": [0, 0, 0]}]}), encoding="utf-8")
    np.savez(path / "rollout.npz", thorax_positions=np.asarray([[0.0, 0.0, 0.0]]))
    for name in ("manifest.json", "metadata.json"):
        (path / name).write_text("{}", encoding="utf-8")
    for name in MODULE.REQUIRED_DERIVED:
        target = path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps({"frame_count": 1, "frames": [{"frame_index": 0}]})
            if name.endswith("viewer_pose.json")
            else json.dumps({"dataset_id": "Healthy_001"}) if name.endswith("metrics.json") else "{}",
            encoding="utf-8",
        )
    for name in MODULE.REQUIRED_FIGURES:
        target = path / "figures" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"figure")


def _config(tmp_path: Path) -> Path:
    path = tmp_path / "flygym.yaml"
    path.write_text("fly: {}\nworld: {}\nsimulation:\n  timestep: 0.0001\n", encoding="utf-8")
    return path


def test_resume_skips_complete_dataset_without_simulation(tmp_path: Path) -> None:
    dataset = tmp_path / "datasets" / "healthy" / "Healthy_001"
    _complete_markers(dataset)

    def must_not_run(*_args):
        raise AssertionError("completed dataset was regenerated")

    summary = MODULE.generate_research_datasets(
        repository_root=tmp_path,
        dataset_root="datasets",
        output_root="results/generation",
        config_path=_config(tmp_path),
        count=1,
        run_suite=False,
        simulation_runner=must_not_run,
    )

    assert summary["counts"]["SKIPPED"] == 1
    assert summary["counts"]["FAILED"] == 3


def test_partial_raw_dataset_is_reported_without_overwrite(tmp_path: Path) -> None:
    dataset = tmp_path / "datasets" / "healthy" / "Healthy_001"
    dataset.mkdir(parents=True)
    (dataset / "rollout.json").write_text("{}", encoding="utf-8")

    calls = 0

    def runner(*_args):
        nonlocal calls
        calls += 1

    summary = MODULE.generate_research_datasets(
        repository_root=tmp_path,
        dataset_root="datasets",
        output_root="results/generation",
        config_path=_config(tmp_path),
        count=1,
        run_suite=False,
        simulation_runner=runner,
    )

    assert calls == 3
    assert summary["datasets"][0]["status"] == "FAILED"
    assert "Partial raw rollout package" in summary["datasets"][0]["error"]


def test_failed_simulation_leaves_no_rollout(tmp_path: Path) -> None:
    def runner(*_args):
        raise RuntimeError("simulator unavailable")

    summary = MODULE.generate_research_datasets(
        repository_root=tmp_path,
        dataset_root="datasets",
        output_root="results/generation",
        config_path=_config(tmp_path),
        count=1,
        run_suite=False,
        simulation_runner=runner,
    )

    dataset = tmp_path / "datasets" / "healthy" / "Healthy_001"
    assert summary["counts"]["FAILED"] == 4
    assert not (dataset / "rollout.json").exists()
    assert not (dataset / "rollout.npz").exists()


def test_runtime_unavailable_stops_before_creating_datasets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(MODULE, "_missing_simulation_modules", lambda: ["flygym", "mujoco"])

    with pytest.raises(MODULE.DatasetGenerationError, match="FlyGym runtime unavailable"):
        MODULE.generate_research_datasets(
            repository_root=tmp_path,
            dataset_root="datasets",
            output_root="results/generation",
            config_path=_config(tmp_path),
            count=1,
            run_suite=False,
        )

    assert not (tmp_path / "datasets" / "healthy" / "Healthy_001" / "rollout.json").exists()


def test_real_generation_pipeline_when_flygym_is_available(tmp_path: Path) -> None:
    for name in ("flygym", "mujoco", "flygym_demo"):
        pytest.importorskip(name, reason="FlyGym integration requires the simulation environment.")

    summary = MODULE.generate_research_datasets(
        repository_root=tmp_path,
        dataset_root=tmp_path / "datasets",
        output_root=tmp_path / "results" / "generation",
        config_path=ROOT / "configs" / "v2" / "flygym" / "healthy.yaml",
        count=1,
        steps=2,
        run_suite=True,
    )

    assert summary["counts"]["COMPLETED"] == len(MODULE.DATASET_GROUPS)
    dataset = tmp_path / "datasets" / "healthy" / "Healthy_001"
    assert (dataset / "rollout.json").is_file()
    assert (dataset / "rollout.npz").is_file()
    assert (dataset / "viewer_pose.json").is_file()
    assert (dataset / "metrics" / "metrics.json").is_file()
    assert (tmp_path / "results" / "experiments" / "final_report.html").is_file()
