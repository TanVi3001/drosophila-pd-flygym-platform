from __future__ import annotations

import importlib.util
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


def test_mapping_gate_requires_two_reviewers_and_one_readout(tmp_path: Path) -> None:
    source = ROOT / "configs" / "workbench" / "shiu_v2_flywire630_mapping.csv"
    target = tmp_path / "mapping.csv"
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    text = target.read_text(encoding="utf-8")
    text = text.replace(
        "PENDING,PENDING,[],[],[],,,PENDING,",
        'APPROVED,YES,["720575940624963786"],[],["720575940660219265"],reviewer-a,,APPROVED,',
        1,
    )
    target.write_text(text, encoding="utf-8")
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
