"""Shared orchestration service for the workbench CLI and local API."""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import re
import subprocess
import sys
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any, Mapping, Sequence

from .adapters import BackendAdapter, BackendRunContext, BackendRunResult, default_adapters
from .assays import AssayAdapter, LocomotionAssayAdapter, NeuralReadoutAssayAdapter
from .benchmark import (
    BenchmarkProtocol,
    compare_benchmark_systems,
    evaluate_retrospective_benchmark,
    summarize_sensitivity,
)
from .confirmation import build_confirmation_plan as make_confirmation_plan
from .handoff import (
    REVIEW_DECISIONS,
    build_evidence_bundle,
    default_review,
    write_evidence_bundle,
)
from .models import (
    DecisionReport,
    JobRecord,
    JobStatus,
    RunManifest,
    StudySpec,
    jsonable,
    stable_hash,
    utc_timestamp,
)
from .ranking import RankingPolicy, rank_candidates
from .store import WorkbenchStore


_INTERPRETER_SNAPSHOT_CACHE: dict[str, dict[str, Any]] = {}


class WorkbenchService:
    """Coordinate validated studies and one subprocess job at a time."""

    def __init__(
        self,
        *,
        store: WorkbenchStore,
        artifact_root: str | Path,
        adapters: Mapping[str, BackendAdapter] | None = None,
        assays: Mapping[str, AssayAdapter] | None = None,
    ) -> None:
        self.store = store
        self.artifact_root = Path(artifact_root).resolve()
        self.artifact_root.mkdir(parents=True, exist_ok=True)
        self.adapters: dict[str, BackendAdapter] = dict(adapters or default_adapters())
        self.assays: dict[str, AssayAdapter] = dict(
            assays
            or {
                "locomotion": LocomotionAssayAdapter(),
                "neural": NeuralReadoutAssayAdapter(),
                "sensory_mn9": NeuralReadoutAssayAdapter(),
            }
        )
        self._run_lock = threading.Lock()
        self._active_processes: dict[str, subprocess.Popen[str]] = {}
        self._cancel_events: dict[str, threading.Event] = {}
        self._active_lock = threading.RLock()

    def capabilities(self) -> list[dict[str, Any]]:
        return [self.adapters[name].describe().as_dict() for name in sorted(self.adapters)]

    def evaluate_benchmark(
        self,
        protocol: BenchmarkProtocol,
        predictions: Mapping[str, Any],
        *,
        evaluation_split: str = "all",
    ) -> dict[str, Any]:
        return evaluate_retrospective_benchmark(
            protocol,
            predictions,
            evaluation_split=evaluation_split,
        )

    def compare_benchmark_systems(
        self,
        protocol: BenchmarkProtocol,
        predictions_by_system: Mapping[str, Mapping[str, Any]],
        *,
        evaluation_split: str = "held_out",
    ) -> dict[str, Any]:
        return compare_benchmark_systems(
            protocol,
            predictions_by_system,
            evaluation_split=evaluation_split,
        )

    def sensitivity_report(self, runs: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        return summarize_sensitivity(runs)

    def rank_observations(
        self,
        observations: Sequence[Mapping[str, Any]],
        policy: RankingPolicy,
    ) -> dict[str, Any]:
        """Apply one study/assay/metric ranking policy to paired observations."""

        return rank_candidates(observations, policy)

    def collect_ranking_observations(
        self,
        study_id: str,
        policy: RankingPolicy,
    ) -> dict[str, Any]:
        """Build paired observations from completed jobs without guessing metadata.

        A job contributes only when its candidate, explicit seed, result
        readout, and matching control are identifiable.  Missing or conflicting
        fields are reported as ``unpaired_jobs`` rather than being filled from
        job order, attempt number, or another implicit convention.
        """

        study = self.get_study(study_id)
        if policy.study_id is not None and policy.study_id != study_id:
            raise ValueError("ranking policy study_id does not match the selected study")
        if not policy.control_candidate_id:
            raise ValueError("rank-study requires policy.control_candidate_id")

        candidate_ids = {candidate.candidate_id for candidate in study.candidates}
        if str(policy.control_candidate_id) not in candidate_ids:
            raise ValueError("ranking policy control_candidate_id is not declared in StudySpec")
        source_jobs: list[dict[str, Any]] = []
        unpaired_jobs: list[dict[str, Any]] = []
        controls: dict[tuple[str, str], dict[str, Any]] = {}
        control_errors: dict[tuple[str, str], str] = {}
        candidate_records: list[dict[str, Any]] = []

        for job in self.list_jobs(study_id=study_id):
            candidate_id = str(job.config.get("candidate_id", "")).strip()
            source = _job_source_summary(job)
            source_jobs.append(source)
            if not candidate_id:
                unpaired_jobs.append(_unpaired_job(job, "missing candidate_id"))
                continue
            if candidate_id not in candidate_ids and candidate_id != policy.control_candidate_id:
                unpaired_jobs.append(_unpaired_job(job, "candidate_id is not declared in StudySpec"))
                continue
            if job.status != JobStatus.COMPLETED or not job.artifact_dir:
                unpaired_jobs.append(_unpaired_job(job, f"job status is {job.status.value}, not COMPLETED"))
                continue

            adapter = self._adapter(job.backend)
            payload = _read_result_payload(
                Path(job.artifact_dir),
                preferred_path=getattr(adapter, "result_path", None),
            )
            seed, seed_error = _extract_job_seed(payload, job.config)
            if seed_error is not None:
                unpaired_jobs.append(_unpaired_job(job, seed_error))
                continue
            metric_value, metric_error = _extract_metric_value(payload, study.primary_metric)
            assay_evaluation = self._evaluate_job_payload(study.assay, payload)
            pairing_key = _job_pairing_key(job.config, job.backend)
            record = {
                "job_id": job.job_id,
                "run_id": job.run_id,
                "candidate_id": candidate_id,
                "seed": seed,
                "value": metric_value,
                "metric_error": metric_error,
                "assay_evaluation": assay_evaluation,
                "manifest_path": job.manifest_path,
                "artifact_dir": job.artifact_dir,
                "payload": payload,
                "pairing_key": pairing_key,
                "phase": _pairing_phase(job.config),
            }
            if candidate_id == policy.control_candidate_id:
                control_key = (pairing_key, str(seed))
                if control_key in controls:
                    control_errors[control_key] = "duplicate_control_seed_within_pairing_scope"
                    controls.pop(control_key, None)
                elif control_key not in control_errors:
                    controls[control_key] = record
            else:
                candidate_records.append(record)

        observations: list[dict[str, Any]] = []
        for record in candidate_records:
            seed_key = str(record["seed"])
            control_key = (str(record["pairing_key"]), seed_key)
            control = controls.get(control_key)
            if control is None:
                reason = control_errors.get(control_key, "missing matching control job for seed")
                unpaired_jobs.append(
                    _unpaired_job(
                        self.get_job(str(record["job_id"])),
                        reason,
                    )
                )
                continue
            candidate_spec = next(
                candidate for candidate in study.candidates if candidate.candidate_id == record["candidate_id"]
            )
            candidate_qc = record["assay_evaluation"]
            control_qc = control["assay_evaluation"]
            qc_pass = bool(candidate_qc["qc_pass"] and control_qc["qc_pass"])
            qc_status = "PASS" if qc_pass else (
                f"candidate={candidate_qc['status']};control={control_qc['status']}"
            )
            direction = candidate_spec.expected_direction
            if direction not in {"increase", "decrease", "any"}:
                direction = None
            observations.append(
                {
                    "study_id": study_id,
                    "candidate_id": record["candidate_id"],
                    "assay": study.assay,
                    "primary_metric": study.primary_metric,
                    "seed": record["seed"],
                    "value": record["value"],
                    "control_value": control["value"],
                    "qc_pass": qc_pass,
                    "qc_status": qc_status,
                    "expected_direction": direction,
                    "metadata": {
                        "candidate_label": candidate_spec.label,
                        "candidate_expected_direction": candidate_spec.expected_direction,
                        "job_id": record["job_id"],
                        "control_job_id": control["job_id"],
                        "run_id": record["run_id"],
                        "control_run_id": control["run_id"],
                        "manifest_path": record["manifest_path"],
                        "control_manifest_path": control["manifest_path"],
                        "metric_error": record["metric_error"],
                        "control_metric_error": control["metric_error"],
                        "pairing_key": record["pairing_key"],
                        "phase": record["phase"],
                    },
                }
            )

        declared_candidate_ids = sorted(
            candidate_ids - {str(policy.control_candidate_id)}
        )
        observed_candidate_ids = sorted({str(item["candidate_id"]) for item in observations})
        missing_candidate_ids = sorted(set(declared_candidate_ids) - set(observed_candidate_ids))
        collection_status = (
            "READY"
            if observations and not unpaired_jobs and not missing_candidate_ids
            else "INCOMPLETE"
        )

        return {
            "study_id": study_id,
            "assay": study.assay,
            "primary_metric": study.primary_metric,
            "control_candidate_id": policy.control_candidate_id,
            "status": collection_status,
            "observations": observations,
            "unpaired_jobs": unpaired_jobs,
            "source_jobs": source_jobs,
            "declared_candidate_ids": declared_candidate_ids,
            "observed_candidate_ids": observed_candidate_ids,
            "missing_candidate_ids": missing_candidate_ids,
            "candidate_coverage": (
                len(observed_candidate_ids) / len(declared_candidate_ids)
                if declared_candidate_ids
                else 0.0
            ),
            "notes": [
                "Only explicit seed values from job configuration or backend result metadata are used.",
                "Control values are paired by exact seed plus phase, sensitivity case, backend, and shared configuration scope; job order and attempt number are never used as a seed.",
                "A paired observation with failed assay QC is retained for diagnosis but cannot enter ranking.",
                "A collection is incomplete until every non-control candidate declared in the StudySpec has at least one paired observation.",
            ],
        }

    def rank_study(self, study_id: str, policy: RankingPolicy) -> dict[str, Any]:
        """Collect job outputs, rank them, and persist an auditable report."""

        collection = self.collect_ranking_observations(study_id, policy)
        ranking = self.rank_observations(collection["observations"], policy)
        source_manifests = [
            item for item in collection["source_jobs"] if item.get("manifest_path")
        ]
        report = {
            "report_version": 1,
            "study_id": study_id,
            "generated_at": utc_timestamp(),
            "status": "READY" if collection["status"] == "READY" else "INCOMPLETE",
            "collection": collection,
            "ranking": ranking,
            "provenance": {
                "policy_hash": stable_hash(policy.as_dict()),
                "collection_hash": stable_hash(collection),
                "source_manifests": source_manifests,
            },
            "scientific_scope": (
                "Ranking is a computational prioritization aid; it is not biological validation, "
                "equivalence, or permission to eliminate a wet-lab direction."
            ),
        }
        target = self.artifact_root / _safe_component(study_id) / "ranking_report.json"
        report["report_path"] = target.as_posix()
        _write_json(target, report)
        return report

    def confirmation_plan(
        self,
        study_id: str,
        *,
        top_k: int = 3,
        explicit_seeds: Sequence[int | str] | None = None,
        sensitivity_grid: Any = None,
    ) -> dict[str, Any]:
        """Create a fresh-seed confirmation plan without submitting jobs."""

        study = self.get_study(study_id)
        ranking_report = self._load_ranking_report(study_id)
        adapter = self._adapter(study.backend)
        capability = adapter.describe()
        plan = make_confirmation_plan(
            study,
            ranking_report,
            self.get_review(study_id),
            top_k=top_k,
            explicit_seeds=explicit_seeds,
            sensitivity_grid=sensitivity_grid,
            backend_name=capability.name,
            backend_seed_capable=capability.supports_explicit_seed,
            backend_parameter_override_capable=capability.supports_parameter_overrides,
        )
        target = self.artifact_root / _safe_component(study_id) / "confirmation_plan.json"
        plan["plan_path"] = target.as_posix()
        _write_json(target, plan)
        return plan

    def submit_confirmation_plan(
        self,
        study_id: str,
        plan: Mapping[str, Any] | None = None,
        *,
        include_sensitivity: bool = False,
    ) -> dict[str, Any]:
        """Submit a confirmation plan after capability checks.

        Base confirmation jobs are submitted by default.  Sensitivity reruns
        are opt-in so a declared grid cannot silently multiply the campaign.
        """

        study = self.get_study(study_id)
        selected_plan = dict(plan or self._load_confirmation_plan(study_id))
        if selected_plan.get("study_id") != study_id:
            raise ValueError("confirmation plan study_id does not match selected study")
        if selected_plan.get("status") != "READY_FOR_SUBMISSION" or not selected_plan.get("ready_for_submission"):
            raise ValueError(
                "confirmation plan is not ready for submission: "
                + ", ".join(str(item) for item in selected_plan.get("blocked_reasons", ()))
            )
        adapter = self._adapter(study.backend)
        capability = adapter.describe()
        if not capability.supports_explicit_seed:
            raise ValueError(
                f"backend {study.backend!r} does not declare explicit seed passthrough"
            )
        sensitivity = selected_plan.get("sensitivity", {})
        sensitivity_cases = sensitivity.get("cases", ()) if isinstance(sensitivity, Mapping) else ()
        if include_sensitivity:
            if not capability.supports_parameter_overrides:
                raise ValueError(
                    f"backend {study.backend!r} does not declare parameter override passthrough"
                )
            if not isinstance(sensitivity, Mapping) or sensitivity.get("status") != "DECLARED":
                raise ValueError("confirmation plan has no valid declared sensitivity grid")
            if not isinstance(sensitivity_cases, Sequence) or isinstance(sensitivity_cases, (str, bytes)) or not sensitivity_cases:
                raise ValueError("confirmation plan sensitivity cases are empty")

        plan_hash = stable_hash(selected_plan)
        job_specs: list[tuple[str, dict[str, Any]]] = []
        sensitivity_job_ids: list[str] = []
        for item in selected_plan.get("control_jobs", ()):
            seed = item.get("seed")
            job_id = _confirmation_job_id("control", str(seed))
            job_specs.append(
                (
                    job_id,
                    {
                        "candidate_id": item.get("candidate_id"),
                        "seed": seed,
                        "phase": "confirmation_control",
                        "confirmation_plan_hash": plan_hash,
                        "fresh_seed": bool(item.get("fresh_seed")),
                    },
                )
            )
        for candidate in selected_plan.get("candidates", ()):
            for item in candidate.get("confirmation_jobs", ()):
                seed = item.get("seed")
                candidate_id = str(item.get("candidate_id"))
                job_id = _confirmation_job_id(candidate_id, str(seed))
                job_specs.append(
                    (
                        job_id,
                        {
                            "candidate_id": candidate_id,
                            "control_candidate_id": item.get("control_candidate_id"),
                            "seed": seed,
                            "phase": "confirmation",
                            "source_rank": item.get("source_rank"),
                            "confirmation_plan_hash": plan_hash,
                            "fresh_seed": bool(item.get("fresh_seed")),
                        },
                    )
                )
        if include_sensitivity:
            control_candidate_id = selected_plan.get("control_candidate_id")
            fresh_seeds = selected_plan.get("fresh_seeds", ())
            if not isinstance(fresh_seeds, Sequence) or isinstance(fresh_seeds, (str, bytes)):
                raise ValueError("confirmation plan fresh_seeds must be a list")
            for case_index, raw_case in enumerate(sensitivity_cases):
                if not isinstance(raw_case, Mapping):
                    raise ValueError("confirmation plan sensitivity case must be an object")
                overrides = dict(raw_case)
                for seed in fresh_seeds:
                    job_id = _confirmation_job_id(
                        f"sensitivity-control-case-{case_index}",
                        str(seed),
                    )
                    sensitivity_job_ids.append(job_id)
                    job_specs.append(
                        (
                            job_id,
                            {
                                "candidate_id": control_candidate_id,
                                "seed": seed,
                                "phase": "confirmation_sensitivity_control",
                                "parameter_overrides": overrides,
                                "sensitivity_case_index": case_index,
                                "sensitivity_case": overrides,
                                "confirmation_plan_hash": plan_hash,
                                "fresh_seed": True,
                            },
                        )
                    )
                for candidate in selected_plan.get("candidates", ()):
                    candidate_id = str(candidate.get("candidate_id"))
                    source_rank = candidate.get("source_rank")
                    for seed in fresh_seeds:
                        job_id = _confirmation_job_id(
                            f"sensitivity-{candidate_id}-case-{case_index}",
                            str(seed),
                        )
                        sensitivity_job_ids.append(job_id)
                        job_specs.append(
                            (
                                job_id,
                                {
                                    "candidate_id": candidate_id,
                                    "control_candidate_id": control_candidate_id,
                                    "seed": seed,
                                    "phase": "confirmation_sensitivity",
                                    "source_rank": source_rank,
                                    "parameter_overrides": overrides,
                                    "sensitivity_case_index": case_index,
                                    "sensitivity_case": overrides,
                                    "confirmation_plan_hash": plan_hash,
                                    "fresh_seed": True,
                                },
                            )
                        )
        if not job_specs:
            raise ValueError("confirmation plan contains no jobs")
        if len({job_id for job_id, _config in job_specs}) != len(job_specs):
            raise ValueError("confirmation plan contains duplicate job IDs")

        validation_errors: list[dict[str, Any]] = []
        validation_dir = self.artifact_root / _safe_component(study_id) / "confirmation-validation"
        for job_id, config in job_specs:
            resolved_config = self._materialize_candidate_config(study, config)
            errors = adapter.validate(study, {**resolved_config, "_artifact_dir": validation_dir})
            if errors:
                validation_errors.append({"job_id": job_id, "errors": list(errors)})
        if validation_errors:
            raise ValueError(f"confirmation plan backend validation failed: {validation_errors}")

        jobs: list[JobRecord] = []
        errors: list[dict[str, Any]] = []
        for job_id, config in job_specs:
            resolved_config = self._materialize_candidate_config(study, config)
            try:
                existing = self.get_job(job_id)
            except KeyError:
                existing = None
            if existing is not None:
                if existing.study_id != study_id or stable_hash(existing.config) != stable_hash(resolved_config):
                    errors.append({"job_id": job_id, "reason": "job_id already exists with different configuration"})
                else:
                    jobs.append(existing)
                continue
            try:
                jobs.append(self.submit_job(study_id, resolved_config, backend=study.backend, job_id=job_id))
            except (KeyError, ValueError, TypeError, OSError) as error:
                errors.append({"job_id": job_id, "reason": f"{type(error).__name__}: {error}"})

        status = "SUBMITTED" if not errors else "PARTIAL"
        report = {
            "submission_version": 1,
            "study_id": study_id,
            "status": status,
            "backend": study.backend,
            "backend_capability": capability.as_dict(),
            "confirmation_plan_hash": plan_hash,
            "include_sensitivity": bool(include_sensitivity),
            "sensitivity_case_count": len(sensitivity_cases) if include_sensitivity else 0,
            "sensitivity_job_count": len(sensitivity_job_ids),
            "sensitivity_job_ids": sensitivity_job_ids,
            "submitted_job_count": len(jobs),
            "job_ids": [job.job_id for job in jobs],
            "jobs": [job.as_dict() for job in jobs],
            "errors": errors,
            "scientific_scope": (
                "Jobs are submitted for computational confirmation only; submission is not biological confirmation."
            ),
        }
        target = self.artifact_root / _safe_component(study_id) / "confirmation_submission.json"
        report["submission_path"] = target.as_posix()
        _write_json(target, report)
        return report

    def run_confirmation(self, study_id: str) -> dict[str, Any]:
        """Run only pending jobs recorded by the confirmation submission."""

        study = self.get_study(study_id)
        submission = self._load_confirmation_submission(study_id)
        if not submission:
            raise ValueError("no confirmation submission exists for this study")
        job_ids = submission.get("job_ids", ())
        if not isinstance(job_ids, Sequence) or isinstance(job_ids, (str, bytes)) or not job_ids:
            raise ValueError("confirmation submission contains no job_ids")

        records: list[JobRecord] = []
        errors: list[dict[str, Any]] = []
        for raw_job_id in job_ids:
            job_id = str(raw_job_id)
            try:
                job = self.get_job(job_id)
            except KeyError:
                errors.append({"job_id": job_id, "reason": "job no longer exists"})
                continue
            if job.study_id != study_id or job.backend != study.backend:
                errors.append({"job_id": job_id, "reason": "job scope does not match confirmation study"})
                continue
            if job.status == JobStatus.PENDING:
                try:
                    job = self.run_job(job_id)
                except (KeyError, ValueError, OSError) as error:
                    errors.append({"job_id": job_id, "reason": f"{type(error).__name__}: {error}"})
                    continue
            elif job.status in {JobStatus.FAILED, JobStatus.CANCELLED}:
                errors.append({"job_id": job_id, "reason": f"job is {job.status.value}; resume explicitly before rerun"})
            records.append(job)

        completed = [job for job in records if job.status == JobStatus.COMPLETED]
        status = "COMPLETED" if len(completed) == len(job_ids) and not errors else (
            "PARTIAL" if completed else "FAILED"
        )
        report = {
            "confirmation_run_version": 1,
            "study_id": study_id,
            "status": status,
            "confirmation_plan_hash": submission.get("confirmation_plan_hash"),
            "job_ids": list(job_ids),
            "completed_job_count": len(completed),
            "jobs": [job.as_dict() for job in records],
            "errors": errors,
            "notes": [
                "Only jobs from confirmation_submission.json were considered.",
                "Failed or cancelled jobs require an explicit resume action.",
                "Completed computational jobs do not establish biological confirmation.",
            ],
        }
        target = self.artifact_root / _safe_component(study_id) / "confirmation_run.json"
        report["run_report_path"] = target.as_posix()
        _write_json(target, report)
        return report

    def create_study(self, study: StudySpec) -> StudySpec:
        # A study may be designed before its optional neural environment is
        # configured. Submission still requires a registered adapter.
        self.store.create_study(study)
        return study

    def get_study(self, study_id: str) -> StudySpec:
        return self.store.get_study(study_id)

    def list_studies(self) -> list[StudySpec]:
        return self.store.list_studies()

    def submit_job(
        self,
        study_id: str,
        config: Mapping[str, Any] | None = None,
        *,
        backend: str | None = None,
        job_id: str | None = None,
    ) -> JobRecord:
        study = self.get_study(study_id)
        selected_backend = backend or study.backend
        adapter = self._adapter(selected_backend)
        job_config = self._materialize_candidate_config(study, config or {})
        validation_config = dict(job_config)
        validation_config["_artifact_dir"] = self.artifact_root / _safe_component(study_id) / "validation"
        errors = adapter.validate(study, validation_config)
        if errors:
            raise ValueError("invalid job configuration: " + "; ".join(errors))
        job = JobRecord(
            job_id=job_id or f"job-{uuid.uuid4().hex[:12]}",
            study_id=study_id,
            backend=selected_backend,
            config=job_config,
        )
        self.store.create_job(job)
        return job

    @staticmethod
    def _materialize_candidate_config(
        study: StudySpec,
        config: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Copy the declared candidate contract into a persisted job config.

        A candidate ID alone is not an intervention.  Persisting the resolved
        intervention and its hash makes the command and later ranking audit
        able to prove which StudySpec candidate was executed.
        """

        job_config = dict(config)
        candidate_id = str(job_config.get("candidate_id", "")).strip()
        if not candidate_id:
            return job_config
        candidate = next((item for item in study.candidates if item.candidate_id == candidate_id), None)
        if candidate is None:
            return job_config

        intervention = dict(candidate.intervention)
        intervention_type = str(intervention.get("type", "none")).strip() or "none"
        job_config["intervention_type"] = intervention_type
        job_config["intervention"] = intervention
        job_config.setdefault("candidate_configuration_hash", stable_hash(candidate.as_dict()))

        backend_requirements = study.run_plan.get("backend_requirements", {})
        if isinstance(backend_requirements, Mapping):
            for key, value in backend_requirements.items():
                if key not in job_config and value is not None:
                    job_config[str(key)] = value
        if (
            intervention_type in {"activation", "outgoing_synapse_block"}
            and job_config.get("condition_label") is None
        ):
            job_config["condition_label"] = intervention_type

        parameters = intervention.get("parameters")
        if (
            intervention_type == "controller_parameter_override"
            and job_config.get("parameter_overrides") is None
            and isinstance(parameters, Mapping)
        ):
            job_config["parameter_overrides"] = dict(parameters)
        if isinstance(parameters, Mapping):
            for key in ("stimulus_rate_hz", "stimulus_schedule", "input_ids", "readout_ids"):
                if key in parameters and key not in job_config:
                    job_config[key] = jsonable(parameters[key])
        return job_config

    def get_job(self, job_id: str) -> JobRecord:
        return self.store.get_job(job_id)

    def list_jobs(self, *, study_id: str | None = None) -> list[JobRecord]:
        return self.store.list_jobs(study_id=study_id)

    def submit_screening(
        self,
        study_id: str,
        seeds: Sequence[int | str],
        *,
        candidate_ids: Sequence[str] | None = None,
        base_config: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Submit one explicit screening job per candidate and seed."""

        study = self.get_study(study_id)
        if not seeds:
            raise ValueError("screening requires at least one seed")
        normalized_seeds: list[int | str] = []
        for seed in seeds:
            if isinstance(seed, bool) or not isinstance(seed, (int, str)):
                raise ValueError("screening seeds must be integers or non-empty strings")
            if isinstance(seed, str) and not seed.strip():
                raise ValueError("screening seeds must be non-empty")
            if str(seed) in {str(item) for item in normalized_seeds}:
                raise ValueError("screening seeds must be unique")
            normalized_seeds.append(seed)

        declared_screening_repetitions = study.run_plan.get(
            "screening_seed_repetitions",
            study.run_plan.get("seed_repetitions"),
        )
        if declared_screening_repetitions is not None:
            try:
                expected_repetitions = int(declared_screening_repetitions)
            except (TypeError, ValueError) as error:
                raise ValueError("declared screening seed repetitions must be an integer") from error
            if expected_repetitions < 1:
                raise ValueError("declared screening seed repetitions must be positive")
            if len(normalized_seeds) != expected_repetitions:
                raise ValueError(
                    f"screening requires exactly {expected_repetitions} declared seeds; "
                    f"got {len(normalized_seeds)}"
                )

        declared = {candidate.candidate_id for candidate in study.candidates}
        selected = list(candidate_ids) if candidate_ids is not None else sorted(declared)
        if not selected:
            raise ValueError("screening requires at least one candidate")
        unknown = sorted(set(selected) - declared)
        if unknown:
            raise ValueError(f"screening candidate_ids are not declared in StudySpec: {unknown}")
        if len(selected) != len(set(selected)):
            raise ValueError("screening candidate_ids must be unique")

        jobs: list[JobRecord] = []
        errors: list[dict[str, Any]] = []
        common = dict(base_config or {})
        common.pop("candidate_id", None)
        common.pop("seed", None)
        for candidate_id in selected:
            for seed in normalized_seeds:
                job_id = _confirmation_job_id(f"screening-{candidate_id}", str(seed))
                config = {
                    **common,
                    "candidate_id": candidate_id,
                    "seed": seed,
                    "phase": "screening",
                }
                try:
                    existing = self.get_job(job_id)
                except KeyError:
                    existing = None
                if existing is not None:
                    if existing.study_id != study_id or stable_hash(existing.config) != stable_hash(
                        self._materialize_candidate_config(study, config)
                    ):
                        errors.append({"job_id": job_id, "reason": "job_id exists with different configuration"})
                    else:
                        jobs.append(existing)
                    continue
                try:
                    jobs.append(self.submit_job(study_id, config, backend=study.backend, job_id=job_id))
                except (KeyError, ValueError, TypeError, OSError) as error:
                    errors.append({"job_id": job_id, "reason": f"{type(error).__name__}: {error}"})

        report = {
            "submission_version": 1,
            "study_id": study_id,
            "phase": "screening",
            "backend": study.backend,
            "candidate_ids": selected,
            "seeds": normalized_seeds,
            "expected_job_count": len(selected) * len(normalized_seeds),
            "submitted_job_count": len(jobs),
            "job_ids": [job.job_id for job in jobs],
            "jobs": [job.as_dict() for job in jobs],
            "errors": errors,
            "status": "SUBMITTED" if not errors else "PARTIAL",
            "scientific_scope": "Screening submission only; jobs are computational and not biological confirmation.",
        }
        target = self.artifact_root / _safe_component(study_id) / "screening_submission.json"
        report["submission_path"] = target.as_posix()
        _write_json(target, report)
        return report

    def run_screening(self, study_id: str) -> dict[str, Any]:
        """Run only jobs in the persisted screening submission."""

        study = self.get_study(study_id)
        path = self.artifact_root / _safe_component(study_id) / "screening_submission.json"
        if not path.is_file():
            raise ValueError("no screening submission exists for this study")
        try:
            submission = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError("screening submission is not valid JSON") from error
        if not isinstance(submission, Mapping):
            raise ValueError("screening submission must be an object")
        records: list[JobRecord] = []
        errors: list[dict[str, Any]] = []
        for raw_job_id in submission.get("job_ids", ()):
            job_id = str(raw_job_id)
            try:
                job = self.get_job(job_id)
                if job.study_id != study_id or job.backend != study.backend:
                    raise ValueError("job scope does not match screening study")
                if job.status == JobStatus.PENDING:
                    job = self.run_job(job_id)
                records.append(job)
            except (KeyError, ValueError, OSError) as error:
                errors.append({"job_id": job_id, "reason": f"{type(error).__name__}: {error}"})
        completed = sum(job.status == JobStatus.COMPLETED for job in records)
        report = {
            "run_version": 1,
            "study_id": study_id,
            "job_ids": list(submission.get("job_ids", ())),
            "completed_job_count": completed,
            "jobs": [job.as_dict() for job in records],
            "errors": errors,
            "status": "COMPLETED" if completed == len(records) and not errors else "PARTIAL",
            "scientific_scope": "Screening run only; completed jobs are not biological confirmation.",
        }
        target = self.artifact_root / _safe_component(study_id) / "screening_run.json"
        report["run_report_path"] = target.as_posix()
        _write_json(target, report)
        return report

    def cancel_job(self, job_id: str) -> JobRecord:
        job = self.get_job(job_id)
        if job.status == JobStatus.PENDING:
            job.status = JobStatus.CANCELLED
            job.finished_at = utc_timestamp()
            job.error = "cancelled before execution"
            return self.store.update_job(job, event="cancelled")
        if job.status == JobStatus.RUNNING:
            with self._active_lock:
                event = self._cancel_events.get(job_id)
                process = self._active_processes.get(job_id)
                if event is not None:
                    event.set()
                if process is not None and process.poll() is None:
                    process.terminate()
            self.store.update_job(job, event="cancel_requested")
            return self.get_job(job_id)
        raise ValueError(f"cannot cancel job in state {job.status.value}")

    def resume_job(self, job_id: str) -> JobRecord:
        job = self.get_job(job_id)
        if job.status not in {JobStatus.FAILED, JobStatus.CANCELLED}:
            raise ValueError(f"only failed or cancelled jobs can resume: {job.status.value}")
        job.status = JobStatus.PENDING
        job.error = None
        job.started_at = None
        job.finished_at = None
        job.run_id = None
        job.artifact_dir = None
        job.manifest_path = None
        return self.store.update_job(job, event="resumed")

    def run_pending(self) -> JobRecord | None:
        self.recover_stale_jobs()
        job = self.store.next_pending_job()
        return None if job is None else self.run_job(job.job_id)

    def recover_stale_jobs(self, *, stale_after_s: float = 3600.0) -> list[JobRecord]:
        """Mark abandoned RUNNING jobs as failed after a worker crash.

        Recovery is conservative: a live worker lock prevents recovery, and a
        job must have an older ``started_at`` than the declared threshold.
        Resuming the returned jobs remains an explicit user action.
        """

        if stale_after_s < 0:
            raise ValueError("stale_after_s must be non-negative")
        lock_path = self.artifact_root / ".worker.lock"
        if lock_path.exists() and not _stale_worker_lock(lock_path):
            return []
        now = datetime.now(UTC)
        recovered: list[JobRecord] = []
        for job in self.list_jobs():
            if job.status != JobStatus.RUNNING or not job.started_at:
                continue
            try:
                started = datetime.fromisoformat(job.started_at)
            except ValueError:
                continue
            age_s = (now - started).total_seconds()
            if age_s < stale_after_s:
                continue
            with self._active_lock:
                if job.job_id in self._active_processes:
                    continue
            job.status = JobStatus.FAILED
            job.finished_at = utc_timestamp()
            job.error = f"stale RUNNING job recovered after {age_s:.1f}s; resume explicitly"
            recovered.append(self.store.update_job(job, event="stale_worker_recovered"))
        return recovered

    def run_job(self, job_id: str) -> JobRecord:
        """Run a single pending job, with a distinct run directory and manifest."""

        with self._run_lock, self._worker_file_lock():
            job = self.get_job(job_id)
            if job.status != JobStatus.PENDING:
                raise ValueError(f"job is not pending: {job.status.value}")
            study = self.get_study(job.study_id)
            adapter = self._adapter(job.backend)
            job.attempt += 1
            job.status = JobStatus.RUNNING
            job.started_at = utc_timestamp()
            job.finished_at = None
            run_id = f"{_safe_component(job.job_id)}-a{job.attempt}-{uuid.uuid4().hex[:8]}"
            run_dir = self.artifact_root / _safe_component(study.study_id) / "runs" / run_id
            job.run_id = run_id
            job.artifact_dir = run_dir.as_posix()
            self.store.claim_job(job, event="started")
            pre_run_provenance = _pre_run_provenance(adapter)

            cancel_event = threading.Event()
            with self._active_lock:
                self._cancel_events[job_id] = cancel_event

            try:
                run_dir.mkdir(parents=True, exist_ok=False)
                validation_config = dict(job.config)
                validation_config["_artifact_dir"] = run_dir
                validation_errors = adapter.validate(study, validation_config)
                if validation_errors:
                    result = BackendRunResult(
                        command=(),
                        interpreter="",
                        repo_root="",
                        exit_code=None,
                        error="invalid job configuration: " + "; ".join(validation_errors),
                    )
                else:
                    context = BackendRunContext(
                        job=job,
                        study=study,
                        run_id=run_id,
                        artifact_dir=run_dir,
                        log_path=run_dir / "run.log",
                        cancel_event=cancel_event,
                        register_process=lambda process: self._register_process(job_id, process),
                    )
                    result = adapter.run(context)
            except Exception as error:  # backend failures must become auditable job failures
                result = BackendRunResult(
                    command=(),
                    interpreter="",
                    repo_root="",
                    exit_code=None,
                    error=f"{type(error).__name__}: {error}",
                )

            status = _status_from_result(result)
            job.status = status
            job.finished_at = utc_timestamp()
            job.error = result.error
            manifest = self._write_run_manifest(
                job,
                study,
                adapter,
                run_dir,
                result,
                status,
                pre_run_provenance=pre_run_provenance,
            )
            job.manifest_path = manifest.as_posix()
            self.store.update_job(job, event=_event_for_status(status))
            with self._active_lock:
                self._active_processes.pop(job_id, None)
                self._cancel_events.pop(job_id, None)
            return job

    def get_report(self, study_id: str) -> dict[str, Any]:
        study = self.get_study(study_id)
        jobs = self.list_jobs(study_id=study_id)
        rows: list[dict[str, Any]] = []
        for job in jobs:
            row: dict[str, Any] = {
                "job_id": job.job_id,
                "backend": job.backend,
                "candidate_id": job.config.get("candidate_id"),
                "status": job.status.value,
                "attempt": job.attempt,
                "run_id": job.run_id,
                "error": job.error,
                "metrics": {},
            }
            if job.artifact_dir:
                adapter = self._adapter(job.backend)
                row["metrics"] = _read_result_metrics(
                    Path(job.artifact_dir),
                    preferred_path=getattr(adapter, "result_path", None),
                )
            assay = self._assay_for(study.assay)
            if assay is not None:
                row["qc"] = assay.evaluate(row["metrics"]).as_dict()
            rows.append(row)
        completed = [row for row in rows if row["status"] == JobStatus.COMPLETED.value]
        report = DecisionReport(
            study_id=study_id,
            generated_at=utc_timestamp(),
            status="ready" if completed else ("incomplete" if rows else "no_runs"),
            results=tuple(rows),
            uncertainty={
                "status": "not_computed",
                "seed_repetitions": study.run_plan.get("seed_repetitions"),
                "note": "v0.1 does not treat computational seeds as biological replicates.",
            },
            limitations=(
                "Use rank-study with a declared control and explicit paired seeds before interpreting candidate priority.",
                "A completed subprocess indicates computational completion, not biological validation.",
                "Model scope and missing mechanisms remain backend-specific.",
            ),
            recommendations=(
                "Review the run manifest and raw backend report before proposing a wet-lab test.",
                "Record the control, experimental unit, randomization, blinding, and primary readout in the study spec.",
            ),
            ranking_eligible=False,
        )
        target = self.artifact_root / _safe_component(study_id) / "decision_report.json"
        _write_json(target, report.as_dict())
        return report.as_dict()

    def compare_jobs(
        self,
        study_id: str,
        reference_job_id: str,
        condition_job_id: str,
    ) -> dict[str, Any]:
        """Compare two completed outputs through the registered assay only."""

        study = self.get_study(study_id)
        reference = self.get_job(reference_job_id)
        condition = self.get_job(condition_job_id)
        if reference.study_id != study_id or condition.study_id != study_id:
            raise ValueError("comparison jobs must belong to the selected study")
        if reference.status != JobStatus.COMPLETED or condition.status != JobStatus.COMPLETED:
            raise ValueError("comparison requires two completed jobs")
        assay = self._assay_for(study.assay)
        if assay is None:
            raise ValueError(f"no assay adapter is registered for {study.assay}")
        adapter = self._adapter(study.backend)
        preferred_path = getattr(adapter, "result_path", None)
        reference_payload = _read_result_payload(
            Path(str(reference.artifact_dir)), preferred_path=preferred_path
        )
        condition_payload = _read_result_payload(
            Path(str(condition.artifact_dir)), preferred_path=preferred_path
        )
        return dict(
            assay.compare(
                reference_payload,
                condition_payload,
                primary_metric=study.primary_metric,
            )
        )

    def get_review(self, study_id: str) -> dict[str, Any]:
        self.get_study(study_id)
        return self.store.get_review(study_id) or default_review()

    def record_review(
        self,
        study_id: str,
        *,
        reviewer: Mapping[str, Any] | str | None,
        decision: str,
        comments: str = "",
    ) -> dict[str, Any]:
        study = self.get_study(study_id)
        normalized_decision = str(decision).strip().lower()
        if normalized_decision not in REVIEW_DECISIONS:
            raise ValueError(f"unsupported review decision: {normalized_decision}")
        if isinstance(reviewer, str):
            reviewer_payload: Any = {"name": reviewer} if reviewer.strip() else None
        else:
            reviewer_payload = dict(reviewer) if reviewer is not None else None
        if normalized_decision == "approved" and not reviewer_payload:
            raise ValueError("an approved bundle requires a reviewer")
        ranking_report = self._load_ranking_report(study_id)
        review = {
            "reviewer": reviewer_payload,
            "decision": normalized_decision,
            "comments": str(comments),
            "reviewed_at": utc_timestamp(),
            "study_configuration_hash": study.configuration_hash,
            "ranking_report_hash": stable_hash(ranking_report) if ranking_report else None,
        }
        return self.store.set_review(study_id, review)

    def get_evidence_bundle(self, study_id: str) -> dict[str, Any]:
        study = self.get_study(study_id)
        report = self.get_report(study_id)
        manifests: list[dict[str, Any]] = []
        for job in self.list_jobs(study_id=study_id):
            if not job.manifest_path:
                continue
            path = Path(job.manifest_path)
            if not path.is_file():
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(payload, Mapping):
                item = dict(payload)
                item["manifest_path"] = path.as_posix()
                manifests.append(item)
        bundle = build_evidence_bundle(
            study,
            report,
            manifests,
            review=self.get_review(study_id),
            ranking_report=self._load_ranking_report(study_id),
            confirmation_submission=self._load_confirmation_submission(study_id),
            confirmation_run=self._load_confirmation_run(study_id),
        )
        return bundle.as_dict()

    def export_evidence_bundle(self, study_id: str, target: str | Path | None = None) -> Path:
        bundle = build_evidence_bundle(
            self.get_study(study_id),
            self.get_report(study_id),
            self._load_run_manifests(study_id),
            review=self.get_review(study_id),
            ranking_report=self._load_ranking_report(study_id),
            confirmation_submission=self._load_confirmation_submission(study_id),
            confirmation_run=self._load_confirmation_run(study_id),
        )
        output = Path(target) if target is not None else self.artifact_root / _safe_component(study_id) / "evidence_bundle"
        return write_evidence_bundle(bundle, output)

    def events(self, entity_type: str, entity_id: str) -> list[dict[str, Any]]:
        return self.store.events(entity_type, entity_id)

    def _evaluate_job_payload(self, assay_name: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        assay = self._assay_for(assay_name)
        if assay is None:
            return {
                "assay": assay_name,
                "status": "NO_ASSAY_ADAPTER",
                "readout_available": False,
                "qc_pass": False,
                "metrics": {},
                "warnings": (f"no assay adapter registered for {assay_name}",),
            }
        return assay.evaluate(payload).as_dict()

    def _assay_for(self, assay_name: str) -> AssayAdapter | None:
        assay = self.assays.get(assay_name)
        if assay is not None:
            return assay
        if assay_name in {"locomotion", "motor", "motor_flat_ground"}:
            return self.assays.get("locomotion")
        if assay_name in {"neural", "sensory", "sensory_mn9"}:
            return self.assays.get("neural") or self.assays.get("sensory_mn9")
        return None

    def _adapter(self, name: str) -> BackendAdapter:
        try:
            return self.adapters[name]
        except KeyError as error:
            raise ValueError(f"backend is not registered: {name}") from error

    def _load_run_manifests(self, study_id: str) -> list[dict[str, Any]]:
        manifests: list[dict[str, Any]] = []
        for job in self.list_jobs(study_id=study_id):
            if not job.manifest_path:
                continue
            path = Path(job.manifest_path)
            if not path.is_file():
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(payload, Mapping):
                item = dict(payload)
                item["manifest_path"] = path.as_posix()
                manifests.append(item)
        return manifests

    def _load_ranking_report(self, study_id: str) -> dict[str, Any]:
        path = self.artifact_root / _safe_component(study_id) / "ranking_report.json"
        if not path.is_file():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return dict(payload) if isinstance(payload, Mapping) else {}

    def _load_confirmation_plan(self, study_id: str) -> dict[str, Any]:
        path = self.artifact_root / _safe_component(study_id) / "confirmation_plan.json"
        if not path.is_file():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return dict(payload) if isinstance(payload, Mapping) else {}

    def _load_confirmation_submission(self, study_id: str) -> dict[str, Any]:
        path = self.artifact_root / _safe_component(study_id) / "confirmation_submission.json"
        if not path.is_file():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return dict(payload) if isinstance(payload, Mapping) else {}

    def _load_confirmation_run(self, study_id: str) -> dict[str, Any]:
        path = self.artifact_root / _safe_component(study_id) / "confirmation_run.json"
        if not path.is_file():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return dict(payload) if isinstance(payload, Mapping) else {}

    def _register_process(self, job_id: str, process: subprocess.Popen[str] | None) -> None:
        with self._active_lock:
            if process is None:
                self._active_processes.pop(job_id, None)
            else:
                self._active_processes[job_id] = process

    @contextmanager
    def _worker_file_lock(self):
        """Enforce one simulation worker across CLI/API processes."""

        lock_path = self.artifact_root / ".worker.lock"
        token = json.dumps({"pid": os.getpid(), "created_at": utc_timestamp()}).encode("utf-8")
        file_descriptor: int | None = None
        for _attempt in range(2):
            try:
                file_descriptor = os.open(
                    lock_path,
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                )
                os.write(file_descriptor, token)
                os.close(file_descriptor)
                file_descriptor = None
                break
            except FileExistsError:
                if not _stale_worker_lock(lock_path):
                    raise RuntimeError(
                        "another workbench worker is active; run or resume this job after it exits"
                    )
                try:
                    lock_path.unlink()
                except FileNotFoundError:
                    continue
        else:
            raise RuntimeError("could not acquire workbench worker lock")

        try:
            yield
        finally:
            if file_descriptor is not None:
                os.close(file_descriptor)
            try:
                current = lock_path.read_bytes()
            except OSError:
                current = b""
            if current == token:
                try:
                    lock_path.unlink()
                except FileNotFoundError:
                    pass

    def _write_run_manifest(
        self,
        job: JobRecord,
        study: StudySpec,
        adapter: BackendAdapter,
        run_dir: Path,
        result: BackendRunResult,
        status: JobStatus,
        *,
        pre_run_provenance: Mapping[str, Any] | None = None,
    ) -> Path:
        backend_root = Path(result.repo_root) if result.repo_root else None
        post_run_state = _git_state(backend_root) if backend_root is not None else None
        provenance = {
            "study_configuration_hash": study.configuration_hash,
            "backend_capabilities": adapter.describe().as_dict(),
            "code_revision": _git_revision(backend_root) if backend_root is not None else None,
            "code_state": post_run_state,
            "job_configuration": jsonable(job.config),
            "input_hashes": _hash_config_inputs(job.config),
            "environment": _environment_snapshot(),
        }
        if pre_run_provenance:
            provenance["pre_run"] = jsonable(pre_run_provenance)
        manifest = RunManifest(
            run_id=str(job.run_id),
            job_id=job.job_id,
            study_id=job.study_id,
            backend=job.backend,
            status=status,
            attempt=job.attempt,
            configuration_hash=stable_hash({"study": study.configuration_hash, "job": job.config}),
            command=result.command,
            interpreter=result.interpreter,
            repo_root=result.repo_root,
            started_at=str(job.started_at),
            finished_at=str(job.finished_at),
            exit_code=result.exit_code,
            artifact_hashes=_inventory(run_dir),
            provenance=provenance,
            error=result.error,
        )
        target = run_dir / "run_manifest.json"
        _write_json(target, manifest.as_dict())
        return target


def _status_from_result(result: BackendRunResult) -> JobStatus:
    if result.cancelled:
        return JobStatus.CANCELLED
    if result.error is None and result.exit_code == 0:
        return JobStatus.COMPLETED
    return JobStatus.FAILED


def _event_for_status(status: JobStatus) -> str:
    return {
        JobStatus.COMPLETED: "completed",
        JobStatus.FAILED: "failed",
        JobStatus.CANCELLED: "cancelled",
    }.get(status, status.value.lower())


def _safe_component(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return cleaned or "unnamed"


def _confirmation_job_id(kind: str, seed: str) -> str:
    return f"confirmation-{_safe_component(kind)}-seed-{_safe_component(seed)}"


def _inventory(root: Path) -> dict[str, str]:
    records: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_file() and relative != "run_manifest.json":
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            records[relative] = digest
    return records


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(jsonable(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_result_metrics(root: Path, *, preferred_path: str | Path | None = None) -> dict[str, Any]:
    payload = _read_result_payload(root, preferred_path=preferred_path)
    if not payload:
        return {}
    result: dict[str, Any] = {}
    for key in (
        "overall_pass",
        "status",
        "checks",
        "derived_locomotion_metrics",
        "metrics",
        "readouts",
        "data_audit",
        "comparison",
        "scientific_scope",
    ):
        if key in payload:
            result[key] = payload[key]
    return result


def _read_result_payload(
    root: Path,
    *,
    preferred_path: str | Path | None = None,
) -> Mapping[str, Any]:
    if not root.is_dir():
        return {}
    if preferred_path is not None:
        candidate = Path(preferred_path)
        if not candidate.is_absolute():
            candidate = root / candidate
        if not candidate.is_file():
            return {}
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, Mapping) else {}
    candidates = [path for path in sorted(root.rglob("*.json")) if path.name not in {"run_manifest.json"}]
    for path in candidates:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, Mapping):
            continue
        return payload
    return {}


def _extract_metric_value(
    payload: Mapping[str, Any],
    metric_name: str,
) -> tuple[float | None, str | None]:
    """Find one scalar metric without silently substituting another metric."""

    containers: list[tuple[str | None, Mapping[str, Any]]] = [(None, payload)]
    for key in ("derived_locomotion_metrics", "metrics", "readouts"):
        value = payload.get(key)
        if isinstance(value, Mapping):
            containers.append((key, value))
    found = False
    parts = str(metric_name).split(".")
    for container_name, container in containers:
        # Study specs conventionally use fully qualified paths such as
        # ``metrics.readout_rates_hz.<id>``.  Once the metrics mapping is the
        # selected root, the leading container component must be removed; a
        # failure here silently turns every valid neural readout into an
        # unpaired observation.
        path_parts = parts[1:] if container_name is not None and parts[:1] == [container_name] else parts
        value: Any = container
        for part in path_parts:
            if not isinstance(value, Mapping) or part not in value:
                value = None
                break
            value = value[part]
        if value is None:
            continue
        found = True
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None, "primary metric is not a scalar number"
        if not math.isfinite(float(value)):
            return None, "primary metric is non-finite"
        return float(value), None
    return None, "primary metric readout is missing" if not found else "primary metric is null"


def _extract_job_seed(
    payload: Mapping[str, Any],
    config: Mapping[str, Any],
) -> tuple[int | str | None, str | None]:
    """Resolve an explicit seed and reject disagreement instead of guessing."""

    config_values: list[Any] = []
    for key in ("seed", "random_seed"):
        if key in config:
            config_values.append(config[key])
    payload_values: list[Any] = []
    for key in ("seed", "random_seed"):
        if key in payload:
            payload_values.append(payload[key])
    configuration = payload.get("configuration")
    if isinstance(configuration, Mapping):
        for key in ("seed", "random_seed"):
            if key in configuration:
                payload_values.append(configuration[key])

    config_seed, config_error = _normalize_seed_values(config_values, "job config")
    if config_error is not None:
        return None, config_error
    payload_seed, payload_error = _normalize_seed_values(payload_values, "backend result")
    if payload_error is not None:
        return None, payload_error
    if config_seed is None and payload_seed is None:
        return None, "explicit seed is missing from job config and backend result"
    if config_seed is not None and payload_seed is not None and str(config_seed) != str(payload_seed):
        return None, "job config seed disagrees with backend result seed"
    return (config_seed if config_seed is not None else payload_seed), None


def _normalize_seed_values(values: list[Any], source: str) -> tuple[int | str | None, str | None]:
    if not values:
        return None, None
    normalized: list[int | str] = []
    for value in values:
        if isinstance(value, bool) or value is None or (isinstance(value, str) and not value.strip()):
            return None, f"{source} contains an invalid explicit seed"
        if isinstance(value, int):
            normalized.append(value)
        elif isinstance(value, str):
            normalized.append(value.strip())
        else:
            return None, f"{source} seed must be an integer or non-empty string"
    if any(str(value) != str(normalized[0]) for value in normalized[1:]):
        return None, f"{source} contains conflicting seed values"
    return normalized[0], None


def _job_source_summary(job: JobRecord) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "job_id": job.job_id,
        "run_id": job.run_id,
        "status": job.status.value,
        "candidate_id": job.config.get("candidate_id"),
        "artifact_dir": job.artifact_dir,
        "manifest_path": job.manifest_path,
    }
    if job.manifest_path:
        path = Path(job.manifest_path)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = None
        if isinstance(payload, Mapping):
            for key in ("run_id", "configuration_hash", "artifact_hashes", "provenance", "status"):
                if key in payload:
                    summary[key] = payload[key]
    return summary


def _pairing_phase(config: Mapping[str, Any]) -> str:
    """Normalize control/condition labels into one comparison phase."""

    phase = str(config.get("phase", "screening")).strip().lower() or "screening"
    if phase.endswith("_control"):
        phase = phase[: -len("_control")]
    return phase


def _job_pairing_key(config: Mapping[str, Any], backend: str) -> str:
    """Return the auditable scope in which a control may be paired.

    Candidate-specific fields are excluded deliberately: the control and the
    candidate need different interventions.  Phase, sensitivity overrides,
    confirmation plan, baseline inputs, and backend identity remain in scope.
    """

    candidate_specific = {
        "candidate_id",
        "control_candidate_id",
        "candidate_configuration_hash",
        "intervention",
        "intervention_type",
        "condition_label",
        "input_ids",
        "stimulus_rate_hz",
        "stimulus_schedule",
        "stimulus_schedule_source",
        "silence_ids",
        "outgoing_synapse_block_ids",
        "source_rank",
        "fresh_seed",
        "phase",
    }
    shared = {
        str(key): value
        for key, value in config.items()
        if key not in candidate_specific and not str(key).startswith("_")
    }
    return stable_hash(
        {
            "backend": str(backend),
            "phase": _pairing_phase(config),
            "shared_configuration": shared,
        }
    )


def _unpaired_job(job: JobRecord, reason: str) -> dict[str, Any]:
    return {
        "job_id": job.job_id,
        "run_id": job.run_id,
        "candidate_id": job.config.get("candidate_id"),
        "status": job.status.value,
        "reason": reason,
        "phase": _pairing_phase(job.config),
        "pairing_key": _job_pairing_key(job.config, job.backend),
        "manifest_path": job.manifest_path,
    }


def _git_revision(repo_root: Path) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    revision = completed.stdout.strip()
    return revision or None


def _git_state(repo_root: Path) -> dict[str, Any] | None:
    """Record checkout state and hashes of changed file contents."""

    try:
        revision = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        status = subprocess.run(
            ["git", "-C", str(repo_root), "status", "--porcelain=v1", "--untracked-files=all"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if status.returncode != 0:
        return None
    status_text = status.stdout
    changed = subprocess.run(
        ["git", "-C", str(repo_root), "diff", "--name-only", "HEAD", "--"],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    untracked = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "--others", "--exclude-standard"],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    if changed.returncode != 0:
        changed = subprocess.run(
            ["git", "-C", str(repo_root), "diff", "--name-only", "--"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    if changed.returncode != 0 or untracked.returncode != 0:
        return None
    tracked_paths = {
        line.strip()
        for line in changed.stdout.splitlines()
        if line.strip()
    }
    untracked_paths = {line.strip() for line in untracked.stdout.splitlines() if line.strip()}
    changed_paths = tracked_paths | untracked_paths
    file_hashes: dict[str, str] = {}
    excluded_untracked: list[str] = []
    for relative in sorted(changed_paths):
        normalized = relative.replace("\\", "/")
        if relative in untracked_paths and not _is_source_provenance_path(normalized):
            excluded_untracked.append(normalized)
            continue
        candidate = repo_root / relative
        if candidate.is_file():
            try:
                file_hashes[normalized] = hashlib.sha256(candidate.read_bytes()).hexdigest()
            except OSError:
                file_hashes[normalized] = "UNREADABLE"
        else:
            file_hashes[normalized] = "DELETED"
    return {
        "revision": revision.stdout.strip() or None,
        "dirty": bool(status_text.strip()),
        "status_sha256": hashlib.sha256(status_text.encode("utf-8")).hexdigest(),
        "changed_file_sha256": file_hashes,
        "content_sha256": stable_hash(file_hashes),
        "untracked_content_excluded": excluded_untracked,
    }


def _is_source_provenance_path(relative: str) -> bool:
    """Avoid hashing generated result trees while retaining source artifacts."""

    parts = Path(relative).parts
    if not parts:
        return False
    source_roots = {
        "src",
        "scripts",
        "configs",
        "tests",
        "requirements",
        "docs",
        "annotations",
    }
    return parts[0].lower() in source_roots


def _pre_run_provenance(adapter: BackendAdapter) -> dict[str, Any]:
    """Capture coordinator/backend state before a subprocess starts."""

    coordinator_root = Path(__file__).resolve().parents[3]
    backend_root_value = getattr(adapter, "repo_root", None)
    backend_root = Path(backend_root_value) if backend_root_value else None
    interpreter = getattr(adapter, "interpreter", None)
    return {
        "captured_at": utc_timestamp(),
        "coordinator_code_state": _git_state(coordinator_root),
        "backend_code_state": _git_state(backend_root) if backend_root is not None else None,
        "backend_environment": _interpreter_snapshot(interpreter),
    }


def _interpreter_snapshot(interpreter: object) -> dict[str, Any] | None:
    if not interpreter:
        return None
    cache_key = str(interpreter)
    cached = _INTERPRETER_SNAPSHOT_CACHE.get(cache_key)
    if cached is not None:
        return dict(cached)
    script = (
        "import importlib.metadata as m, json, platform, sys; "
        "names=('brian2','numpy','pandas','pyarrow','flygym','mujoco','fastapi'); "
        "print(json.dumps({'python_executable':sys.executable,'python_version':platform.python_version(),"
        "'platform':platform.platform(),'packages':{n:(m.version(n) if n in {x.metadata['Name'].lower() for x in m.distributions()} else None) for n in names}}))"
    )
    try:
        result = subprocess.run(
            [str(interpreter), "-c", script],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        payload = {"python_executable": str(interpreter), "error": f"{type(error).__name__}: {error}"}
        _INTERPRETER_SNAPSHOT_CACHE[cache_key] = payload
        return dict(payload)
    if result.returncode != 0:
        payload = {
            "python_executable": str(interpreter),
            "error": (result.stderr or f"interpreter exited with {result.returncode}").strip(),
        }
        _INTERPRETER_SNAPSHOT_CACHE[cache_key] = payload
        return dict(payload)
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        payload = {"python_executable": str(interpreter), "error": "interpreter snapshot was not JSON"}
    if not isinstance(payload, Mapping):
        payload = {"python_executable": str(interpreter)}
    normalized = dict(payload)
    _INTERPRETER_SNAPSHOT_CACHE[cache_key] = normalized
    return dict(normalized)


def _hash_config_inputs(config: Mapping[str, Any]) -> dict[str, str]:
    """Hash existing file inputs referenced by a job configuration."""

    records: dict[str, str] = {}

    def visit(value: Any, label: str) -> None:
        if isinstance(value, Mapping):
            for key, item in value.items():
                visit(item, f"{label}.{key}")
            return
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            for index, item in enumerate(value):
                visit(item, f"{label}[{index}]")
            return
        if not isinstance(value, (str, Path)):
            return
        candidate = Path(value).expanduser()
        if not candidate.is_file():
            return
        try:
            records[label] = hashlib.sha256(candidate.read_bytes()).hexdigest()
        except OSError:
            records[label] = "UNREADABLE"

    visit(config, "job")
    return dict(sorted(records.items()))


def _environment_snapshot() -> dict[str, Any]:
    """Capture a compact, local-only software environment fingerprint."""

    package_names = (
        "numpy",
        "scipy",
        "pandas",
        "pyarrow",
        "pyyaml",
        "flygym",
        "mujoco",
        "fastapi",
    )
    packages: dict[str, str] = {}
    for name in package_names:
        try:
            packages[name] = importlib_metadata.version(name)
        except importlib_metadata.PackageNotFoundError:
            continue
    return {
        "python_version": sys.version,
        "python_executable": str(Path(sys.executable).resolve()),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "packages": packages,
    }


def _stale_worker_lock(path: Path, *, malformed_age_s: float = 3600.0) -> bool:
    """Return whether a worker lock can be safely reclaimed after a crash."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        try:
            return time.time() - path.stat().st_mtime > malformed_age_s
        except OSError:
            return True
    pid = payload.get("pid") if isinstance(payload, Mapping) else None
    if isinstance(pid, int) and pid > 0:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        except PermissionError:
            return False
        except OSError:
            return True
        return False
    try:
        return time.time() - path.stat().st_mtime > malformed_age_s
    except OSError:
        return True


__all__ = ["WorkbenchService"]
