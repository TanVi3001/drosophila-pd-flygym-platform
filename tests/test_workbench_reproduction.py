from __future__ import annotations

import json
from pathlib import Path

from drosophila_pd.workbench.reproduction import verify_reproduction


def _write_campaign(root: Path, *, study_id: str, failed: bool = False) -> Path:
    artifact_dir = root / "artifacts" / study_id / "runs" / "job"
    artifact_dir.mkdir(parents=True)
    run_manifest = artifact_dir / "run_manifest.json"
    run_manifest.write_text(
        json.dumps(
            {
                "backend": "lif_2024",
                "provenance": {
                    "code_revision": "neural-commit",
                    "study_configuration_hash": "study-hash",
                    "backend_capabilities": {"name": "lif_2024"},
                },
            }
        ),
        encoding="utf-8",
    )
    if not failed:
        metrics_dir = artifact_dir / "lif_condition"
        metrics_dir.mkdir()
        (metrics_dir / "metrics.json").write_text(
            json.dumps(
                {
                    "metrics": {
                        "spike_count_total": 3,
                        "duration_s": 1.0,
                        "readout_rates_hz": {"mn9": 3.0},
                    }
                }
            ),
            encoding="utf-8",
        )
    job = {
        "job_id": "screen-candidate-seed-7",
        "status": "FAILED" if failed else "COMPLETED",
        "error": "invalid orientation" if failed else None,
        "artifact_dir": str(artifact_dir),
        "manifest_path": str(run_manifest),
        "config": {
            "candidate_id": "candidate",
            "seed": 7,
            "duration_s": 1.0,
            "intervention": {"type": "none"},
        },
    }
    manifest = root / "campaign_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "phase": "screening",
                "status": "PARTIAL" if failed else "PASS",
                "study_id": study_id,
                "study_configuration_hash": "study-hash",
                "study_config_sha256": "config-sha",
                "scientific_scope": "test",
                "jobs": [job],
            }
        ),
        encoding="utf-8",
    )
    return manifest


def test_reproduction_requires_explicit_failure_case(tmp_path: Path) -> None:
    reference = _write_campaign(tmp_path / "reference", study_id="reference")
    replica = _write_campaign(tmp_path / "replica", study_id="replica")

    result = verify_reproduction(
        reference,
        replica,
        operator_name="second operator",
        clean_install=True,
    )

    assert result["status"] == "BLOCKED"
    assert result["comparison"]["outputs_within_declared_tolerance"] is True
    assert result["comparison"]["failure_states_checked"] is False
    assert result["subset"]["includes_failure_case"] is False


def test_reproduction_passes_success_and_failure_subsets(tmp_path: Path) -> None:
    reference = _write_campaign(tmp_path / "reference", study_id="reference")
    replica = _write_campaign(tmp_path / "replica", study_id="replica")
    failure_reference = _write_campaign(tmp_path / "failure-reference", study_id="failure-reference", failed=True)
    failure_replica = _write_campaign(tmp_path / "failure-replica", study_id="failure-replica", failed=True)

    result = verify_reproduction(
        reference,
        replica,
        operator_name="second operator",
        clean_install=True,
        failure_reference_manifest=failure_reference,
        failure_replica_manifest=failure_replica,
    )

    assert result["status"] == "PASS"
    assert result["comparison"]["manifests_match"] is True
    assert result["comparison"]["provenance_match"] is True
    assert result["comparison"]["outputs_within_declared_tolerance"] is True
    assert result["comparison"]["failure_states_checked"] is True
    assert result["subset"]["includes_success_case"] is True
    assert result["subset"]["includes_failure_case"] is True
    assert result["operator_role"] == "same_operator"
    assert result["independent_operator_claim_eligible"] is False


def test_reproduction_only_marks_explicit_second_operator_as_independent(tmp_path: Path) -> None:
    reference = _write_campaign(tmp_path / "reference", study_id="reference")
    replica = _write_campaign(tmp_path / "replica", study_id="replica")
    failure_reference = _write_campaign(tmp_path / "failure-reference", study_id="failure-reference", failed=True)
    failure_replica = _write_campaign(tmp_path / "failure-replica", study_id="failure-replica", failed=True)

    result = verify_reproduction(
        reference,
        replica,
        operator_name="separate human",
        operator_role="second_operator",
        clean_install=True,
        failure_reference_manifest=failure_reference,
        failure_replica_manifest=failure_replica,
    )

    assert result["status"] == "PASS"
    assert result["independent_operator_claim_eligible"] is True
