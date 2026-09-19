from __future__ import annotations

from pathlib import Path
import sys

import pytest
import yaml

from drosophila_pd.workbench import NeuralLifAdapter, StudySpec


ROOT = Path(__file__).resolve().parents[1]


def _study(path: Path) -> StudySpec:
    return StudySpec.from_dict(yaml.safe_load(path.read_text(encoding="utf-8")))


def _lif_fixture_or_skip() -> tuple[Path, Path]:
    """Return the external LIF roots or skip with the missing paths listed."""

    neural_root = ROOT.parent / "drosophila-pd-neural"
    model_root = ROOT.parent / "external" / "Drosophila_brain_model"
    required = (
        neural_root,
        model_root,
        model_root / "2023_03_23_completeness_630_final.csv",
        model_root / "2023_03_23_connectivity_630_final.parquet",
        neural_root / "annotations" / "flywire630_sensory_mn9_public.csv",
    )
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        pytest.skip("external LIF fixtures are not distributed in Git: " + ", ".join(missing))
    interpreter = Path(sys.executable)
    if not interpreter.is_file():
        pytest.skip(f"active Python interpreter is unavailable: {interpreter}")
    return neural_root, model_root


def test_new_mn9_protocols_are_explicit_and_use_the_timed_capability() -> None:
    intensity = _study(ROOT / "configs" / "workbench" / "sensory_mn9_intensity.yaml")
    temporal = _study(ROOT / "configs" / "workbench" / "sensory_mn9_temporal.yaml")
    assert intensity.metadata["experiment_id"] == "E1"
    assert temporal.metadata["experiment_id"] == "E2"
    assert temporal.run_plan["confirmation_seed_repetitions"] == 30
    assert any(
        candidate.intervention.get("parameters", {}).get("stimulus_schedule")
        for candidate in temporal.candidates
    )


def test_e2_v2_declares_a_matched_rate_time_contrast_and_controls() -> None:
    study = _study(ROOT / "configs" / "workbench" / "sensory_mn9_temporal_matched_input.yaml")
    assert study.metadata["experiment_id"] == "E2-v2"
    assert study.metadata["primary_contrast"] == "pulsed_150hz_vs_sustained_low_75hz"
    assert study.metadata["ranking_policy"]["control_candidate_id"] == "sustained_low_75hz"
    assert study.metadata["ranking_policy"]["expected_direction"] == "any"
    candidates = {candidate.candidate_id: candidate for candidate in study.candidates}

    def integrated_input(candidate_id: str) -> float:
        schedule = candidates[candidate_id].intervention["parameters"]["stimulus_schedule"]
        return sum(
            float(window["rate_hz"]) * (float(window["end_s"]) - float(window["start_s"]))
            for window in schedule
        )

    assert integrated_input("sustained_low_75hz") == integrated_input("pulsed_150hz")
    assert integrated_input("sustained_high_150hz") == 150.0
    assert {"no_intervention", "sustained_low_75hz", "pulsed_150hz", "sustained_high_150hz"} == set(candidates)


def test_lif_adapter_serializes_schedule_and_declares_capability() -> None:
    neural_root, model_root = _lif_fixture_or_skip()
    adapter = NeuralLifAdapter(
        neural_repo_root=neural_root,
        neural_interpreter=Path(sys.executable),
        model_root=model_root,
    )
    study = _study(ROOT / "configs" / "workbench" / "sensory_mn9_temporal.yaml")
    candidate = next(item for item in study.candidates if item.candidate_id == "pulsed_sugar")
    config = {
        "candidate_id": candidate.candidate_id,
        "intervention_type": "activation",
        "intervention": candidate.intervention,
        "model_root": model_root,
        "completeness": model_root / "2023_03_23_completeness_630_final.csv",
        "connectivity": model_root / "2023_03_23_connectivity_630_final.parquet",
        "annotation_file": neural_root / "annotations" / "flywire630_sensory_mn9_public.csv",
        "input_ids": candidate.intervention["parameters"]["input_ids"],
        "readout_ids": ["720575940660219265"],
        "duration_s": 1.0,
        "trials": 1,
    }
    assert adapter.describe().supports_timed_stimulus is True
    assert adapter.validate(study, config) == ()
    command = adapter.command(study, config, ROOT / ".pytest-tmp-temporal-adapter")
    assert "--stimulus-schedule-json" in command


def test_lif_adapter_rejects_ambiguous_or_out_of_duration_windows() -> None:
    neural_root, model_root = _lif_fixture_or_skip()
    adapter = NeuralLifAdapter(
        neural_repo_root=neural_root,
        neural_interpreter=Path(sys.executable),
        model_root=model_root,
    )
    study = _study(ROOT / "configs" / "workbench" / "sensory_mn9_temporal.yaml")
    candidate = next(item for item in study.candidates if item.candidate_id == "pulsed_sugar")
    parameters = dict(candidate.intervention["parameters"])
    parameters["stimulus_schedule"] = [
        {"start_s": 0.0, "end_s": 0.75, "rate_hz": 150.0, "input_ids": ["720575940624963786"]},
        {"start_s": 0.5, "end_s": 1.1, "rate_hz": 150.0, "input_ids": ["720575940624963786"]},
    ]
    invalid = {
        "candidate_id": candidate.candidate_id,
        "intervention_type": "activation",
        "intervention": {"type": "activation", "parameters": parameters},
        "model_root": model_root,
        "completeness": model_root / "2023_03_23_completeness_630_final.csv",
        "connectivity": model_root / "2023_03_23_connectivity_630_final.parquet",
        "annotation_file": neural_root / "annotations" / "flywire630_sensory_mn9_public.csv",
        "input_ids": parameters["input_ids"],
        "readout_ids": ["720575940660219265"],
        "duration_s": 1.0,
        "trials": 1,
    }

    errors = adapter.validate(study, invalid)

    assert any("ends after duration_s" in error for error in errors)
    assert any("repeat input IDs" in error for error in errors)
