from __future__ import annotations

import sys
from pathlib import Path

from drosophila_pd.experiments.healthy_baseline import HealthyBaselineConfig
from drosophila_pd.workbench import (
    CandidateSpec,
    NeuralBridgeAdapter,
    NeuralLifAdapter,
    StudySpec,
    default_adapters,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def _study() -> StudySpec:
    return StudySpec(
        name="seed gate",
        hypothesis="h",
        falsifiable_prediction="p",
        assay="motor_flat_ground",
        primary_metric="mean_planar_path_speed_mm_s",
        candidates=(CandidateSpec("control", "Control"),),
        backend="flygym_healthy",
    )


def _lif_fixture(root: Path) -> tuple[Path, Path]:
    """Build the smallest filesystem contract needed by ``NeuralLifAdapter``."""

    neural_root = root / "drosophila-pd-neural-disease"
    model_root = root / "external" / "Drosophila_brain_model"
    (neural_root / "scripts").mkdir(parents=True)
    (neural_root / "annotations").mkdir(parents=True)
    model_root.mkdir(parents=True)
    (neural_root / "scripts" / "run_lif_condition.py").write_text(
        "raise SystemExit('contract fixture only')\n", encoding="utf-8"
    )
    (neural_root / "annotations" / "flywire630_sensory_mn9_public.csv").write_text(
        "root_id\n1\n", encoding="utf-8"
    )
    (model_root / "2023_03_23_completeness_630_final.csv").write_text(
        "id,complete\n1,True\n", encoding="utf-8"
    )
    (model_root / "2023_03_23_connectivity_630_final.parquet").write_bytes(b"fixture")
    return neural_root, model_root


def test_healthy_baseline_config_seed_override_is_revalidated() -> None:
    config = HealthyBaselineConfig.from_mapping({"random_seed": 2})
    updated = config.with_random_seed(17)

    assert config.random_seed == 2
    assert updated.random_seed == 17
    assert config.to_report()["random_seed"] == 2
    assert updated.to_report()["random_seed"] == 17

    sensitivity = updated.with_overrides({"controller.intrinsic_frequency_hz": 13.0})
    assert sensitivity.controller.intrinsic_frequency_hz == 13.0
    try:
        updated.with_overrides({"controller.not_a_real_parameter": 1.0})
    except ValueError as error:
        assert "does not exist" in str(error)
    else:
        raise AssertionError("unknown parameter override was accepted")


def test_healthy_and_brain_driven_adapters_declare_seed_passthrough(tmp_path: Path) -> None:
    adapters = default_adapters(repo_root=REPO_ROOT, interpreter=sys.executable)
    healthy = adapters["flygym_healthy"]
    brain = adapters["flygym_brain_driven"]

    assert healthy.describe().supports_explicit_seed is True
    assert healthy.describe().supports_parameter_overrides is True
    assert brain.describe().supports_explicit_seed is True
    assert brain.describe().supports_parameter_overrides is True

    healthy_command = healthy.command(
        _study(),
        {
            "seed": 17,
            "parameter_overrides": {"controller.intrinsic_frequency_hz": 13.0},
            "baseline_config": REPO_ROOT / "configs" / "experiments" / "healthy_baseline.yaml",
        },
        REPO_ROOT / ".pytest-tmp-seed-gate",
    )
    assert "--seed" in healthy_command
    assert healthy_command[healthy_command.index("--seed") + 1] == "17"
    assert "--override-json" in healthy_command
    assert any(
        '"controller.intrinsic_frequency_hz":13.0' in item
        for item in healthy_command
    )

    scales_path = tmp_path / "scales.json"
    scales_path.write_text('{"motor_scale": 1.0, "coupling_scale": 1.0}', encoding="utf-8")
    brain_study = StudySpec(
        name="brain scale gate",
        hypothesis="h",
        falsifiable_prediction="p",
        assay="motor_flat_ground",
        primary_metric="mean_planar_path_speed_mm_s",
        candidates=(
            CandidateSpec(
                "motor_candidate",
                "Motor scale",
                intervention={"type": "motor_scale", "parameters": {"scale": 0.8}},
            ),
        ),
        backend="flygym_brain_driven",
    )
    brain_config = {
        "candidate_id": "motor_candidate",
        "intervention_type": "motor_scale",
        "intervention": brain_study.candidates[0].intervention,
        "scales_json": scales_path,
        "baseline_config": REPO_ROOT / "configs" / "experiments" / "healthy_baseline.yaml",
        "seed": 17,
    }
    assert brain.validate(brain_study, brain_config) == ()
    brain_command = brain.command(brain_study, brain_config, tmp_path / "brain-artifact")
    assert brain_command[brain_command.index("--motor-scale") + 1] == "0.8"
    assert brain_command[brain_command.index("--seed") + 1] == "17"

    unsupported_study = StudySpec(
        name="unsupported brain intervention",
        hypothesis="h",
        falsifiable_prediction="p",
        assay="motor_flat_ground",
        primary_metric="mean_planar_path_speed_mm_s",
        candidates=(
            CandidateSpec(
                "blocked_candidate",
                "Outgoing synapse block",
                intervention={"type": "outgoing_synapse_block", "scale": 0.0},
            ),
        ),
        backend="flygym_brain_driven",
    )
    errors = brain.validate(
        unsupported_study,
        {
            **brain_config,
            "candidate_id": "blocked_candidate",
            "intervention_type": "outgoing_synapse_block",
            "intervention": unsupported_study.candidates[0].intervention,
        },
    )
    assert any("not supported by backend" in error for error in errors)


def test_neural_bridge_is_not_claimed_seed_capable_by_default() -> None:
    # The neural bridge consumes externally generated spike manifests and its
    # separate repository CLI has no declared seed passthrough contract here.
    # It must remain blocked for confirmation execution until that contract is
    # added and verified in the neural repository.
    bridge = NeuralBridgeAdapter(
        neural_repo_root=REPO_ROOT,
        neural_interpreter=sys.executable,
        platform_root=REPO_ROOT,
        platform_interpreter=sys.executable,
    )
    assert bridge.describe().supports_explicit_seed is False


def test_lif_adapter_has_explicit_external_runtime_contract(tmp_path: Path) -> None:
    neural_root, external_root = _lif_fixture(tmp_path)
    adapter = NeuralLifAdapter(
        neural_repo_root=neural_root,
        neural_interpreter=sys.executable,
        model_root=external_root,
    )
    study = StudySpec(
        name="lif adapter",
        hypothesis="h",
        falsifiable_prediction="p",
        assay="sensory_mn9",
        primary_metric="metrics.readout_rates_hz.720575940660219265",
        candidates=(
            CandidateSpec(
                "activation",
                "Activation",
                intervention={"type": "activation"},
            ),
        ),
        backend="lif_2024",
    )
    config = {
        "candidate_id": "activation",
        "intervention_type": "activation",
        "intervention": study.candidates[0].intervention,
        "model_root": external_root,
        "completeness": external_root / "2023_03_23_completeness_630_final.csv",
        "connectivity": external_root / "2023_03_23_connectivity_630_final.parquet",
        "annotation_file": neural_root / "annotations" / "flywire630_sensory_mn9_public.csv",
        "input_ids": [720575940624963786],
        "readout_ids": [720575940660219265],
        "seed": 3,
        "trials": 1,
        "duration_s": 0.01,
    }

    assert adapter.describe().supports_explicit_seed is True
    assert adapter.validate(study, config) == ()
    command = adapter.command(study, config, tmp_path / "lif-adapter")
    assert "--input-id" in command
    assert "--readout-id" in command
    assert "--annotation-file" in command
    assert command[command.index("--seed") + 1] == "3"

    control_study = StudySpec(
        name="lif control adapter",
        hypothesis="h",
        falsifiable_prediction="p",
        assay="sensory_mn9",
        primary_metric="metrics.readout_rates_hz.720575940660219265",
        candidates=(CandidateSpec("control", "No input", intervention={"type": "none"}),),
        backend="lif_2024",
    )
    control_config = {
        **config,
        "candidate_id": "control",
        "intervention_type": "none",
        "intervention": {"type": "none"},
        "input_ids": [],
    }
    assert adapter.validate(control_study, control_config) == ()
    control_command = adapter.command(control_study, control_config, tmp_path / "lif-control")
    assert "--input-id" not in control_command


def test_lif_adapter_keeps_activation_and_outgoing_block_ids_separate(tmp_path: Path) -> None:
    neural_root, external_root = _lif_fixture(tmp_path)
    adapter = NeuralLifAdapter(
        neural_repo_root=neural_root,
        neural_interpreter=sys.executable,
        model_root=external_root,
    )
    study = StudySpec(
        name="blocking semantics",
        hypothesis="blocking a reviewed upstream target changes MN9",
        falsifiable_prediction="MN9 decreases relative to matched activation",
        assay="sensory_mn9",
        primary_metric="metrics.readout_rates_hz.720575940660219265",
        candidates=(
            CandidateSpec(
                "block",
                "Reviewed block",
                intervention={
                    "type": "outgoing_synapse_block",
                    "parameters": {"outgoing_synapse_block_ids": ["720575940624963786"]},
                },
            ),
        ),
        backend="lif_2024",
    )
    config = {
        "candidate_id": "block",
        "intervention_type": "outgoing_synapse_block",
        "intervention": study.candidates[0].intervention,
        "model_root": external_root,
        "completeness": external_root / "2023_03_23_completeness_630_final.csv",
        "connectivity": external_root / "2023_03_23_connectivity_630_final.parquet",
        "annotation_file": neural_root / "annotations" / "flywire630_sensory_mn9_public.csv",
        "readout_ids": ["720575940660219265"],
    }
    assert adapter.validate(study, config) == ()
    command = adapter.command(study, config, tmp_path / "lif-block")
    assert "--silence-id" in command
    assert "--input-id" not in command

    ambiguous = dict(config)
    ambiguous["intervention"] = {
        "type": "outgoing_synapse_block",
        "parameters": {"neuron_ids": ["720575940624963786"]},
    }
    errors = adapter.validate(study, {**ambiguous, "intervention_type": "outgoing_synapse_block"})
    assert any("ambiguous neuron_ids" in error for error in errors)
