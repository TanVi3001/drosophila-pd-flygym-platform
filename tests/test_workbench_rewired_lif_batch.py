from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "run_shiu_v2_rewired_lif_batch",
    ROOT / "scripts" / "run_shiu_v2_rewired_lif_batch.py",
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_frozen_mapping_review_is_complete_and_approved() -> None:
    result = MODULE.validate_mapping(
        ROOT / "configs" / "workbench" / "shiu_public_benchmark_v2.json",
        ROOT / "configs" / "workbench" / "shiu_v2_flywire630_mapping.csv",
    )

    assert result["status"] == "READY"
    assert result["protocol_case_count"] == 106
    assert result["mapping_row_count"] == 106
    assert result["missing_case_ids"] == []
    assert result["unknown_case_ids"] == []
    assert result["duplicate_case_ids"] == []
    assert len(result["approved_case_ids"]) == 106
    assert result["pending_case_ids"] == []
    assert result["unassessable_case_ids"] == []
    assert result["rejected_case_ids"] == []
    assert result["invalid_rows"] == []


def test_mapping_gate_requires_two_reviewers_and_both_mn9_readouts(tmp_path: Path) -> None:
    source = ROOT / "configs" / "workbench" / "shiu_v2_flywire630_mapping.csv"
    target = tmp_path / "mapping.csv"
    with source.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
        fields = handle.seek(0) or next(csv.reader(handle))
    rows[0].update(
        {
            "mapping_status": "APPROVED",
            "assay_comparable": "YES",
            "input_ids_json": json.dumps(["720575940624963786"], separators=(",", ":")),
            "reviewer_1": "reviewer-a",
            "reviewer_2": "",
            "reviewer_1_decision": "APPROVED",
            "reviewer_2_decision": "APPROVED",
            "review_decision": "APPROVED",
        }
    )
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    result = MODULE.validate_mapping(
        ROOT / "configs" / "workbench" / "shiu_public_benchmark_v2.json",
        target,
    )

    assert result["status"] == "BLOCKED"
    assert result["invalid_rows"] == [
        {
            "case_id": "shiu_table3_row_002",
            "reason": "approved_row_requires_two_reviewers",
        }
    ]


def test_mapping_gate_requires_explicit_two_reviewer_decisions(tmp_path: Path) -> None:
    source = ROOT / "configs" / "workbench" / "shiu_v2_flywire630_mapping.csv"
    target = tmp_path / "mapping.csv"
    with source.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
        fields = handle.seek(0) or next(csv.reader(handle))
    rows[0].update(
        {
            "mapping_status": "APPROVED",
            "assay_comparable": "YES",
            "input_ids_json": json.dumps(["720575940624963786"], separators=(",", ":")),
            "reviewer_1": "reviewer-a",
            "reviewer_2": "reviewer-b",
            "reviewer_1_decision": "PENDING",
            "reviewer_2_decision": "PENDING",
            "review_decision": "APPROVED",
        }
    )
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    result = MODULE.validate_mapping(
        ROOT / "configs" / "workbench" / "shiu_public_benchmark_v2.json",
        target,
    )

    assert result["status"] == "BLOCKED"
    assert result["invalid_rows"] == [
        {
            "case_id": "shiu_table3_row_002",
            "reason": "approved_row_requires_two_reviewer_decisions",
        }
    ]


def test_rejected_mapping_blocks_ready_to_run(tmp_path: Path) -> None:
    source = ROOT / "configs" / "workbench" / "shiu_v2_flywire630_mapping.csv"
    target = tmp_path / "mapping.csv"
    with source.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
        fields = handle.seek(0) or next(csv.reader(handle))
    for row in rows:
        row.update(
            {
                "mapping_status": "APPROVED",
                "assay_comparable": "YES",
                "reviewer_1": "reviewer-a",
                "reviewer_2": "reviewer-b",
                "reviewer_1_decision": "APPROVED",
                "reviewer_2_decision": "APPROVED",
                "review_decision": "APPROVED",
            }
        )
    rows[-1]["mapping_status"] = "REJECTED"
    rows[-1]["assay_comparable"] = "NO"
    rows[-1]["reviewer_1_decision"] = "REJECTED"
    rows[-1]["reviewer_2_decision"] = "REJECTED"
    rows[-1]["review_decision"] = "REJECTED"
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    result = MODULE.validate_mapping(
        ROOT / "configs" / "workbench" / "shiu_public_benchmark_v2.json",
        target,
    )

    assert result["status"] == "BLOCKED"
    assert len(result["approved_case_ids"]) == 105
    assert len(result["rejected_case_ids"]) == 1
    assert result["rejected_case_ids"] == ["shiu_table3_row_107"]


def test_all_rejected_cases_cannot_be_ready(tmp_path: Path) -> None:
    source = ROOT / "configs" / "workbench" / "shiu_v2_flywire630_mapping.csv"
    target = tmp_path / "mapping.csv"
    with source.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
        fields = handle.seek(0) or next(csv.reader(handle))
    for row in rows:
        row.update(
            {
                "mapping_status": "REJECTED",
                "assay_comparable": "NO",
                "reviewer_1": "reviewer-a",
                "reviewer_2": "reviewer-b",
                "reviewer_1_decision": "REJECTED",
                "reviewer_2_decision": "REJECTED",
                "review_decision": "REJECTED",
            }
        )
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    result = MODULE.validate_mapping(
        ROOT / "configs" / "workbench" / "shiu_public_benchmark_v2.json",
        target,
    )

    assert result["status"] == "BLOCKED"
    assert result["approved_case_ids"] == []
    assert len(result["rejected_case_ids"]) == 106


def test_approved_mapping_requires_both_mn9_readouts(tmp_path: Path) -> None:
    source = ROOT / "configs" / "workbench" / "shiu_v2_flywire630_mapping.csv"
    target = tmp_path / "mapping.csv"
    with source.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
        fields = handle.seek(0) or next(csv.reader(handle))
    rows[0].update(
        {
            "mapping_status": "APPROVED",
            "assay_comparable": "YES",
            "input_ids_json": json.dumps(["720575940624963786"], separators=(",", ":")),
            "readout_ids_json": json.dumps(["720575940660219265"], separators=(",", ":")),
            "reviewer_1": "reviewer-a",
            "reviewer_2": "reviewer-b",
            "reviewer_1_decision": "APPROVED",
            "reviewer_2_decision": "APPROVED",
            "review_decision": "APPROVED",
        }
    )
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    result = MODULE.validate_mapping(
        ROOT / "configs" / "workbench" / "shiu_public_benchmark_v2.json",
        target,
    )

    assert result["status"] == "BLOCKED"
    assert result["invalid_rows"] == [
        {
            "case_id": "shiu_table3_row_002",
            "reason": "shiu_v2_requires_mn9_left_and_right_readout_ids",
        }
    ]


def test_resume_reuses_only_a_valid_pass_artifact(tmp_path: Path) -> None:
    output = tmp_path / "control"
    output.mkdir()
    (output / "status.json").write_text('{"status":"PASS"}\n', encoding="utf-8")
    (output / "metrics.json").write_text(
        json.dumps(
            {
                "metrics": {
                    "readout_rates_hz": {
                        "left": 10.0,
                        "right": 20.0,
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    result = MODULE._reusable_lif_result(output, ["left", "right"])

    assert result is not None
    assert result["resumed"] is True
    assert result["readout_rate_hz"] == 15.0


def test_resume_does_not_reuse_failed_or_incomplete_artifact(tmp_path: Path) -> None:
    output = tmp_path / "condition"
    output.mkdir()
    (output / "status.json").write_text('{"status":"FAILED"}\n', encoding="utf-8")

    assert MODULE._reusable_lif_result(output, ["left"]) is None
