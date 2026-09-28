from __future__ import annotations

import hashlib
import json
from pathlib import Path

from drosophila_pd.workbench.reproduction import verify_reproduction


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


def _success_campaign(root: Path, *, run_marker: str) -> tuple[Path, Path, Path]:
    artifact_root = root / "artifacts" / "study" / "runs" / "job"
    metrics_path = artifact_root / "lif_condition" / "metrics.json"
    nested_manifest = artifact_root / "lif_condition" / "run_manifest.json"
    _write_json(metrics_path, {"created_at": run_marker, "metrics": {"readout_rates_hz": {"mn9": 3.0}}})
    _write_json(nested_manifest, {"run_id": run_marker, "status": "PASS"})

    artifact_hashes = {
        path.relative_to(artifact_root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (metrics_path, nested_manifest)
    }
    outer_manifest = artifact_root / "run_manifest.json"
    _write_json(
        outer_manifest,
        {
            "manifest_version": 1,
            "backend": "lif_2024",
            "configuration_hash": "same-job-config",
            "artifact_hashes": artifact_hashes,
            "provenance": {
                "code_revision": "same-neural-commit",
                "study_configuration_hash": "same-study-hash",
                "backend_capabilities": {"name": "lif_2024"},
                "input_hashes": {"connectivity": "same-connectivity-hash"},
                "environment": {"python_version": "3.12.10"},
                "code_state": {"dirty": False, "content_sha256": "same-code-state"},
            },
        },
    )
    campaign = root / "campaign.json"
    _write_json(
        campaign,
        {
            "phase": "reproduction_success",
            "status": "PASS",
            "study_id": "study",
            "study_configuration_hash": "same-study-hash",
            "study_config_sha256": "same-study-config-sha",
            "scientific_scope": "synthetic test",
            "jobs": [
                {
                    "job_id": "success",
                    "status": "COMPLETED",
                    "artifact_dir": str(artifact_root),
                    "manifest_path": str(outer_manifest),
                    "config": {"candidate_id": "control", "seed": 7},
                }
            ],
        },
    )
    return campaign, metrics_path, nested_manifest


def _failure_campaign(root: Path) -> Path:
    campaign = root / "failure_campaign.json"
    _write_json(
        campaign,
        {
            "phase": "reproduction_failure_qc",
            "status": "PARTIAL",
            "study_id": "study",
            "study_configuration_hash": "same-study-hash",
            "study_config_sha256": "same-study-config-sha",
            "scientific_scope": "synthetic test",
            "jobs": [
                {
                    "job_id": "failure",
                    "status": "FAILED",
                    "error": "declared QC failure",
                    "artifact_dir": str(root / "failed-run"),
                    "config": {"candidate_id": "control", "seed": 7},
                }
            ],
        },
    )
    return campaign


def _verify(reference: Path, replica: Path, root: Path) -> dict:
    return verify_reproduction(
        reference,
        replica,
        operator_name="owner",
        operator_role="same_operator",
        clean_install=True,
        failure_reference_manifest=_failure_campaign(root / "failure-reference"),
        failure_replica_manifest=_failure_campaign(root / "failure-replica"),
    )


def test_valid_reruns_allow_different_serialization_metadata(tmp_path: Path) -> None:
    reference, _, _ = _success_campaign(tmp_path / "reference", run_marker="first-run")
    replica, _, _ = _success_campaign(tmp_path / "replica", run_marker="second-run")

    result = _verify(reference, replica, tmp_path)

    assert result["status"] == "PASS"
    assert result["comparison"]["provenance_match"] is True
    assert result["comparison"]["outputs_within_declared_tolerance"] is True
    assert result["comparison"]["failure_states_checked"] is True
    assert result["independent_operator_claim_eligible"] is False
    details = result["details"]["success_case"]
    assert details["reference_artifact_hashes"] != details["replica_artifact_hashes"]


def test_tampered_nested_manifest_is_rejected(tmp_path: Path) -> None:
    reference, _, nested_manifest = _success_campaign(tmp_path / "reference", run_marker="first-run")
    replica, _, _ = _success_campaign(tmp_path / "replica", run_marker="second-run")
    _write_json(nested_manifest, {"run_id": "tampered", "status": "PASS"})

    result = _verify(reference, replica, tmp_path)

    assert result["status"] == "BLOCKED"
    assert any(
        "artifact hashes do not match files on disk" in item
        for item in result["comparison"]["discrepancies"]
    )


def test_tampered_metrics_are_rejected(tmp_path: Path) -> None:
    reference, metrics_path, _ = _success_campaign(tmp_path / "reference", run_marker="first-run")
    replica, _, _ = _success_campaign(tmp_path / "replica", run_marker="second-run")
    _write_json(metrics_path, {"metrics": {"readout_rates_hz": {"mn9": 999.0}}})

    result = _verify(reference, replica, tmp_path)

    assert result["status"] == "BLOCKED"
    assert any(
        "artifact hashes do not match files on disk" in item
        for item in result["comparison"]["discrepancies"]
    )
