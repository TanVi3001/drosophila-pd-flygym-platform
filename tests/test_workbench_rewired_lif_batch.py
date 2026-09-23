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


def test_frozen_mapping_template_is_complete_but_not_approved() -> None:
    result = MODULE.validate_mapping(
        ROOT / "configs" / "workbench" / "shiu_public_benchmark_v2.json",
        ROOT / "configs" / "workbench" / "shiu_v2_flywire630_mapping.csv",
    )

    assert result["status"] == "BLOCKED"
    assert result["protocol_case_count"] == 106
    assert result["mapping_row_count"] == 106
    assert result["missing_case_ids"] == []
    assert result["unknown_case_ids"] == []
    assert result["duplicate_case_ids"] == []
    assert result["approved_case_ids"] == []
    assert len(result["pending_case_ids"]) == 106
    assert result["unassessable_case_ids"] == []


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
