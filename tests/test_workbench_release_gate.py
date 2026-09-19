from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
import yaml

from drosophila_pd.workbench import BenchmarkProtocol


ROOT = Path(__file__).resolve().parents[1]
GATE_PATH = ROOT / "scripts" / "workbench_release_gate.py"


def _gate_module():
    spec = importlib.util.spec_from_file_location("workbench_release_gate", GATE_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError("could not load release gate module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _registry() -> tuple[Path, BenchmarkProtocol]:
    path = ROOT / "configs" / "workbench" / "shiu_public_benchmark_v1.yaml"
    protocol = BenchmarkProtocol.from_dict(yaml.safe_load(path.read_text(encoding="utf-8")))
    return path, protocol


def _comparison(protocol: BenchmarkProtocol) -> dict[str, object]:
    case_ids = list(protocol.held_out_case_ids)
    report = {
        "status": "EVALUATED",
        "case_count": len(case_ids),
        "assessable_case_count": len(case_ids),
        "coverage": 1.0,
        "unassessable_cases": [],
        "evaluated_cases": [{"case_id": case_id} for case_id in case_ids],
        "class_balance": {"positive": 4, "negative": 4},
        "confusion_matrix": {},
        "precision": 0.5,
        "recall": 0.5,
        "precision_at_k": {"value": 0.5, "case_ids": case_ids[:3]},
        "false_negatives": [],
    }
    return {
        "comparison_version": 1,
        "protocol_hash": protocol.protocol_hash,
        "evaluation_split": "held_out",
        "baseline_protocol": {
            "calibration": "development_only_balanced_accuracy_threshold",
            "random_seed": 17,
        },
        "matched_evaluation": {
            "status": "COMPLETE",
            "held_out_case_count": len(protocol.held_out_case_ids),
            "common_assessable_case_count": len(protocol.held_out_case_ids),
            "common_assessable_case_ids": case_ids,
        },
        "systems": {
            name: dict(report)
            for name in ("workbench", "random", "effect_only", "heuristic")
        },
    }


def test_release_gate_requires_a_matched_held_out_comparison(tmp_path: Path) -> None:
    gate = _gate_module()
    registry_path, protocol = _registry()

    missing = gate._benchmark_evaluation_gate(None, registry_path)
    assert missing["status"] == "BLOCKED"

    report_path = tmp_path / "comparison.json"
    report_path.write_text(json.dumps(_comparison(protocol)), encoding="utf-8")
    result = gate._benchmark_evaluation_gate(report_path, registry_path)
    assert result["status"] == "PASS"


def test_release_gate_rejects_a_comparison_with_the_wrong_protocol_hash(tmp_path: Path) -> None:
    gate = _gate_module()
    registry_path, protocol = _registry()
    payload = _comparison(protocol)
    payload["protocol_hash"] = "wrong"
    report_path = tmp_path / "comparison.json"
    report_path.write_text(json.dumps(payload), encoding="utf-8")

    result = gate._benchmark_evaluation_gate(report_path, registry_path)
    assert result["status"] == "BLOCKED"
    assert "protocol hash" in result["detail"]


def test_release_gate_rejects_partial_matched_coverage(tmp_path: Path) -> None:
    gate = _gate_module()
    registry_path, protocol = _registry()
    payload = _comparison(protocol)
    payload["matched_evaluation"] = {
        "status": "PARTIAL",
        "held_out_case_count": len(protocol.held_out_case_ids),
        "common_assessable_case_count": 1,
        "common_assessable_case_ids": [protocol.held_out_case_ids[0]],
    }
    report_path = tmp_path / "partial-comparison.json"
    report_path.write_text(json.dumps(payload), encoding="utf-8")

    result = gate._benchmark_evaluation_gate(report_path, registry_path)
    assert result["status"] == "BLOCKED"
    assert "partial" in result["detail"]


def test_release_gate_requires_auditable_second_operator_fields(tmp_path: Path) -> None:
    gate = _gate_module()
    path = tmp_path / "reproduction.json"
    path.write_text(
        json.dumps(
            {
                "status": "PASS",
                "operator_role": "second_operator",
                "operator_name": "operator-b",
                "source_commit": "platform:abc;neural:def",
                "environment": {"clean_install": True, "lockfile_or_export": "lock.txt"},
                "inputs": {
                    "study_config_hash": "study-hash",
                    "public_artifact_hashes": ["artifact-hash"],
                },
                "subset": {"includes_success_case": True, "includes_failure_case": True},
                "comparison": {
                    "manifests_match": True,
                    "provenance_match": True,
                    "outputs_within_declared_tolerance": True,
                    "failure_states_checked": True,
                    "discrepancies": [],
                },
            }
        ),
        encoding="utf-8",
    )
    assert gate._reproduction_gate(path)["status"] == "PASS"


def _seed_campaign_payload(seeds: list[int], *, status: str = "PASS") -> dict[str, object]:
    return {
        "status": status,
        "seeds": seeds,
        "jobs": [
            {
                "status": "COMPLETED",
                "config": {"candidate_id": "control", "seed": seed},
            }
            for seed in seeds
        ],
    }


def test_seed_gate_requires_completed_jobs_for_every_declared_seed(tmp_path: Path) -> None:
    gate = _gate_module()
    payload = _seed_campaign_payload(list(range(10)))
    payload["jobs"] = payload["jobs"][:-1]
    path = tmp_path / "screening.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    result = gate._seed_gate(path, "screening_10_seeds", 10)

    assert result["status"] == "BLOCKED"
    assert "cover exactly" in result["detail"]


def test_seed_gate_checks_confirmation_against_reference_seed_set(tmp_path: Path) -> None:
    gate = _gate_module()
    payload = _seed_campaign_payload(list(range(100, 130)))
    payload.update(
        {
            "new_seed_set": True,
            "reference_seeds": list(range(10)),
        }
    )
    path = tmp_path / "confirmation.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    result = gate._seed_gate(path, "confirmation_30_new_seeds", 30, require_new=True)

    assert result["status"] == "PASS"


def test_computational_public_data_profile_keeps_human_limits_explicit() -> None:
    gate = _gate_module()
    artifact = ROOT / "data" / "benchmarks" / "41586_2024_7763_MOESM2_ESM.xlsx"
    if not artifact.is_file():
        pytest.skip("optional external benchmark workbook is not downloaded")
    result = gate._computational_public_data_profile(
        ROOT / "configs" / "workbench" / "shiu_public_benchmark_v2.json",
        artifact,
    )
    assert result["status"] == "READY_WITH_LIMITATIONS"
    assert "human_source_and_biological_mapping_review_pending" in result["limitations"]
    assert "independent_second_operator_not_claimed" in result["limitations"]
