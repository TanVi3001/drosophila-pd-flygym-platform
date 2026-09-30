from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "validate_external_validation_package.py"
SPEC = importlib.util.spec_from_file_location("external_validation_package", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def _refresh_checksums(root: Path) -> None:
    files = sorted(
        path for path in root.rglob("*")
        if path.is_file() and path.name != "checksums.sha256"
    )
    lines = [f"{_digest(path)}  {path.relative_to(root).as_posix()}" for path in files]
    (root / "checksums.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _synthetic_package(root: Path) -> Path:
    input_root = root / "validation_input_package"
    schema = {
        "schema_version": "external-validation-input-v1",
        "required_fields": [
            "case_id",
            "assay_metadata",
            "intervention_metadata",
            "input_neuron_identity",
            "simulator_input",
        ],
        "case_id_pattern": "^EXTVAL_[0-9]{4,}$",
    }
    _write_json(input_root / "input_schema.json", schema)
    cases = [
        {
            "case_id": f"EXTVAL_{number:04d}",
            "assay_metadata": {"assay_type": "SYNTHETIC_TEST_ONLY"},
            "intervention_metadata": {"mode": "synthetic_stimulation", "level": 1},
            "input_neuron_identity": {"namespace": "SYNTHETIC", "id": f"CELL_{number:04d}"},
            "simulator_input": {"seed": number, "duration_s": 1.0},
        }
        for number in (1, 2)
    ]
    (input_root / "cases.jsonl").write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in cases),
        encoding="utf-8",
    )
    manifest = {
        "schema_version": "external-validation-manifest-v1",
        "package_version": "1.0.0",
        "case_count": len(cases),
        "assay_type": "SYNTHETIC_TEST_ONLY",
        "source_citation": "Synthetic unit-test fixture; not a biological dataset",
        "input_schema_version": schema["schema_version"],
        "input_schema_sha256": _digest(input_root / "input_schema.json"),
        "label_schema_sha256": "a" * 64,
        "curator_identifier": "SYNTHETIC_CURATOR",
        "created_at_utc": "2026-09-30T00:00:00Z",
    }
    _write_json(root / "validation_manifest.json", manifest)
    _refresh_checksums(root)
    return root


def test_synthetic_input_package_passes_no_peeking_validation(tmp_path: Path) -> None:
    package = _synthetic_package(tmp_path / "owner_receipt")

    assert MODULE.validate_package(package) == []


@pytest.mark.parametrize("sensitive_field", ["label", "outcome", "phenotype", "response_class", "reference_label"])
def test_result_like_columns_are_rejected(tmp_path: Path, sensitive_field: str) -> None:
    package = _synthetic_package(tmp_path / "owner_receipt")
    cases_path = package / "validation_input_package" / "cases.jsonl"
    rows = [json.loads(line) for line in cases_path.read_text(encoding="utf-8").splitlines()]
    rows[0][sensitive_field] = "SYNTHETIC_FORBIDDEN_VALUE"
    cases_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    _refresh_checksums(package)

    errors = MODULE.validate_package(package)

    assert any("prohibited field name" in error for error in errors)


def test_outcome_like_values_and_non_neutral_ids_are_rejected(tmp_path: Path) -> None:
    package = _synthetic_package(tmp_path / "owner_receipt")
    cases_path = package / "validation_input_package" / "cases.jsonl"
    rows = [json.loads(line) for line in cases_path.read_text(encoding="utf-8").splitlines()]
    rows[0]["case_id"] = "EXTVAL_positive_0001"
    rows[1]["intervention_metadata"]["note"] = "synthetic positive response"
    cases_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    _refresh_checksums(package)

    errors = MODULE.validate_package(package)

    assert any("non-anonymous case ID" in error for error in errors)
    assert any("outcome-like value" in error for error in errors)


def test_sealed_labels_presence_is_rejected_without_reading_contents(tmp_path: Path) -> None:
    package = _synthetic_package(tmp_path / "owner_receipt")
    sealed = package / "validation_labels_sealed"
    sealed.mkdir()
    (sealed / "synthetic_secret.json").write_text("not opened", encoding="utf-8")

    errors = MODULE.validate_package(package)

    assert errors == ["sealed labels directory must not be present in owner workspace"]
    assert "synthetic_secret" not in " ".join(errors)


def test_checksum_mismatch_and_outcome_filename_are_rejected(tmp_path: Path) -> None:
    package = _synthetic_package(tmp_path / "owner_receipt")
    (package / "validation_input_package" / "observed_results.csv").write_text("x\n1\n", encoding="utf-8")

    errors = MODULE.validate_package(package)

    assert any("prohibited filename" in error for error in errors)


def test_checksum_tampering_is_rejected(tmp_path: Path) -> None:
    package = _synthetic_package(tmp_path / "owner_receipt")
    cases_path = package / "validation_input_package" / "cases.jsonl"
    cases_path.write_text(cases_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    errors = MODULE.validate_package(package)

    assert any("SHA-256 mismatch" in error for error in errors)


def test_access_policy_seals_labels_before_prediction_freeze() -> None:
    policy = json.loads((ROOT / "configs/workbench/external_validation_access_policy_v1.json").read_text(encoding="utf-8"))
    prefreeze = ["CURATION", "INPUT_RELEASED", "OWNER_MAPPING_REVIEW", "PREDICTION_EXECUTION", "PREDICTIONS_FROZEN"]
    protected_roles = ["owner", "codex_development_agent", "llm_rag", "simulation", "model_training"]

    for role in protected_roles:
        for stage in prefreeze:
            permissions = policy["principals"][role][stage]
            assert permissions["labels"] is False
            assert permissions["outcomes"] is False

    evaluator = policy["principals"]["independent_evaluator"]
    for stage in ["CURATION", "INPUT_RELEASED", "OWNER_MAPPING_REVIEW", "PREDICTION_EXECUTION", "PREDICTIONS_FROZEN"]:
        assert evaluator[stage]["labels"] is False
        assert evaluator[stage]["outcomes"] is False
    assert evaluator["LABEL_RELEASE"]["labels"] is True
