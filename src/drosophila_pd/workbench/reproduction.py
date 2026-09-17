"""Reproduction checks for Workbench campaigns.

The verifier is deliberately stricter than a visual comparison of rankings. It
checks that the two runs used the same declared study/seed subset, used the
same configuration and provenance, and produced equivalent per-job metrics.  A
successful reproduction is never inferred from a missing failure case or from
matching aggregate numbers alone.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from typing import Any


DEFAULT_ABSOLUTE_TOLERANCE = 1e-9
DEFAULT_RELATIVE_TOLERANCE = 1e-9


def _load_document(path: Path) -> Mapping[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        import yaml

        value = yaml.safe_load(text)
    else:
        value = json.loads(text)
    if not isinstance(value, Mapping):
        raise ValueError(f"campaign manifest must be an object: {path}")
    return value


def _as_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value


def _jobs(payload: Mapping[str, Any], label: str) -> list[Mapping[str, Any]]:
    raw = payload.get("jobs", [])
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        raise ValueError(f"{label}.jobs must be a list")
    result = []
    for index, value in enumerate(raw):
        result.append(_as_mapping(value, f"{label}.jobs[{index}]"))
    return result


def _job_key(job: Mapping[str, Any], label: str) -> tuple[str, str]:
    config = _as_mapping(job.get("config", {}), f"{label}.config")
    candidate = str(config.get("candidate_id", ""))
    seed = str(config.get("seed", ""))
    if not candidate or not seed:
        raise ValueError(f"{label} does not declare candidate_id and seed")
    return candidate, seed


def _canonical(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _canonical(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    return value


def _config_for_comparison(job: Mapping[str, Any]) -> Mapping[str, Any]:
    config = _as_mapping(job.get("config", {}), "job.config")
    # Config paths are intentionally relative in the Workbench study.  Keep
    # every declared field: silently dropping a parameter would make this a
    # ranking check rather than a reproduction check.
    return config


def _resolve_artifact_dir(job: Mapping[str, Any], manifest_path: Path) -> Path:
    raw = job.get("artifact_dir")
    if not raw:
        raise ValueError(f"job {job.get('job_id', '<unknown>')} has no artifact_dir")
    path = Path(str(raw))
    if not path.is_absolute():
        path = manifest_path.parent / path
    return path


def _metrics_payload(job: Mapping[str, Any], manifest_path: Path) -> Mapping[str, Any]:
    path = _resolve_artifact_dir(job, manifest_path) / "lif_condition" / "metrics.json"
    if not path.exists():
        raise FileNotFoundError(f"missing metrics artifact: {path}")
    payload = _load_document(path)
    metrics = payload.get("metrics")
    if not isinstance(metrics, Mapping):
        raise ValueError(f"metrics artifact has no metrics object: {path}")
    return metrics


def _compare_values(
    reference: Any,
    replica: Any,
    path: str,
    differences: list[str],
    *,
    absolute_tolerance: float,
    relative_tolerance: float,
) -> None:
    if isinstance(reference, Mapping) or isinstance(replica, Mapping):
        if not isinstance(reference, Mapping) or not isinstance(replica, Mapping):
            differences.append(f"{path}: mapping/scalar mismatch")
            return
        reference_keys = {str(key) for key in reference}
        replica_keys = {str(key) for key in replica}
        for missing in sorted(reference_keys - replica_keys):
            differences.append(f"{path}.{missing}: missing in replica")
        for extra in sorted(replica_keys - reference_keys):
            differences.append(f"{path}.{extra}: unexpected in replica")
        for key in sorted(reference_keys & replica_keys):
            _compare_values(
                reference[next(item for item in reference if str(item) == key)],
                replica[next(item for item in replica if str(item) == key)],
                f"{path}.{key}",
                differences,
                absolute_tolerance=absolute_tolerance,
                relative_tolerance=relative_tolerance,
            )
        return
    if isinstance(reference, Sequence) and not isinstance(reference, (str, bytes)):
        if not isinstance(replica, Sequence) or isinstance(replica, (str, bytes)):
            differences.append(f"{path}: sequence/scalar mismatch")
            return
        if len(reference) != len(replica):
            differences.append(f"{path}: length {len(reference)} != {len(replica)}")
            return
        for index, (ref_item, replica_item) in enumerate(zip(reference, replica)):
            _compare_values(
                ref_item,
                replica_item,
                f"{path}[{index}]",
                differences,
                absolute_tolerance=absolute_tolerance,
                relative_tolerance=relative_tolerance,
            )
        return
    if isinstance(reference, (int, float)) and not isinstance(reference, bool):
        if not isinstance(replica, (int, float)) or isinstance(replica, bool):
            differences.append(f"{path}: numeric/scalar mismatch")
            return
        if not (math.isfinite(float(reference)) and math.isfinite(float(replica))):
            differences.append(f"{path}: non-finite values are not reproducible")
            return
        if not math.isclose(
            float(reference),
            float(replica),
            abs_tol=absolute_tolerance,
            rel_tol=relative_tolerance,
        ):
            differences.append(f"{path}: {reference!r} != {replica!r}")
        return
    if reference != replica:
        differences.append(f"{path}: {reference!r} != {replica!r}")


def _provenance_signature(job: Mapping[str, Any], manifest_path: Path) -> dict[str, Any]:
    run_manifest_path = job.get("manifest_path")
    if run_manifest_path:
        path = Path(str(run_manifest_path))
        if not path.is_absolute():
            path = manifest_path.parent / path
    else:
        path = _resolve_artifact_dir(job, manifest_path) / "run_manifest.json"
    if not path.exists():
        raise FileNotFoundError(f"missing run manifest: {path}")
    run = _load_document(path)
    provenance = run.get("provenance", {})
    if not isinstance(provenance, Mapping):
        raise ValueError(f"run manifest has no provenance object: {path}")
    capabilities = provenance.get("backend_capabilities", {})
    if not isinstance(capabilities, Mapping):
        capabilities = {}
    input_hashes = provenance.get("input_hashes", {})
    if not isinstance(input_hashes, Mapping):
        input_hashes = {}
    strict_manifest = run.get("manifest_version") is not None
    if strict_manifest:
        required = {
            "backend": run.get("backend"),
            "configuration_hash": run.get("configuration_hash"),
            "code_revision": provenance.get("code_revision"),
            "study_configuration_hash": provenance.get("study_configuration_hash"),
            "backend_capability_name": capabilities.get("name"),
            "input_hashes": input_hashes,
            "environment": provenance.get("environment"),
            "code_state": provenance.get("code_state"),
        }
        missing = [name for name, value in required.items() if value in (None, "", {})]
        if missing:
            raise ValueError(f"run manifest provenance is incomplete: {', '.join(missing)}")
        if not isinstance(provenance.get("environment"), Mapping):
            raise ValueError("run manifest environment provenance must be an object")
        artifact_hashes = run.get("artifact_hashes")
        if not isinstance(artifact_hashes, Mapping) or not artifact_hashes:
            raise ValueError("run manifest artifact_hashes are missing")
        artifact_root = path.parent
        actual_hashes: dict[str, str] = {}
        for artifact in sorted(artifact_root.rglob("*")):
            if artifact.is_file() and artifact.name != "run_manifest.json":
                import hashlib

                actual_hashes[artifact.relative_to(artifact_root).as_posix()] = hashlib.sha256(
                    artifact.read_bytes()
                ).hexdigest()
        declared_hashes = {str(key): str(value) for key, value in artifact_hashes.items()}
        if actual_hashes != declared_hashes:
            raise ValueError("run manifest artifact hashes do not match files on disk")
    return {
        "backend": str(run.get("backend", "")),
        "configuration_hash": str(run.get("configuration_hash", "")),
        "code_revision": str(provenance.get("code_revision", "")),
        "study_configuration_hash": str(provenance.get("study_configuration_hash", "")),
        "backend_capability_name": str(capabilities.get("name", "")),
        "input_hashes": {
            str(key): str(value)
            for key, value in sorted(input_hashes.items(), key=lambda item: str(item[0]))
        },
        "artifact_hashes": {
            str(key): str(value)
            for key, value in sorted(
                (run.get("artifact_hashes", {}) if isinstance(run.get("artifact_hashes", {}), Mapping) else {}).items(),
                key=lambda item: str(item[0]),
            )
        },
    }


def _campaign_signature(payload: Mapping[str, Any], label: str) -> dict[str, Any]:
    return {
        "phase": str(payload.get("phase", "")),
        "status": str(payload.get("status", "")).upper(),
        "study_id": str(payload.get("study_id", "")),
        "study_configuration_hash": str(payload.get("study_configuration_hash", "")),
        "study_config_sha256": str(payload.get("study_config_sha256", "")),
        "scientific_scope": str(payload.get("scientific_scope", "")),
        "jobs": _jobs(payload, label),
    }


def _compare_campaign(
    reference_path: Path,
    replica_path: Path,
    *,
    require_completed: bool,
    absolute_tolerance: float,
    relative_tolerance: float,
) -> dict[str, Any]:
    reference_payload = _load_document(reference_path)
    replica_payload = _load_document(replica_path)
    reference = _campaign_signature(reference_payload, "reference")
    replica = _campaign_signature(replica_payload, "replica")
    differences: list[str] = []

    for field in (
        "phase",
        "status",
        "study_configuration_hash",
        "study_config_sha256",
        "scientific_scope",
    ):
        if reference[field] != replica[field]:
            differences.append(f"campaign.{field}: {reference[field]!r} != {replica[field]!r}")

    reference_keys = [_job_key(job, "reference") for job in reference["jobs"]]
    replica_keys = [_job_key(job, "replica") for job in replica["jobs"]]
    reference_jobs = {_job_key(job, "reference"): job for job in reference["jobs"]}
    replica_jobs = {_job_key(job, "replica"): job for job in replica["jobs"]}
    for label, keys in (("reference", reference_keys), ("replica", replica_keys)):
        duplicates = sorted({key for key in keys if keys.count(key) > 1})
        for key in duplicates:
            differences.append(f"{label}.jobs.{key}: duplicate candidate/seed key")
    if require_completed and not reference_jobs:
        differences.append("reference campaign contains no jobs")
    if require_completed and not replica_jobs:
        differences.append("replica campaign contains no jobs")
    for key in sorted(set(reference_jobs) - set(replica_jobs)):
        differences.append(f"jobs.{key}: missing in replica")
    for key in sorted(set(replica_jobs) - set(reference_jobs)):
        differences.append(f"jobs.{key}: unexpected in replica")

    provenance_match = True
    outputs_match = True
    compared_jobs = 0
    non_completed_reference = []
    non_completed_replica = []
    reference_signatures: dict[tuple[str, str], dict[str, Any]] = {}
    replica_signatures: dict[tuple[str, str], dict[str, Any]] = {}
    for key in sorted(set(reference_jobs) & set(replica_jobs)):
        ref_job = reference_jobs[key]
        replica_job = replica_jobs[key]
        ref_status = str(ref_job.get("status", "")).upper()
        replica_status = str(replica_job.get("status", "")).upper()
        if require_completed:
            if ref_status != "COMPLETED":
                non_completed_reference.append({"key": key, "status": ref_status})
            if replica_status != "COMPLETED":
                non_completed_replica.append({"key": key, "status": replica_status})
        if ref_status != replica_status:
            differences.append(f"jobs.{key}.status: {ref_status!r} != {replica_status!r}")
        if _canonical(_config_for_comparison(ref_job)) != _canonical(_config_for_comparison(replica_job)):
            differences.append(f"jobs.{key}.config: declared configurations differ")
        if ref_status == "COMPLETED" and replica_status == "COMPLETED":
            try:
                ref_provenance = _provenance_signature(ref_job, reference_path)
                replica_provenance = _provenance_signature(replica_job, replica_path)
                reference_signatures[key] = ref_provenance
                replica_signatures[key] = replica_provenance
                if ref_provenance != replica_provenance:
                    provenance_match = False
                    differences.append(f"jobs.{key}.provenance: signatures differ")
            except (FileNotFoundError, ValueError, OSError) as error:
                provenance_match = False
                differences.append(f"jobs.{key}.provenance: {error}")
        elif not require_completed:
            ref_error = bool(str(ref_job.get("error", "")).strip())
            replica_error = bool(str(replica_job.get("error", "")).strip())
            if ref_error != replica_error:
                differences.append(f"jobs.{key}.error_presence: {ref_error} != {replica_error}")
        if ref_status == "COMPLETED" and replica_status == "COMPLETED":
            try:
                ref_metrics = _metrics_payload(ref_job, reference_path)
                replica_metrics = _metrics_payload(replica_job, replica_path)
                metric_differences: list[str] = []
                _compare_values(
                    ref_metrics,
                    replica_metrics,
                    f"jobs.{key}.metrics",
                    metric_differences,
                    absolute_tolerance=absolute_tolerance,
                    relative_tolerance=relative_tolerance,
                )
                if metric_differences:
                    outputs_match = False
                    differences.extend(metric_differences[:20])
                    if len(metric_differences) > 20:
                        differences.append(
                            f"jobs.{key}.metrics: {len(metric_differences) - 20} more differences"
                        )
            except (FileNotFoundError, ValueError, OSError) as error:
                outputs_match = False
                differences.append(f"jobs.{key}.metrics: {error}")
        compared_jobs += 1

    if require_completed and (non_completed_reference or non_completed_replica):
        outputs_match = False
        differences.append(f"non_completed_reference={non_completed_reference}")
        differences.append(f"non_completed_replica={non_completed_replica}")

    has_failure_state = (
        bool(non_completed_reference or non_completed_replica)
        or reference["status"] not in {"PASS", "COMPLETED", "COMPLETE"}
        or replica["status"] not in {"PASS", "COMPLETED", "COMPLETE"}
    )

    return {
        "manifests_match": not differences,
        "provenance_match": provenance_match and not any("provenance" in item for item in differences),
        "outputs_within_declared_tolerance": outputs_match,
        "failure_states_checked": not require_completed,
        "has_failure_state": has_failure_state,
        "compared_job_count": compared_jobs,
        "reference_job_count": len(reference["jobs"]),
        "replica_job_count": len(replica["jobs"]),
        "study_ids": sorted({reference["study_id"], replica["study_id"]}),
        "seeds": sorted(
            {key[1] for key in set(reference_jobs) & set(replica_jobs)},
            key=lambda value: (not value.isdigit(), int(value) if value.isdigit() else value),
        ),
        "source_revisions": sorted(
            {
                signature["code_revision"]
                for signature in (*reference_signatures.values(), *replica_signatures.values())
                if signature["code_revision"]
            }
        ),
        "reference_input_hashes": sorted(
            {
                digest
                for signature in reference_signatures.values()
                for digest in signature["input_hashes"].values()
            }
        ),
        "reference_artifact_hashes": sorted(
            digest
            for signature in reference_signatures.values()
            for digest in signature.get("artifact_hashes", {}).values()
        ),
        "replica_artifact_hashes": sorted(
            digest
            for signature in replica_signatures.values()
            for digest in signature.get("artifact_hashes", {}).values()
        ),
        "replica_input_hashes": sorted(
            {
                digest
                for signature in replica_signatures.values()
                for digest in signature["input_hashes"].values()
            }
        ),
        "discrepancies": differences,
    }


def verify_reproduction(
    reference_manifest: Path,
    replica_manifest: Path,
    *,
    operator_name: str,
    operator_role: str = "same_operator",
    clean_install: bool = False,
    python_version: str = "3.12",
    lockfile_or_export: str | None = None,
    platform_interpreter: str | None = None,
    neural_interpreter: str | None = None,
    source_commit: str | None = None,
    benchmark_protocol_hash: str | None = None,
    platform_repo: str | None = None,
    neural_repo: str | None = None,
    failure_reference_manifest: Path | None = None,
    failure_replica_manifest: Path | None = None,
    absolute_tolerance: float = DEFAULT_ABSOLUTE_TOLERANCE,
    relative_tolerance: float = DEFAULT_RELATIVE_TOLERANCE,
) -> dict[str, Any]:
    if not operator_name.strip():
        raise ValueError("operator_name must not be empty")
    operator_role = str(operator_role).strip().lower()
    allowed_roles = {"same_operator", "second_operator", "automated"}
    if operator_role not in allowed_roles:
        raise ValueError("operator_role must be same_operator, second_operator, or automated")
    if absolute_tolerance < 0 or relative_tolerance < 0:
        raise ValueError("tolerances must be non-negative")
    success = _compare_campaign(
        reference_manifest,
        replica_manifest,
        require_completed=True,
        absolute_tolerance=absolute_tolerance,
        relative_tolerance=relative_tolerance,
    )
    failure_states_checked = False
    failure: dict[str, Any] | None = None
    if (failure_reference_manifest is None) != (failure_replica_manifest is None):
        success["discrepancies"].append(
            "failure reference and replica manifests must be supplied together"
        )
    elif failure_reference_manifest is not None and failure_replica_manifest is not None:
        failure = _compare_campaign(
            failure_reference_manifest,
            failure_replica_manifest,
            require_completed=False,
            absolute_tolerance=absolute_tolerance,
            relative_tolerance=relative_tolerance,
        )
        failure_states_checked = bool(failure["manifests_match"] and failure["has_failure_state"])
        if not failure_states_checked:
            success["discrepancies"].extend(
                f"failure_case: {item}" for item in failure["discrepancies"]
            )
            if failure["manifests_match"] and not failure["has_failure_state"]:
                success["discrepancies"].append(
                    "failure_case: supplied manifests contain no explicit failed/cancelled/rejected job"
                )
    success["failure_states_checked"] = failure_states_checked

    source_revisions = success.get("source_revisions", [])
    public_artifact_hashes = sorted(
        {
            digest
            for signature in (
                success.get("reference_input_hashes", []),
                success.get("replica_input_hashes", []),
            )
            for digest in signature
        }
    )
    inferred_source_commit = source_commit or (";".join(source_revisions) if source_revisions else None)
    status = (
        "PASS"
        if clean_install
        and success["manifests_match"]
        and success["provenance_match"]
        and success["outputs_within_declared_tolerance"]
        and failure_states_checked
        else "BLOCKED"
    )
    reference_payload = _load_document(reference_manifest)
    subset_seeds = success.get("seeds", [])
    return {
        "reproduction_id": "workbench-reproduction-v2",
        "status": status,
        "operator_role": operator_role,
        "independent_operator_claim_eligible": operator_role == "second_operator" and status == "PASS",
        "operator_name": operator_name,
        "run_at": datetime.now(timezone.utc).isoformat(),
        "source_commit": inferred_source_commit,
        "platform_repo": platform_repo or str(reference_payload.get("platform_repo", "")),
        "neural_repo": neural_repo or str(reference_payload.get("neural_repo", "")),
        "environment": {
            "clean_install": bool(clean_install),
            "python_version": python_version,
            "lockfile_or_export": lockfile_or_export,
            "platform_interpreter": platform_interpreter,
            "neural_interpreter": neural_interpreter,
        },
        "inputs": {
            "benchmark_protocol_hash": benchmark_protocol_hash,
            "study_config_hash": reference_payload.get("study_configuration_hash"),
            "public_artifact_hashes": public_artifact_hashes,
        },
        "subset": {
            "study_ids": success.get("study_ids", []),
            "seeds": subset_seeds,
            "includes_success_case": success["reference_job_count"] > 0,
            "includes_failure_case": failure_states_checked,
        },
        "comparison": {
            "manifests_match": bool(success["manifests_match"]),
            "provenance_match": bool(success["provenance_match"]),
            "outputs_within_declared_tolerance": bool(success["outputs_within_declared_tolerance"]),
            "failure_states_checked": failure_states_checked,
            "declared_tolerance": {
                "absolute": absolute_tolerance,
                "relative": relative_tolerance,
            },
            "compared_job_count": success["compared_job_count"],
            "discrepancies": success["discrepancies"],
        },
        "review": {
            "approved_by_primary_operator": False,
            "approved_by_second_operator": False,
            "notes": (
                "Automated comparison only. A same-operator or AI run is computational "
                "reproduction, not independent-operator reproduction; scientific approval "
                "remains a human review step."
            ),
        },
        "details": {
            "success_case": success,
            "failure_case": failure,
        },
    }


__all__ = ["verify_reproduction"]
