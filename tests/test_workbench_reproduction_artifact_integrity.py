from __future__ import annotations

import hashlib
import json
from pathlib import Path

from drosophila_pd.workbench.reproduction import verify_reproduction


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _strict_success_campaign(
    root: Path,
    *,
    serialization_marker: str,
) -> tuple[Path, Path]:
    artifact_dir = (
        root
        / "artifacts"
        / "reproduction-study"
        / "runs"
        / "job"
    )
    lif_dir = artifact_dir / "lif_condition"
    lif_dir.mkdir(parents=True)

    metrics_path = lif_dir / "metrics.json"
    _write_json(
        metrics_path,
        {
            "created_at_utc": serialization_marker,
            "metrics": {
                "spike_count_total": 3,
                "duration_s": 1.0,
                "readout_rates_hz": {
                    "mn9": 3.0,
                },
            },
        },
    )

    # Deliberately different between reference and replica.
    # It is an auditable artifact, but its UUID/timestamp-like metadata
    # must not be treated as scientific output equality.
    nested_manifest = lif_dir / "run_manifest.json"
    _write_json(
        nested_manifest,
        {
            "run_id": serialization_marker,
            "created_at_utc": serialization_marker,
            "status": "PASS",
        },
    )

    artifact_hashes = {}
    for artifact in sorted(artifact_dir.rglob("*")):
        if not artifact.is_file():
            continue
        relative = artifact.relative_to(
            artifact_dir
        ).as_posix()
        if relative == "run_manifest.json":
            continue
        artifact_hashes[relative] = _sha256(
            artifact
        )

    outer_manifest = artifact_dir / "run_manifest.json"

    _write_json(
        outer_manifest,
        {
            "manifest_version": 1,
            "backend": "lif_2024",
            "configuration_hash": "job-config-hash",
            "artifact_hashes": artifact_hashes,
            "provenance": {
                "code_revision": "neural-commit",
                "study_configuration_hash": "study-hash",
                "backend_capabilities": {
                    "name": "lif_2024"
                },
                "input_hashes": {
                    "connectivity": "connectivity-hash",
                    "annotation_file": "annotation-hash",
                },
                "environment": {
                    "python_version": "3.12.10"
                },
                "code_state": {
                    "dirty": False,
                    "content_sha256": "source-state-hash",
                },
            },
        },
    )

    campaign = root / "campaign.json"

    _write_json(
        campaign,
        {
            "phase": "reproduction_success",
            "status": "PASS",
            "study_id": "reproduction-study",
            "study_configuration_hash": "study-hash",
            "study_config_sha256": "study-config-sha",
            "scientific_scope": "test reproduction scope",
            "jobs": [
                {
                    "job_id": "success",
                    "status": "COMPLETED",
                    "error": None,
                    "artifact_dir": str(artifact_dir),
                    "manifest_path": str(outer_manifest),
                    "config": {
                        "candidate_id": "no_intervention",
                        "seed": 7,
                        "duration_s": 1.0,
                    },
                }
            ],
        },
    )

    return campaign, metrics_path


def _failure_campaign(root: Path) -> Path:
    campaign = root / "failure_campaign.json"

    _write_json(
        campaign,
        {
            "phase": "reproduction_failure_qc",
            "status": "PARTIAL",
            "study_id": "reproduction-study",
            "study_configuration_hash": "study-hash",
            "study_config_sha256": "study-config-sha",
            "scientific_scope": "test reproduction scope",
            "jobs": [
                {
                    "job_id": "failure",
                    "status": "FAILED",
                    "error": "declared QC failure",
                    "artifact_dir": str(root / "failed-run"),
                    "config": {
                        "candidate_id": "no_intervention",
                        "seed": 7,
                        "duration_s": 1.0,
                    },
                }
            ],
        },
    )

    return campaign


def test_strict_reproduction_allows_nondeterministic_artifact_serialization(
    tmp_path: Path,
) -> None:
    reference, _ = _strict_success_campaign(
        tmp_path / "reference",
        serialization_marker="reference-run-id",
    )
    replica, _ = _strict_success_campaign(
        tmp_path / "replica",
        serialization_marker="replica-run-id",
    )

    failure_reference = _failure_campaign(
        tmp_path / "failure-reference"
    )
    failure_replica = _failure_campaign(
        tmp_path / "failure-replica"
    )

    result = verify_reproduction(
        reference,
        replica,
        operator_name="owner",
        operator_role="same_operator",
        clean_install=True,
        failure_reference_manifest=failure_reference,
        failure_replica_manifest=failure_replica,
    )

    assert result["status"] == "PASS"
    assert result["comparison"]["manifests_match"] is True
    assert result["comparison"]["provenance_match"] is True
    assert (
        result["comparison"][
            "outputs_within_declared_tolerance"
        ]
        is True
    )
    assert (
        result["comparison"]["failure_states_checked"]
        is True
    )

    success = result["details"]["success_case"]

    # The byte-level artifacts are allowed to differ between valid reruns.
    assert (
        success["reference_artifact_hashes"]
        != success["replica_artifact_hashes"]
    )


def test_strict_reproduction_still_rejects_tampered_artifact(
    tmp_path: Path,
) -> None:
    reference, metrics = _strict_success_campaign(
        tmp_path / "reference",
        serialization_marker="reference-run-id",
    )
    replica, _ = _strict_success_campaign(
        tmp_path / "replica",
        serialization_marker="replica-run-id",
    )

    failure_reference = _failure_campaign(
        tmp_path / "failure-reference"
    )
    failure_replica = _failure_campaign(
        tmp_path / "failure-replica"
    )

    # Modify a file AFTER its declared SHA-256 was frozen.
    metrics.write_text(
        '{"metrics":{"spike_count_total":999}}\n',
        encoding="utf-8",
    )

    result = verify_reproduction(
        reference,
        replica,
        operator_name="owner",
        operator_role="same_operator",
        clean_install=True,
        failure_reference_manifest=failure_reference,
        failure_replica_manifest=failure_replica,
    )

    assert result["status"] == "BLOCKED"

    discrepancies = result["comparison"][
        "discrepancies"
    ]

    assert any(
        "artifact hashes do not match files on disk"
        in item
        for item in discrepancies
    )
