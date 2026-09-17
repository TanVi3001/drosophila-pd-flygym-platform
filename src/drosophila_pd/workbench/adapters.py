"""Backend adapters used by the workbench worker.

Adapters own the command line contract for a backend.  The service never
imports the neural package and therefore cannot accidentally mix the two
repositories' packages or virtual environments.
"""

from __future__ import annotations

import os
import json
import math
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Protocol, Sequence

from .models import CapabilityDescriptor, JobRecord, StudySpec


@dataclass(frozen=True)
class BackendRunContext:
    job: JobRecord
    study: StudySpec
    run_id: str
    artifact_dir: Path
    log_path: Path
    cancel_event: threading.Event
    register_process: Callable[[subprocess.Popen[str] | None], None]


@dataclass(frozen=True)
class BackendRunResult:
    command: tuple[str, ...]
    interpreter: str
    repo_root: str
    exit_code: int | None
    cancelled: bool = False
    error: str | None = None


class BackendAdapter(Protocol):
    name: str

    def describe(self) -> CapabilityDescriptor:
        ...

    def validate(self, study: StudySpec, config: Mapping[str, object]) -> tuple[str, ...]:
        ...

    def run(self, context: BackendRunContext) -> BackendRunResult:
        ...


CommandFactory = Callable[[StudySpec, Mapping[str, object], Path], Sequence[str]]


class CommandBackendAdapter:
    """Run one explicitly configured command and capture its complete log."""

    def __init__(
        self,
        *,
        name: str,
        descriptor: CapabilityDescriptor,
        repo_root: str | Path,
        interpreter: str | Path,
        command_factory: CommandFactory,
        script_path: str | Path,
        result_path: str | Path | None = None,
    ) -> None:
        self.name = name
        self._descriptor = descriptor
        self.repo_root = Path(repo_root).resolve()
        self.interpreter = str(Path(interpreter).resolve()) if Path(str(interpreter)).is_absolute() else str(interpreter)
        self.script_path = Path(script_path)
        self.result_path = None if result_path is None else Path(result_path)
        self._command_factory = command_factory

    def describe(self) -> CapabilityDescriptor:
        available = self._base_validation()
        descriptor = self._descriptor
        return CapabilityDescriptor(
            name=descriptor.name,
            display_name=descriptor.display_name,
            ready=descriptor.ready and not available,
            supported_assays=descriptor.supported_assays,
            supported_interventions=descriptor.supported_interventions,
            limitations=descriptor.limitations,
            requirements=descriptor.requirements + tuple(available),
            supports_explicit_seed=descriptor.supports_explicit_seed,
            supports_parameter_overrides=descriptor.supports_parameter_overrides,
            supports_timed_stimulus=descriptor.supports_timed_stimulus,
        )

    def validate(self, study: StudySpec, config: Mapping[str, object]) -> tuple[str, ...]:
        errors = list(self._base_validation())
        try:
            command = self.command(study, config, Path(config.get("_artifact_dir", self.repo_root)))
        except (KeyError, TypeError, ValueError, OSError) as error:
            errors.append(f"cannot build backend command: {type(error).__name__}: {error}")
        else:
            if not command:
                errors.append("backend command is empty")
        return tuple(errors)

    def command(self, study: StudySpec, config: Mapping[str, object], artifact_dir: Path) -> tuple[str, ...]:
        raw = tuple(str(item) for item in self._command_factory(study, config, artifact_dir))
        if not raw:
            raise ValueError("backend command is empty")
        return raw

    def run(self, context: BackendRunContext) -> BackendRunResult:
        command = self.command(context.study, context.job.config, context.artifact_dir)
        context.artifact_dir.mkdir(parents=True, exist_ok=True)
        context.log_path.parent.mkdir(parents=True, exist_ok=True)
        cancelled = False
        process: subprocess.Popen[str] | None = None
        try:
            with context.log_path.open("w", encoding="utf-8") as log:
                log.write("$ " + _display_command(command) + "\n")
                log.flush()
                process = subprocess.Popen(
                    command,
                    cwd=self.repo_root,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    text=True,
                    env=os.environ.copy(),
                )
                context.register_process(process)
                while process.poll() is None:
                    if context.cancel_event.is_set():
                        cancelled = True
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait(timeout=5)
                        break
                    time.sleep(0.05)
                exit_code = process.wait()
                log.write(f"\nexit_code={exit_code}\n")
        except OSError as error:
            return BackendRunResult(
                command=command,
                interpreter=command[0],
                repo_root=self.repo_root.as_posix(),
                exit_code=None,
                cancelled=cancelled,
                error=f"{type(error).__name__}: {error}",
            )
        finally:
            context.register_process(None)
        return BackendRunResult(
            command=command,
            interpreter=command[0],
            repo_root=self.repo_root.as_posix(),
            exit_code=exit_code,
            cancelled=cancelled,
            error=None if exit_code == 0 and not cancelled else f"backend exited with code {exit_code}",
        )

    def _base_validation(self) -> tuple[str, ...]:
        errors: list[str] = []
        if not self.repo_root.is_dir():
            errors.append(f"repo_root does not exist: {self.repo_root}")
        if not (self.repo_root / self.script_path).is_file():
            errors.append(f"script does not exist: {self.repo_root / self.script_path}")
        if Path(self.interpreter).is_absolute():
            if not Path(self.interpreter).is_file():
                errors.append(f"interpreter does not exist: {self.interpreter}")
        elif shutil.which(self.interpreter) is None:
            errors.append(f"interpreter is not on PATH: {self.interpreter}")
        return tuple(errors)


class HealthyBaselineAdapter(CommandBackendAdapter):
    def __init__(self, repo_root: str | Path | None = None, interpreter: str | Path | None = None) -> None:
        root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[3]
        python = interpreter or sys.executable
        super().__init__(
            name="flygym_healthy",
            descriptor=CapabilityDescriptor(
                name="flygym_healthy",
                display_name="FlyGym healthy locomotion baseline",
                ready=True,
                supported_assays=("locomotion", "motor", "motor_flat_ground"),
                supported_interventions=("none", "control", "controller_parameter_override"),
                limitations=(
                    "Computational locomotion benchmark only.",
                    "Does not establish neuron-specific or disease validation.",
                ),
                requirements=("FlyGym/MuJoCo dependencies must be installed in the selected interpreter.",),
                supports_explicit_seed=True,
                supports_parameter_overrides=True,
            ),
            repo_root=root,
            interpreter=python,
            command_factory=self._build_command,
            script_path=Path("scripts") / "run_healthy_baseline.py",
            result_path=Path("healthy_baseline.json"),
        )

    def validate(self, study: StudySpec, config: Mapping[str, object]) -> tuple[str, ...]:
        errors = list(super().validate(study, config))
        errors.extend(_candidate_contract_errors(study, config, self.describe().supported_interventions))
        if study.assay not in self.describe().supported_assays:
            errors.append(f"assay is outside backend capability: {study.assay}")
        config_path = Path(str(config.get("baseline_config", self.repo_root / "configs" / "experiments" / "healthy_baseline.yaml")))
        if not config_path.is_file():
            errors.append(f"baseline_config does not exist: {config_path}")
        if config.get("parameter_overrides") is not None and not isinstance(config["parameter_overrides"], Mapping):
            errors.append("parameter_overrides must be a mapping")
        return tuple(dict.fromkeys(errors))

    def _build_command(self, _study: StudySpec, config: Mapping[str, object], artifact_dir: Path) -> Sequence[str]:
        config_path = Path(str(config.get("baseline_config", self.repo_root / "configs" / "experiments" / "healthy_baseline.yaml"))).resolve()
        output = (artifact_dir / "healthy_baseline.json").resolve()
        command = [
            self.interpreter,
            str((self.repo_root / self.script_path).resolve()),
            "--config",
            str(config_path),
            "--output",
            str(output),
        ]
        if config.get("seed") is not None:
            command.extend(("--seed", str(config["seed"])))
        if config.get("parameter_overrides") is not None:
            if not isinstance(config["parameter_overrides"], Mapping):
                raise ValueError("parameter_overrides must be a mapping")
            command.extend(
                (
                    "--override-json",
                    json.dumps(config["parameter_overrides"], sort_keys=True, separators=(",", ":")),
                )
            )
        return tuple(command)


class BrainDrivenAdapter(CommandBackendAdapter):
    def __init__(self, repo_root: str | Path | None = None, interpreter: str | Path | None = None) -> None:
        root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[3]
        python = interpreter or sys.executable
        super().__init__(
            name="flygym_brain_driven",
            descriptor=CapabilityDescriptor(
                name="flygym_brain_driven",
                display_name="FlyGym brain-driven paired locomotion",
                ready=True,
                supported_assays=("locomotion", "motor", "motor_flat_ground"),
                supported_interventions=("motor_scale", "coupling_scale"),
                limitations=(
                    "Bridge scales are computational proxies and require an auditable source manifest.",
                    "A perturbation result is not a claim that a neuron is dead or absent.",
                ),
                requirements=("A validated bridge scales JSON and FlyGym/MuJoCo dependencies are required.",),
                supports_explicit_seed=True,
                supports_parameter_overrides=True,
            ),
            repo_root=root,
            interpreter=python,
            command_factory=self._build_command,
            script_path=Path("scripts") / "run_brain_driven_experiment.py",
            result_path=Path("brain_driven.json"),
        )

    def validate(self, study: StudySpec, config: Mapping[str, object]) -> tuple[str, ...]:
        errors = list(super().validate(study, config))
        errors.extend(_candidate_contract_errors(study, config, self.describe().supported_interventions))
        if study.assay not in self.describe().supported_assays:
            errors.append(f"assay is outside backend capability: {study.assay}")
        scales = config.get("scales_json")
        if not scales or not Path(str(scales)).is_file():
            errors.append(f"scales_json does not exist: {scales}")
        if config.get("parameter_overrides") is not None and not isinstance(config["parameter_overrides"], Mapping):
            errors.append("parameter_overrides must be a mapping")
        intervention_type = str(config.get("intervention_type", "")).strip()
        if intervention_type in {"motor_scale", "coupling_scale"}:
            scale = _intervention_scale(config, intervention_type)
            if scale is None:
                errors.append(f"{intervention_type} requires intervention.parameters.scale or intervention.scale")
            else:
                try:
                    numeric_scale = float(scale)
                except (TypeError, ValueError):
                    errors.append(f"{intervention_type} scale must be numeric")
                else:
                    if not math.isfinite(numeric_scale) or numeric_scale < 0:
                        errors.append(f"{intervention_type} scale must be finite and non-negative")
        return tuple(dict.fromkeys(errors))

    def _build_command(self, _study: StudySpec, config: Mapping[str, object], artifact_dir: Path) -> Sequence[str]:
        scales = Path(str(config["scales_json"])).resolve()
        baseline = Path(str(config.get("baseline_config", self.repo_root / "configs" / "experiments" / "healthy_baseline.yaml"))).resolve()
        output = (artifact_dir / "brain_driven.json").resolve()
        command: list[str] = [
            self.interpreter,
            str((self.repo_root / self.script_path).resolve()),
            "--scales-json",
            str(scales),
            "--baseline-config",
            str(baseline),
            "--output",
            str(output),
        ]
        if config.get("model_name"):
            command.extend(("--model-name", str(config["model_name"])))
        intervention_type = str(config.get("intervention_type", "")).strip()
        if intervention_type in {"motor_scale", "coupling_scale"}:
            scale = _intervention_scale(config, intervention_type)
            if scale is None:
                raise ValueError(f"{intervention_type} requires intervention.parameters.scale or intervention.scale")
            flag = "--motor-scale" if intervention_type == "motor_scale" else "--coupling-scale"
            command.extend((flag, str(scale)))
        if config.get("seed") is not None:
            command.extend(("--seed", str(config["seed"])))
        if config.get("parameter_overrides") is not None:
            if not isinstance(config["parameter_overrides"], Mapping):
                raise ValueError("parameter_overrides must be a mapping")
            command.extend(
                (
                    "--override-json",
                    json.dumps(config["parameter_overrides"], sort_keys=True, separators=(",", ":")),
                )
            )
        return command


class NeuralBridgeAdapter(CommandBackendAdapter):
    """Run the explicit neural-repo bridge without importing that package."""

    def __init__(
        self,
        neural_repo_root: str | Path,
        neural_interpreter: str | Path,
        platform_root: str | Path | None = None,
        platform_interpreter: str | Path | None = None,
    ) -> None:
        neural_root = Path(neural_repo_root)
        platform = Path(platform_root) if platform_root is not None else Path(__file__).resolve().parents[3]
        platform_python = platform_interpreter or sys.executable
        super().__init__(
            name="neural_bridge",
            descriptor=CapabilityDescriptor(
                name="neural_bridge",
                display_name="Brian2 spike manifest to FlyGym bridge",
                ready=True,
                supported_assays=("neural", "sensory_mn9", "locomotion"),
                supported_interventions=("activation", "outgoing_synapse_block"),
                limitations=(
                    "Consumes already generated spike outputs; this adapter does not create new LIF spikes.",
                    "The neural-to-body mapping is a proxy and requires explicit source manifests.",
                ),
                requirements=("Neural and platform repositories must remain in separate environments.",),
            ),
            repo_root=neural_root,
            interpreter=neural_interpreter,
            command_factory=lambda study, config, artifact_dir: self._build_command(
                study, config, artifact_dir, platform, str(platform_python)
            ),
            script_path=Path("scripts") / "run_lif_to_flygym.py",
            result_path=Path("lif_to_flygym") / "platform_report.json",
        )

    def validate(self, study: StudySpec, config: Mapping[str, object]) -> tuple[str, ...]:
        errors = list(super().validate(study, config))
        errors.extend(_candidate_contract_errors(study, config, self.describe().supported_interventions))
        required = ("reference_spikes", "condition_spikes", "reference_manifest", "condition_manifest", "model")
        for key in required:
            value = config.get(key)
            if not value:
                errors.append(f"{key} is required")
            elif key != "model" and not Path(str(value)).is_file():
                errors.append(f"{key} does not exist: {value}")
        return tuple(dict.fromkeys(errors))

    def _build_command(
        self,
        _study: StudySpec,
        config: Mapping[str, object],
        artifact_dir: Path,
        platform_root: Path,
        platform_interpreter: str,
    ) -> Sequence[str]:
        output = (artifact_dir / "lif_to_flygym").resolve()
        command: list[str] = [
            self.interpreter,
            str((self.repo_root / self.script_path).resolve()),
            "--reference-spikes", str(Path(str(config["reference_spikes"])).resolve()),
            "--condition-spikes", str(Path(str(config["condition_spikes"])).resolve()),
            "--reference-manifest", str(Path(str(config["reference_manifest"])).resolve()),
            "--condition-manifest", str(Path(str(config["condition_manifest"])).resolve()),
            "--model", str(config["model"]),
            "--platform-root", str(platform_root.resolve()),
            "--platform-python", str(Path(platform_interpreter).resolve()),
            "--output", str(output),
        ]
        for key, flag in (("annotations", "--annotations"), ("condition_label", "--condition-label"), ("duration_s", "--duration-s")):
            if config.get(key) is not None:
                command.extend((flag, str(config[key])))
        if config.get("allow_missing_turn"):
            command.append("--allow-missing-turn")
        return command


class NeuralLifAdapter(CommandBackendAdapter):
    """Run the explicit external Shiu-2024 LIF wrapper in its own environment."""

    def __init__(
        self,
        neural_repo_root: str | Path,
        neural_interpreter: str | Path,
        model_root: str | Path | None = None,
    ) -> None:
        neural_root = Path(neural_repo_root)
        default_model_root = neural_root.parent / "external" / "Drosophila_brain_model"
        self.model_root = Path(model_root) if model_root is not None else default_model_root
        super().__init__(
            name="lif_2024",
            descriptor=CapabilityDescriptor(
                name="lif_2024",
                display_name="Shiu 2024 Brian2 LIF condition runner",
                ready=True,
                supported_assays=("neural", "sensory", "sensory_mn9"),
                supported_interventions=("none", "activation", "outgoing_synapse_block", "activation_plus_outgoing_synapse_block"),
                limitations=(
                    "Runs the pinned external LIF model and reports computational spike readouts only.",
                    "The upstream model is imported by file path and remains a separate dependency.",
                    "Outgoing synapse block is a model operation, not neuron death or biological absence.",
                ),
                requirements=(
                    "The separate neural interpreter must contain Brian2, pandas, pyarrow, and the public model data.",
                ),
                supports_explicit_seed=True,
                supports_parameter_overrides=False,
                supports_timed_stimulus=True,
            ),
            repo_root=neural_root,
            interpreter=neural_interpreter,
            command_factory=self._build_command,
            script_path=Path("scripts") / "run_lif_condition.py",
            result_path=Path("lif_condition") / "metrics.json",
        )

    def validate(self, study: StudySpec, config: Mapping[str, object]) -> tuple[str, ...]:
        errors = list(super().validate(study, config))
        errors.extend(_candidate_contract_errors(study, config, self.describe().supported_interventions))
        if study.assay not in self.describe().supported_assays:
            errors.append(f"assay is outside backend capability: {study.assay}")
        for key, default in (
            ("model_root", self.model_root),
            ("completeness", None),
            ("connectivity", None),
            ("annotation_file", None),
        ):
            value = config.get(key, default)
            if key == "annotation_file" and value is None:
                continue
            if not value:
                errors.append(f"{key} is required")
            elif not Path(str(value)).is_file() and key != "model_root":
                errors.append(f"{key} does not exist: {value}")
            elif key == "model_root" and not Path(str(value)).is_dir():
                errors.append(f"model_root does not exist: {value}")

        intervention_type = str(config.get("intervention_type", "none")).strip() or "none"
        try:
            input_ids = _neural_input_ids(config)
            silence_ids = _neural_silence_ids(config)
            readout_ids = _neural_readout_ids(config)
        except ValueError as error:
            errors.append(str(error))
            input_ids = ()
            silence_ids = ()
            readout_ids = ()
        if intervention_type == "activation" and not input_ids:
            errors.append("activation requires a non-empty reviewed input ID set")
        if config.get("input_ids") is not None and (
            not isinstance(config.get("input_ids"), Sequence)
            or isinstance(config.get("input_ids"), (str, bytes))
        ):
            errors.append("input_ids must be a sequence of reviewed neuron IDs")
        if intervention_type in {"outgoing_synapse_block", "activation_plus_outgoing_synapse_block"} and not silence_ids:
            errors.append(f"{intervention_type} requires reviewed outgoing-synapse block IDs")
        if study.assay == "sensory_mn9" and not readout_ids:
            errors.append("sensory_mn9 requires at least one explicit reviewed readout ID")
        if config.get("readout_ids") is not None and (
            not isinstance(config.get("readout_ids"), Sequence)
            or isinstance(config.get("readout_ids"), (str, bytes))
        ):
            errors.append("readout_ids must be a sequence of reviewed neuron IDs")
        if config.get("trials") is not None:
            try:
                if int(config["trials"]) <= 0:
                    errors.append("trials must be positive")
            except (TypeError, ValueError):
                errors.append("trials must be an integer")
        if config.get("stimulus_rate_hz") is not None:
            try:
                rate = float(config["stimulus_rate_hz"])
            except (TypeError, ValueError):
                errors.append("stimulus_rate_hz must be numeric")
            else:
                if not math.isfinite(rate) or rate < 0:
                    errors.append("stimulus_rate_hz must be finite and non-negative")
        schedule = _stimulus_schedule(config)
        if schedule is not None:
            if not isinstance(schedule, Sequence) or isinstance(schedule, (str, bytes)):
                errors.append("stimulus_schedule must be a list of time-window objects")
            else:
                try:
                    duration_s = float(config.get("duration_s", 1.0))
                except (TypeError, ValueError):
                    duration_s = float("nan")
                    errors.append("duration_s must be numeric for a stimulus schedule")
                schedule_windows: list[tuple[float, float, set[str]]] = []
                for index, window in enumerate(schedule):
                    if not isinstance(window, Mapping):
                        errors.append(f"stimulus_schedule[{index}] must be an object")
                        continue
                    for key in ("start_s", "end_s", "rate_hz", "input_ids"):
                        if key not in window:
                            errors.append(f"stimulus_schedule[{index}] is missing {key}")
                    start = end = rate = float("nan")
                    try:
                        start = float(window.get("start_s"))
                        end = float(window.get("end_s"))
                        rate = float(window.get("rate_hz"))
                    except (TypeError, ValueError):
                        errors.append(f"stimulus_schedule[{index}] has non-numeric timing/rate")
                    else:
                        if not math.isfinite(start) or not math.isfinite(end) or end <= start or start < 0:
                            errors.append(f"stimulus_schedule[{index}] has invalid start_s/end_s")
                        elif not math.isfinite(duration_s) or duration_s <= 0 or end > duration_s:
                            errors.append(f"stimulus_schedule[{index}] ends after duration_s")
                        if not math.isfinite(rate) or rate < 0:
                            errors.append(f"stimulus_schedule[{index}] has invalid rate_hz")
                    try:
                        ids = _neural_id_list(window.get("input_ids"))
                    except ValueError as error:
                        errors.append(f"stimulus_schedule[{index}]: {error}")
                    else:
                        if not ids:
                            errors.append(f"stimulus_schedule[{index}] input_ids must be non-empty")
                        elif math.isfinite(start) and math.isfinite(end) and end > start:
                            schedule_windows.append((start, end, set(ids)))
                for left_index, (left_start, left_end, left_ids) in enumerate(schedule_windows):
                    for right_start, right_end, right_ids in schedule_windows[left_index + 1 :]:
                        if left_end <= right_start or right_end <= left_start:
                            continue
                        repeated_ids = sorted(left_ids.intersection(right_ids))
                        if repeated_ids:
                            errors.append(
                                "overlapping stimulus windows repeat input IDs: "
                                + ", ".join(repeated_ids)
                            )
        return tuple(dict.fromkeys(errors))

    def _build_command(self, _study: StudySpec, config: Mapping[str, object], artifact_dir: Path) -> Sequence[str]:
        model_root = Path(str(config.get("model_root", self.model_root))).resolve()
        completeness = Path(str(config.get("completeness", model_root / "2023_03_23_completeness_630_final.csv"))).resolve()
        connectivity = Path(str(config.get("connectivity", model_root / "2023_03_23_connectivity_630_final.parquet"))).resolve()
        output = (artifact_dir / "lif_condition").resolve()
        command: list[str] = [
            self.interpreter,
            str((self.repo_root / self.script_path).resolve()),
            "--model-root", str(model_root),
            "--completeness", str(completeness),
            "--connectivity", str(connectivity),
            "--condition-label", str(config.get("condition_label", config.get("candidate_id", "condition"))),
            "--output", str(output),
            "--seed", str(config.get("seed", 0)),
            "--trials", str(config.get("trials", 1)),
            "--duration-s", str(config.get("duration_s", 1.0)),
            "--stimulus-rate-hz", str(config.get("stimulus_rate_hz", 150.0)),
            "--id-namespace", str(config.get("id_namespace", "flywire_root_id")),
            "--dataset-id", str(config.get("dataset_id", "flywire-630-2023-03-23")),
        ]
        if config.get("annotation_file") is not None:
            command.extend(("--annotation-file", str(Path(str(config["annotation_file"])).resolve())))
        for value in _neural_input_ids(config):
            command.extend(("--input-id", value))
        for value in _neural_silence_ids(config):
            command.extend(("--silence-id", value))
        for value in _neural_readout_ids(config):
            command.extend(("--readout-id", value))
        schedule = _stimulus_schedule(config)
        if schedule is not None:
            command.extend(("--stimulus-schedule-json", json.dumps(schedule, sort_keys=True, separators=(",", ":"))))
        return command


def _candidate_contract_errors(
    study: StudySpec,
    config: Mapping[str, object],
    supported_interventions: Sequence[str],
) -> list[str]:
    """Validate that a declared candidate has an executable intervention contract.

    The generic test adapter intentionally remains permissive, but concrete
    backends must never silently accept a StudySpec intervention that they do
    not implement.  The service writes ``intervention_type`` and the full
    ``intervention`` into the job configuration before this function runs.
    """

    candidate_id = str(config.get("candidate_id", "")).strip()
    if not candidate_id:
        return ["candidate_id is required for a concrete backend"]
    candidate = next((item for item in study.candidates if item.candidate_id == candidate_id), None)
    if candidate is None:
        return [f"candidate_id is not declared in StudySpec: {candidate_id}"]

    intervention = config.get("intervention")
    if not isinstance(intervention, Mapping):
        intervention = candidate.intervention
    intervention_type = str(
        config.get(
            "intervention_type",
            intervention.get("type", "none") if isinstance(intervention, Mapping) else "none",
        )
    ).strip() or "none"
    if intervention_type not in set(supported_interventions):
        return [
            f"candidate intervention {intervention_type!r} is not supported by backend "
            f"(supported: {', '.join(supported_interventions) or 'none'})"
        ]

    parameters = intervention.get("parameters")
    if "neuron_ids" in intervention or (
        isinstance(parameters, Mapping) and "neuron_ids" in parameters
    ):
        return [
            "ambiguous neuron_ids is not accepted; declare input_ids for activation "
            "or outgoing_synapse_block_ids for synapse blocking"
        ]

    if intervention_type == "controller_parameter_override":
        overrides = config.get("parameter_overrides")
        if not isinstance(overrides, Mapping) or not overrides:
            return ["controller_parameter_override requires non-empty parameter_overrides"]
    return []


def _intervention_scale(config: Mapping[str, object], intervention_type: str) -> object | None:
    """Read the explicit scale for a brain-driven intervention.

    StudySpec permits either a compact ``scale`` field or a nested
    ``parameters.scale`` field.  The adapter accepts both but never infers a
    scale from an unrelated baseline parameter override.
    """

    intervention = config.get("intervention")
    if not isinstance(intervention, Mapping):
        return None
    parameters = intervention.get("parameters")
    if isinstance(parameters, Mapping) and parameters.get("scale") is not None:
        return parameters.get("scale")
    if intervention.get("scale") is not None:
        return intervention.get("scale")
    return None


def _neural_id_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    result: list[str] = []
    for item in value:
        if isinstance(item, bool) or item is None or isinstance(item, float):
            raise ValueError(
                "neuron IDs must be exact strings or integers; floating-point IDs are rejected"
            )
        text = str(item).strip()
        if text:
            result.append(text)
    return tuple(dict.fromkeys(result))


def _neural_input_ids(config: Mapping[str, object]) -> tuple[str, ...]:
    direct = _neural_id_list(config.get("input_ids"))
    if direct:
        return direct
    intervention = config.get("intervention")
    if not isinstance(intervention, Mapping):
        return ()
    for key in ("input_ids", "stimulus_ids"):
        candidate = _neural_id_list(intervention.get(key))
        if candidate:
            return candidate
    parameters = intervention.get("parameters")
    if isinstance(parameters, Mapping):
        for key in ("input_ids", "stimulus_ids"):
            candidate = _neural_id_list(parameters.get(key))
            if candidate:
                return candidate
    return ()


def _neural_silence_ids(config: Mapping[str, object]) -> tuple[str, ...]:
    direct = _neural_id_list(config.get("silence_ids"))
    if direct:
        return direct
    intervention = config.get("intervention")
    if not isinstance(intervention, Mapping):
        return ()
    for key in ("silence_ids", "outgoing_synapse_block_ids", "target_ids"):
        candidate = _neural_id_list(intervention.get(key))
        if candidate:
            return candidate
    parameters = intervention.get("parameters")
    if isinstance(parameters, Mapping):
        for key in ("silence_ids", "outgoing_synapse_block_ids", "target_ids"):
            candidate = _neural_id_list(parameters.get(key))
            if candidate:
                return candidate
    return ()


def _neural_readout_ids(config: Mapping[str, object]) -> tuple[str, ...]:
    direct = _neural_id_list(config.get("readout_ids"))
    if direct:
        return direct
    requirements = config.get("backend_requirements")
    if isinstance(requirements, Mapping):
        return _neural_id_list(requirements.get("readout_ids"))
    return ()


def _stimulus_schedule(config: Mapping[str, object]) -> object | None:
    direct = config.get("stimulus_schedule")
    if direct is not None:
        return direct
    intervention = config.get("intervention")
    if not isinstance(intervention, Mapping):
        return None
    parameters = intervention.get("parameters")
    if isinstance(parameters, Mapping):
        return parameters.get("stimulus_schedule")
    return None


def default_adapters(
    *,
    repo_root: str | Path | None = None,
    interpreter: str | Path | None = None,
    neural_repo_root: str | Path | None = None,
    neural_interpreter: str | Path | None = None,
) -> dict[str, BackendAdapter]:
    adapters: dict[str, BackendAdapter] = {
        "flygym_healthy": HealthyBaselineAdapter(repo_root, interpreter),
        "flygym_brain_driven": BrainDrivenAdapter(repo_root, interpreter),
    }
    if neural_repo_root is not None and neural_interpreter is not None:
        adapters["lif_2024"] = NeuralLifAdapter(
            neural_repo_root=neural_repo_root,
            neural_interpreter=neural_interpreter,
        )
        adapters["neural_bridge"] = NeuralBridgeAdapter(
            neural_repo_root=neural_repo_root,
            neural_interpreter=neural_interpreter,
            platform_root=repo_root,
            platform_interpreter=interpreter,
        )
    return adapters


def _display_command(command: Sequence[str]) -> str:
    return " ".join(_quote(item) for item in command)


def _quote(value: str) -> str:
    if not value or any(char.isspace() for char in value) or '"' in value:
        return '"' + value.replace('"', '\\"') + '"'
    return value


__all__ = [
    "BackendAdapter",
    "BackendRunContext",
    "BackendRunResult",
    "BrainDrivenAdapter",
    "CommandBackendAdapter",
    "HealthyBaselineAdapter",
    "NeuralLifAdapter",
    "NeuralBridgeAdapter",
    "default_adapters",
]
