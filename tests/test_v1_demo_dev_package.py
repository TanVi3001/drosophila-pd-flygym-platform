from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
BUILDER_PATH = ROOT / "scripts/build_v1_demo_dev_package.py"
SPEC = importlib.util.spec_from_file_location("v1_demo_package_builder", BUILDER_PATH)
assert SPEC is not None and SPEC.loader is not None
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)


def _write_source_case(root: Path, case_id: str) -> None:
    config_base = {
        "dataset_id": "flywire-630-2023-03-23",
        "duration_s": 1.0,
        "id_namespace": "flywire_root_id",
        "outgoing_synapse_block_ids": [],
        "readout_ids": ["readout-1"],
        "seed": 20260922,
        "stimulus_rate_hz": 50.0,
        "stimulus_schedule": [],
        "trial_count": 1,
    }
    for state in ("control", "condition"):
        folder = root / case_id / state
        folder.mkdir(parents=True, exist_ok=True)
        ids = [] if state == "control" else ["input-1"]
        config = {
            **config_base,
            "condition_label": f"{case_id}_{state}",
            "input_ids": ids,
            "intervention": {"type": "none" if state == "control" else "activation"},
        }
        (folder / "status.json").write_text(
            json.dumps({"status": "PASS"}), encoding="utf-8"
        )
        metrics = {
            "schema_version": "test-metrics-1",
            "status": "PASS",
            "metrics": {
                "trial_count": 1,
                "duration_s": 1.0,
                "spike_count_total": 3,
                "neuron_count_in_output": 2,
                "readout_spike_counts": {"readout-1": 1},
                "readout_rates_hz": {"readout-1": 1.0},
            },
            "data_audit": {
                "output_ids_are_unique_after_string_cast": True,
                "declared_input_ids_missing_from_output": [],
                "declared_readout_ids_in_output": ["readout-1"],
                "declared_readout_ids_silent": [],
                "completeness": {"output_ids_missing_from_completeness": 0},
            },
        }
        (folder / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
        run = {
            "status": "PASS",
            "run_id": f"run-{case_id}-{state}",
            "created_at_utc": "2026-09-30T00:00:00+00:00",
            "finished_at_utc": "2026-09-30T00:00:01+00:00",
            "dataset_id": config_base["dataset_id"],
            "id_namespace": config_base["id_namespace"],
            "duration_s": 1.0,
            "seed": 20260922,
            "trial_count": 1,
            "condition": config,
            "source_provenance": {"connectivity": {"sha256": "c" * 64}},
            "metrics": {"sha256": "a" * 64},
            "spike_output": {"sha256": "b" * 64},
        }
        (folder / "run_manifest.json").write_text(json.dumps(run), encoding="utf-8")


@pytest.fixture
def synthetic_source(tmp_path: Path) -> tuple[Path, tuple[str, ...]]:
    _, case_ids = BUILDER.load_allowlist()
    source = tmp_path / "source-mixed-shape-test-only"
    source.mkdir()
    for case_id in case_ids:
        _write_source_case(source, case_id)
    # This unallowlisted sentinel must never be read or copied by the builder.
    sentinel = source / "shiu_table3_row_001" / "condition" / "run_manifest.json"
    sentinel.parent.mkdir(parents=True)
    sentinel.write_text("not-json-and-must-not-be-read", encoding="utf-8")
    return source, case_ids


def test_allowlist_is_exactly_locked_development_membership() -> None:
    payload, case_ids = BUILDER.load_allowlist()
    assert payload["partition"] == "DEVELOPMENT"
    assert len(case_ids) == len(set(case_ids)) == 74
    assert BUILDER.canonical_split_sha256(case_ids) == (
        "3f9b39c1b6e91d766e85eaa0347f79243553a9b73a51442e944b7d8135713467"
    )


def test_non_allowlisted_case_is_rejected_before_path_creation(tmp_path: Path) -> None:
    _, case_ids = BUILDER.load_allowlist()
    with pytest.raises(BUILDER.PackageBuildError, match="not in the locked"):
        BUILDER._assert_allowed_case("shiu_table3_row_001", case_ids)
    assert not (tmp_path / "shiu_table3_row_001").exists()


def test_package_root_must_be_outside_source_root(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    with pytest.raises(BUILDER.PackageBuildError, match="outside the source"):
        BUILDER._assert_isolated_paths(source, source / "package")


def test_builder_source_uses_no_directory_enumeration_or_ai_v2() -> None:
    tree = ast.parse(BUILDER_PATH.read_text(encoding="utf-8"))
    prohibited = {"iterdir", "glob", "rglob", "scandir", "walk", "listdir"}
    calls = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert not calls.intersection(prohibited)
    assert "ai_v2" not in BUILDER_PATH.read_text(encoding="utf-8").lower()


def test_package_membership_hashes_checksums_and_label_free_content(
    tmp_path: Path, synthetic_source: tuple[Path, tuple[str, ...]]
) -> None:
    source, case_ids = synthetic_source
    package = tmp_path / "isolated-package"
    result = BUILDER.build_package(source_root=source, package_root=package)
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    assert result["package_checksum_verification"] == "PASS"
    assert manifest["case_count"] == 74
    assert manifest["case_ids"] == list(case_ids)
    assert manifest["builder_script_sha256"] == hashlib.sha256(BUILDER_PATH.read_bytes()).hexdigest()
    assert manifest["membership_verification"] == {
        "expected_case_count": 74,
        "package_case_count": 74,
        "extra_case_count": 0,
        "missing_case_count": 0,
        "result": "PASS",
        "method": "exact allowlist-derived case paths; no directory enumeration",
    }
    assert not (package / "cases/shiu_table3_row_001").exists()

    checksum_lines = (package / "checksums.sha256").read_text(encoding="utf-8").splitlines()
    checksum_rows = [line.split("  ", 1) for line in checksum_lines]
    assert checksum_rows == sorted(checksum_rows, key=lambda row: row[1])
    for digest, relative in checksum_rows:
        assert hashlib.sha256((package / relative).read_bytes()).hexdigest() == digest

    for item in manifest["package_files"]:
        if not item["path"].endswith(".json"):
            continue
        payload = json.loads((package / item["path"]).read_text(encoding="utf-8"))
        assert not BUILDER._contains_forbidden_fields(payload)
    assert manifest["labels_included"] is False
    assert manifest["outcomes_included"] is False


def test_missing_exact_artifact_is_recorded_without_search(
    tmp_path: Path, synthetic_source: tuple[Path, tuple[str, ...]]
) -> None:
    source, case_ids = synthetic_source
    case_id = case_ids[0]
    missing_path = source / case_id / "condition" / "metrics.json"
    missing_path.unlink()
    (missing_path.parent / "metrics_backup.json").write_text("{}", encoding="utf-8")

    package = tmp_path / "package-with-missing-source"
    result = BUILDER.build_package(source_root=source, package_root=package)
    readiness = json.loads((package / "demo_case_readiness.json").read_text(encoding="utf-8"))
    first = next(row for row in readiness["cases"] if row["case_id"] == case_id)
    assert result["status"] == "PASS"
    assert first["simulation_artifact_available"] is False
    case_manifest = json.loads((package / "cases" / case_id / "case.json").read_text(encoding="utf-8"))
    assert f"{case_id}/condition/metrics.json" in case_manifest["missing_expected_artifacts"]
    partial_output = json.loads(
        (package / "cases" / case_id / "simulation/condition_output.json").read_text(encoding="utf-8")
    )
    assert partial_output["metrics"] == {}
    assert not any("metrics_backup" in item["path"] for item in manifest_files(package))


def manifest_files(package_root: Path) -> list[dict[str, str]]:
    manifest = json.loads((package_root / "manifest.json").read_text(encoding="utf-8"))
    return list(manifest["package_files"])
