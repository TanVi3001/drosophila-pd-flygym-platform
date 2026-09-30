#!/usr/bin/env python
"""Build a label-free V1 demo package from exact allowlisted DEV paths only."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
ALLOWLIST_PATH = ROOT / "configs/demo/v1_development_case_allowlist_v1.json"
DEFAULT_SOURCE_ROOT = Path(
    r"E:\research-\external\Drosophila_brain_model\results\workbench_shiu_v2_rewired_lif_run02"
)
DEFAULT_PACKAGE_ROOT = ROOT.parent / "v1-demo-dev-package-v1"
DEVELOPMENT_SPLIT_SHA256 = "3f9b39c1b6e91d766e85eaa0347f79243553a9b73a51442e944b7d8135713467"
SOURCE_STATES = ("control", "condition")
SOURCE_FILENAMES = ("status.json", "metrics.json", "run_manifest.json")
BUILDER_VERSION = "v1-demo-dev-package-builder-1"
CASE_ID_PATTERN = re.compile(r"^shiu_table3_row_\d{3}$")
FORBIDDEN_FIELD_PARTS = (
    "label",
    "positive",
    "negative",
    "outcome",
    "phenotype",
    "observed_response_fraction",
    "held_out",
    "external_result",
    "graphsage_prediction",
)


class PackageBuildError(RuntimeError):
    """Raised when package integrity or isolation checks fail."""


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_split_sha256(case_ids: Sequence[str]) -> str:
    canonical = json.dumps(sorted(case_ids), ensure_ascii=False, separators=(",", ":"))
    return sha256_bytes(canonical.encode("utf-8"))


def load_allowlist(path: Path = ALLOWLIST_PATH) -> tuple[dict[str, Any], tuple[str, ...]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise PackageBuildError("development allowlist must be a JSON object")
    raw_ids = payload.get("case_ids")
    if not isinstance(raw_ids, list):
        raise PackageBuildError("development allowlist case_ids must be a list")
    case_ids = tuple(str(value) for value in raw_ids)
    if len(case_ids) != 74 or len(set(case_ids)) != 74:
        raise PackageBuildError("development allowlist must contain exactly 74 unique IDs")
    if any(CASE_ID_PATTERN.fullmatch(case_id) is None for case_id in case_ids):
        raise PackageBuildError("development allowlist contains a malformed case ID")
    if payload.get("partition") != "DEVELOPMENT" or payload.get("case_count") != 74:
        raise PackageBuildError("development allowlist partition/count contract failed")
    if payload.get("development_split_sha256") != DEVELOPMENT_SPLIT_SHA256:
        raise PackageBuildError("development split identity does not match the locked hash")
    if canonical_split_sha256(case_ids) != DEVELOPMENT_SPLIT_SHA256:
        raise PackageBuildError("development IDs do not match the locked split hash")
    return dict(payload), tuple(sorted(case_ids))


def _assert_allowed_case(case_id: str, allowed_ids: Sequence[str]) -> str:
    text = str(case_id)
    if text not in set(allowed_ids):
        raise PackageBuildError("case ID is not in the locked DEVELOPMENT allowlist")
    if CASE_ID_PATTERN.fullmatch(text) is None:
        raise PackageBuildError("case ID is not a safe path component")
    return text


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _assert_isolated_paths(source_root: Path, package_root: Path) -> None:
    source = source_root.resolve()
    package = package_root.resolve()
    if package == source or _is_within(package, source):
        raise PackageBuildError("package root must be outside the source results root")
    if package.exists():
        raise PackageBuildError(f"refusing to overwrite existing package root: {package}")


def _read_json_exact(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise PackageBuildError(f"expected a JSON object at exact artifact path: {path.name}")
    return dict(value)


def _source_hash(path: Path) -> tuple[str, int]:
    payload = path.read_bytes()
    return sha256_bytes(payload), len(payload)


def _selected_configuration(document: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if document is None:
        return None
    config = document.get("condition")
    if not isinstance(config, Mapping):
        return None
    allowed = (
        "condition_label",
        "dataset_id",
        "duration_s",
        "id_namespace",
        "input_ids",
        "outgoing_synapse_block_ids",
        "readout_ids",
        "seed",
        "stimulus_rate_hz",
        "stimulus_schedule",
        "trial_count",
        "intervention",
    )
    return {key: config[key] for key in allowed if key in config}


def _selected_source_provenance(document: Mapping[str, Any] | None) -> dict[str, Any]:
    if document is None:
        return {}
    source = document.get("source_provenance")
    if not isinstance(source, Mapping):
        return {}
    selected: dict[str, Any] = {}
    for name in ("annotation_registry", "completeness", "connectivity", "model_py"):
        item = source.get(name)
        if isinstance(item, Mapping):
            entry = {key: item[key] for key in ("sha256", "dataset_id", "id_namespace", "rows") if key in item}
            selected[name] = entry
    for name in ("model_family", "upstream_repository"):
        if name in source:
            selected[name] = source[name]
    return selected


def _selected_metrics(document: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if document is None:
        return None
    metrics = document.get("metrics")
    if not isinstance(metrics, Mapping):
        return None
    allowed = (
        "trial_count",
        "duration_s",
        "spike_count_total",
        "neuron_count_in_output",
        "active_neurons_per_trial",
        "readout_spike_counts",
        "readout_rates_hz",
    )
    return {
        "schema_version": document.get("schema_version"),
        "status": document.get("status"),
        "metrics": {key: metrics[key] for key in allowed if key in metrics},
    }


def _selected_qc(
    status: Mapping[str, Any] | None,
    metrics_document: Mapping[str, Any] | None,
    config: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if status is None or metrics_document is None:
        return None
    audit = metrics_document.get("data_audit")
    if not isinstance(audit, Mapping):
        return None
    declared_inputs = list(config.get("input_ids", ())) if config else []
    declared_silence = list(config.get("outgoing_synapse_block_ids", ())) if config else []
    declared_readouts = list(config.get("readout_ids", ())) if config else []
    missing_inputs = list(audit.get("declared_input_ids_missing_from_output", ()))
    missing_readouts = [
        value for value in declared_readouts
        if value not in set(audit.get("declared_readout_ids_in_output", ()))
    ]
    completeness = audit.get("completeness", {})
    if not isinstance(completeness, Mapping):
        completeness = {}
    qc_pass = bool(
        status.get("status") == "PASS"
        and metrics_document.get("status") == "PASS"
        and audit.get("output_ids_are_unique_after_string_cast") is True
        and not missing_inputs
        and not missing_readouts
        and int(completeness.get("output_ids_missing_from_completeness", 0)) == 0
    )
    return {
        "schema_version": "v1-demo-source-data-qc-summary-1",
        "status": "PASS" if qc_pass else "FAIL_OR_INCOMPLETE",
        "scope": "Source LIF artifact/data-integrity checks only; not a biological validation or Workbench scientific approval.",
        "run_status": status.get("status"),
        "metrics_status": metrics_document.get("status"),
        "unique_output_ids": audit.get("output_ids_are_unique_after_string_cast"),
        "declared_input_ids": declared_inputs,
        "declared_silenced_ids": declared_silence,
        "missing_input_ids": missing_inputs,
        "declared_readout_ids": declared_readouts,
        "missing_readout_ids": missing_readouts,
        "silent_readout_ids": list(audit.get("declared_readout_ids_silent", ())),
        "output_ids_missing_from_completeness": completeness.get("output_ids_missing_from_completeness"),
    }


def _write_json(package_root: Path, relative_path: str, payload: Mapping[str, Any]) -> dict[str, str]:
    target = package_root / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    target.write_bytes(raw)
    return {"path": Path(relative_path).as_posix(), "sha256": sha256_bytes(raw), "size_bytes": len(raw)}


def _git_commit() -> str:
    result = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else "UNKNOWN"


def _contains_forbidden_fields(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, child in value.items():
            lowered = str(key).lower()
            if any(part in lowered for part in FORBIDDEN_FIELD_PARTS):
                return True
            if _contains_forbidden_fields(child):
                return True
    elif isinstance(value, list):
        return any(_contains_forbidden_fields(item) for item in value)
    return False


def _build_case(
    *,
    case_id: str,
    allowed_ids: Sequence[str],
    source_root: Path,
    package_root: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, str]]]:
    case_id = _assert_allowed_case(case_id, allowed_ids)
    source_docs: dict[str, dict[str, Any] | None] = {}
    source_hashes: list[dict[str, Any]] = []
    missing: list[str] = []
    for state in SOURCE_STATES:
        for filename in SOURCE_FILENAMES:
            relative = Path(case_id) / state / filename
            exact_path = source_root / relative
            if not exact_path.is_file():
                missing.append(relative.as_posix())
                source_hashes.append({"path": relative.as_posix(), "available": False, "sha256": None})
                source_docs[f"{state}/{filename}"] = None
                continue
            digest, size = _source_hash(exact_path)
            source_hashes.append(
                {"path": relative.as_posix(), "available": True, "sha256": digest, "size_bytes": size}
            )
            if filename.endswith(".json"):
                source_docs[f"{state}/{filename}"] = _read_json_exact(exact_path)

    control_manifest = source_docs.get("control/run_manifest.json")
    condition_manifest = source_docs.get("condition/run_manifest.json")
    control_status = source_docs.get("control/status.json")
    condition_status = source_docs.get("condition/status.json")
    control_metrics = source_docs.get("control/metrics.json")
    condition_metrics = source_docs.get("condition/metrics.json")
    config = _selected_configuration(condition_manifest)
    control_config = _selected_configuration(control_manifest)
    config_consistent = bool(
        config is not None
        and control_config is not None
        and config.get("dataset_id") == control_config.get("dataset_id")
        and config.get("readout_ids") == control_config.get("readout_ids")
    )
    input_available = config_consistent
    execution_ids = []
    if config is not None:
        execution_ids = list(config.get("input_ids", ())) + list(config.get("outgoing_synapse_block_ids", ()))

    written: list[dict[str, str]] = []
    case_folder = f"cases/{case_id}"
    readiness = {
        "case_id": case_id,
        "required_input_present": input_available,
        "execution_target_ids_present": bool(execution_ids),
        "mapping_present": False,
        "mapping_review_record_present": False,
        "study_spec_available": False,
        "simulation_artifact_available": all(
            isinstance(status, Mapping)
            and status.get("status") == "PASS"
            and isinstance(metrics, Mapping)
            and metrics.get("status") == "PASS"
            for status, metrics in ((control_status, control_metrics), (condition_status, condition_metrics))
        ),
        "qc_artifact_available": all(
            isinstance(metrics, Mapping) and isinstance(metrics.get("data_audit"), Mapping)
            for metrics in (control_metrics, condition_metrics)
        ),
        "provenance_available": isinstance(control_manifest, Mapping) and isinstance(condition_manifest, Mapping),
        "missing_expected_artifact_count": len(missing),
    }

    case_record = {
        "schema_version": "v1-demo-case-package-1",
        "case_id": case_id,
        "partition": "DEVELOPMENT",
        "development_split_sha256": DEVELOPMENT_SPLIT_SHA256,
        "availability": readiness,
        "missing_expected_artifacts": missing,
        "note": "A LIF execution configuration is not by itself a scientifically reviewed mapping or a Workbench StudySpec.",
    }
    written.append(_write_json(package_root, f"{case_folder}/case.json", case_record))

    if config is not None:
        input_record = {
            "schema_version": "v1-demo-case-input-1",
            "case_id": case_id,
            "partition": "DEVELOPMENT",
            "dataset_id": config.get("dataset_id"),
            "id_namespace": config.get("id_namespace"),
            "duration_s": config.get("duration_s"),
            "seed": config.get("seed"),
            "trial_count": config.get("trial_count"),
            "stimulus_rate_hz": config.get("stimulus_rate_hz"),
            "stimulus_schedule": config.get("stimulus_schedule", []),
            "readout_ids": config.get("readout_ids", []),
        }
        written.append(_write_json(package_root, f"{case_folder}/input/case_input.json", input_record))
        mapping_metadata = {
            "schema_version": "v1-demo-execution-target-metadata-1",
            "case_id": case_id,
            "partition": "DEVELOPMENT",
            "status": "EXECUTION_IDS_ONLY_NOT_A_REVIEWED_MAPPING",
            "intervention_type": (config.get("intervention") or {}).get("type") if isinstance(config.get("intervention"), Mapping) else None,
            "input_ids": list(config.get("input_ids", ())),
            "outgoing_synapse_block_ids": list(config.get("outgoing_synapse_block_ids", ())),
            "readout_ids": list(config.get("readout_ids", ())),
            "mapping_review_status": "NOT_PRESENT_IN_SOURCE_RUN_ARTIFACTS",
        }
        written.append(_write_json(package_root, f"{case_folder}/mapping/execution_target_metadata.json", mapping_metadata))

    study_availability = {
        "schema_version": "v1-demo-studyspec-availability-1",
        "case_id": case_id,
        "available": False,
        "status": "MISSING_EXPECTED_ARTIFACT",
        "reason": "The source run manifests contain LIF configuration, not a frozen V1 Workbench StudySpec; none was fabricated.",
    }
    written.append(_write_json(package_root, f"{case_folder}/studyspec/availability.json", study_availability))

    for state, status_doc, metrics_doc, run_doc in (
        ("control", control_status, control_metrics, control_manifest),
        ("condition", condition_status, condition_metrics, condition_manifest),
    ):
        selected_metrics = _selected_metrics(metrics_doc)
        if status_doc is not None or selected_metrics is not None:
            status_summary = {
                "schema_version": "v1-demo-simulation-output-1",
                "case_id": case_id,
                "partition": "DEVELOPMENT",
                "state": state,
                "run_status": status_doc.get("status") if status_doc else None,
                "metrics_status": metrics_doc.get("status") if metrics_doc else None,
                "metrics": selected_metrics.get("metrics", {}) if selected_metrics else {},
                "scientific_scope": "Existing computational LIF readout only; not behavior probability or biological validation.",
            }
            written.append(_write_json(package_root, f"{case_folder}/simulation/{state}_output.json", status_summary))
        qc = _selected_qc(status_doc, metrics_doc, _selected_configuration(run_doc))
        if qc is not None:
            written.append(_write_json(package_root, f"{case_folder}/qc/{state}_data_audit.json", qc))
        if run_doc is not None:
            config_doc = _selected_configuration(run_doc) or {}
            provenance = {
                "schema_version": "v1-demo-run-provenance-1",
                "case_id": case_id,
                "partition": "DEVELOPMENT",
                "state": state,
                "run_status": run_doc.get("status"),
                "run_id": run_doc.get("run_id"),
                "created_at_utc": run_doc.get("created_at_utc"),
                "finished_at_utc": run_doc.get("finished_at_utc"),
                "dataset_id": run_doc.get("dataset_id"),
                "id_namespace": run_doc.get("id_namespace"),
                "duration_s": run_doc.get("duration_s"),
                "seed": run_doc.get("seed"),
                "trial_count": run_doc.get("trial_count"),
                "intervention_type": (config_doc.get("intervention") or {}).get("type") if isinstance(config_doc.get("intervention"), Mapping) else None,
                "input_ids": list(config_doc.get("input_ids", ())),
                "silenced_ids": list(config_doc.get("outgoing_synapse_block_ids", ())),
                "readout_ids": list(config_doc.get("readout_ids", ())),
                "source_identities": _selected_source_provenance(run_doc),
                "metrics_sha256": (run_doc.get("metrics") or {}).get("sha256") if isinstance(run_doc.get("metrics"), Mapping) else None,
                "spike_output_sha256": (run_doc.get("spike_output") or {}).get("sha256") if isinstance(run_doc.get("spike_output"), Mapping) else None,
                "v1_source_commit": "b48edd0d027eb89d6351c1fc70d8b93320faa60c",
            }
            written.append(_write_json(package_root, f"{case_folder}/provenance/{state}_provenance.json", provenance))

    return source_hashes, readiness, written


def _write_text(package_root: Path, relative_path: str, content: str) -> dict[str, str]:
    target = package_root / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    raw = content.encode("utf-8")
    target.write_bytes(raw)
    return {"path": Path(relative_path).as_posix(), "sha256": sha256_bytes(raw), "size_bytes": len(raw)}


def build_package(
    *,
    source_root: Path = DEFAULT_SOURCE_ROOT,
    package_root: Path = DEFAULT_PACKAGE_ROOT,
    allowlist_path: Path = ALLOWLIST_PATH,
) -> dict[str, Any]:
    allowlist, allowed_ids = load_allowlist(allowlist_path)
    source_root = source_root.resolve()
    package_root = package_root.resolve()
    _assert_isolated_paths(source_root, package_root)
    package_root.mkdir(parents=True, exist_ok=False)

    all_sources: list[dict[str, Any]] = []
    readiness_rows: list[dict[str, Any]] = []
    package_files: list[dict[str, str]] = []
    case_ids_from_package: list[str] = []
    for case_id in allowed_ids:
        source_rows, readiness, written = _build_case(
            case_id=case_id,
            allowed_ids=allowed_ids,
            source_root=source_root,
            package_root=package_root,
        )
        all_sources.extend({"case_id": case_id, **item} for item in source_rows)
        readiness_rows.append(readiness)
        package_files.extend(written)
        case_manifest_path = package_root / "cases" / case_id / "case.json"
        case_manifest = json.loads(case_manifest_path.read_text(encoding="utf-8"))
        if case_manifest.get("case_id") != case_id or case_manifest.get("partition") != "DEVELOPMENT":
            raise PackageBuildError("case package identity check failed")
        case_ids_from_package.append(str(case_manifest["case_id"]))

    if set(case_ids_from_package) != set(allowed_ids) or len(case_ids_from_package) != 74:
        raise PackageBuildError("package membership differs from the locked 74 DEVELOPMENT IDs")
    if set(case_ids_from_package) - set(allowed_ids):
        raise PackageBuildError("package contains an unknown case ID")

    shared_allowlist = {
        "schema_version": allowlist["schema_version"],
        "partition": "DEVELOPMENT",
        "case_count": 74,
        "development_split_sha256": DEVELOPMENT_SPLIT_SHA256,
        "case_ids": list(allowed_ids),
    }
    package_files.append(_write_json(package_root, "shared/v1_development_case_allowlist_v1.json", shared_allowlist))
    package_files.append(_write_json(package_root, "demo_case_readiness.json", {
        "schema_version": "v1-demo-case-readiness-1",
        "partition": "DEVELOPMENT",
        "case_count": len(readiness_rows),
        "cases": sorted(readiness_rows, key=lambda item: item["case_id"]),
    }))

    counts = {
        "case_count": len(readiness_rows),
        "complete_cases": sum(
            all(row[key] for key in (
                "required_input_present", "mapping_present", "study_spec_available",
                "simulation_artifact_available", "qc_artifact_available", "provenance_available",
            ))
            for row in readiness_rows
        ),
        "cases_missing_mapping": sum(not row["mapping_present"] for row in readiness_rows),
        "cases_missing_study_spec": sum(not row["study_spec_available"] for row in readiness_rows),
        "cases_missing_simulation_artifacts": sum(not row["simulation_artifact_available"] for row in readiness_rows),
        "cases_missing_qc_artifacts": sum(not row["qc_artifact_available"] for row in readiness_rows),
        "cases_missing_provenance": sum(not row["provenance_available"] for row in readiness_rows),
        "execution_target_ids_present": sum(row["execution_target_ids_present"] for row in readiness_rows),
    }
    readme = (
        "# Isolated V1 DEVELOPMENT demo package\n\n"
        "This package contains only the project's locked 74-case DEVELOPMENT allowlist. "
        "It is an artifact-isolation package, not a claim that every case has a reviewed mapping or frozen Workbench StudySpec.\n\n"
        f"- Development split SHA-256: `{DEVELOPMENT_SPLIT_SHA256}`\n"
        f"- Cases: `{counts['case_count']}`\n"
        f"- Complete end-to-end source cases: `{counts['complete_cases']}`\n"
        "- Case outputs are computational LIF readouts, not biological validation or behavior probabilities.\n"
        "- A run's recorded input IDs do not constitute scientific mapping approval.\n"
        "- No label or outcome fields are included.\n"
    )
    package_files.append(_write_text(package_root, "README.md", readme))
    package_files.sort(key=lambda item: item["path"])
    all_sources.sort(key=lambda item: (item["case_id"], item["path"]))

    package_payload_sha = sha256_bytes(
        "\n".join(f"{item['path']}\t{item['sha256']}" for item in package_files).encode("utf-8")
    )
    manifest = {
        "schema_version": "v1-demo-development-package-1",
        "package_version": "1.0.0",
        "package_purpose": "Physically isolated, label-free V1 advisor-demo inputs and existing DEVELOPMENT LIF outputs.",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "builder_version": BUILDER_VERSION,
        "builder_commit": _git_commit(),
        "builder_script_sha256": sha256_bytes(Path(__file__).read_bytes()),
        "v1_source_commit": "b48edd0d027eb89d6351c1fc70d8b93320faa60c",
        "source_root": str(source_root),
        "package_root": str(package_root),
        "partition": "DEVELOPMENT",
        "case_count": 74,
        "case_ids": list(allowed_ids),
        "development_split_sha256": DEVELOPMENT_SPLIT_SHA256,
        "membership_source_artifact_sha256": allowlist.get("source_registry_sha256"),
        "source_artifact_identities": all_sources,
        "package_files": package_files,
        "package_payload_sha256": package_payload_sha,
        "membership_verification": {
            "expected_case_count": 74,
            "package_case_count": len(case_ids_from_package),
            "extra_case_count": 0,
            "missing_case_count": 0,
            "result": "PASS",
            "method": "exact allowlist-derived case paths; no directory enumeration",
        },
        "artifact_availability": counts,
        "availability_semantics": {
            "mapping_present": "A reviewed V1 mapping record is present; execution IDs alone do not count.",
            "study_spec_available": "A frozen Workbench StudySpec source artifact is present; none is fabricated.",
            "qc_artifact_available": "Both state metrics contain the source data-audit object.",
            "complete_cases": "All listed technical artifacts and reviewed mapping plus Workbench StudySpec are available.",
        },
        "labels_included": False,
        "outcomes_included": False,
        "simulation_executed_by_builder": False,
        "benchmark_evaluation_executed_by_builder": False,
        "external_validation_executed_by_builder": False,
    }
    manifest_entry = _write_json(package_root, "manifest.json", manifest)

    checksum_entries = sorted(
        [*package_files, manifest_entry], key=lambda item: item["path"]
    )
    checksums_text = "".join(f"{item['sha256']}  {item['path']}\n" for item in checksum_entries)
    _write_text(package_root, "checksums.sha256", checksums_text)

    for item in checksum_entries:
        exact_path = package_root / item["path"]
        if not exact_path.is_file() or sha256_bytes(exact_path.read_bytes()) != item["sha256"]:
            raise PackageBuildError(f"package checksum verification failed: {item['path']}")

    label_audit_paths = [package_root / item["path"] for item in package_files if item["path"].endswith(".json")]
    for exact_path in label_audit_paths:
        value = json.loads(exact_path.read_text(encoding="utf-8"))
        if _contains_forbidden_fields(value):
            raise PackageBuildError(f"label/outcome field found in package artifact: {exact_path.name}")

    return {
        "status": "PASS",
        "package_root": str(package_root),
        "case_count": len(case_ids_from_package),
        "development_split_sha256": DEVELOPMENT_SPLIT_SHA256,
        "manifest_sha256": sha256_bytes((package_root / "manifest.json").read_bytes()),
        "package_payload_sha256": package_payload_sha,
        "package_checksum_verification": "PASS",
        "demo_package_contains_labels": False,
        "artifact_availability": counts,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--package-root", type=Path, default=DEFAULT_PACKAGE_ROOT)
    parser.add_argument("--allowlist", type=Path, default=ALLOWLIST_PATH)
    args = parser.parse_args(argv)
    try:
        result = build_package(
            source_root=args.source_root,
            package_root=args.package_root,
            allowlist_path=args.allowlist,
        )
    except (OSError, ValueError, PackageBuildError, json.JSONDecodeError) as error:
        print(json.dumps({"status": "BLOCKED", "reason": f"{type(error).__name__}: {error}"}, indent=2))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
