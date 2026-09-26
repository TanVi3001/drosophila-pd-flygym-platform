from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from export_shiu_mapping_registry import build_registry  # noqa: E402


def _protocol():
    return {
        "cases": [
            {"case_id": "case-1", "metadata": {"cell_type": "DAN"}},
            {"case_id": "case-2", "metadata": {"cell_type": "asteroid"}},
            {"case_id": "case-3", "metadata": {"cell_type": "missing"}},
        ]
    }


def test_registry_preserves_source_sets_and_marks_aliases_for_review():
    registry = build_registry(
        _protocol(),
        {"DAN": [1, 2], "Asteroid": [3]},
        {"1", "2", "3"},
        source_sha256="a" * 64,
    )

    exact, alias, missing = registry["mapping_records"]
    assert registry["case_count"] == 3
    assert registry["exact_match_count"] == 1
    assert registry["casefold_alias_count"] == 1
    assert exact["target_ids"] == ["1", "2"]
    assert exact["review_status"] == "PENDING_SCIENTIFIC_REVIEW"
    assert alias["source_mapping_key"] == "Asteroid"
    assert alias["mapping_status"] == "CASEFOLD_ALIAS_REQUIRES_REVIEW"
    assert alias["review_status"] == "PENDING_SCIENTIFIC_REVIEW"
    assert missing["mapping_status"] == "MISSING"
    assert missing["target_ids"] == []


def test_registry_never_exports_duplicate_or_out_of_dataset_ids_as_ready():
    registry = build_registry(
        _protocol(),
        {"DAN": [1, 99, 99], "Asteroid": [3]},
        {"1", "2", "3"},
        source_sha256="b" * 64,
    )

    exact = registry["mapping_records"][0]
    assert exact["mapping_status"] == "INVALID_SOURCE_ID_SET"
    assert exact["review_status"] == "PENDING_SCIENTIFIC_REVIEW"
    assert registry["invalid_id_set_count"] == 1


def test_registry_rejects_missing_source_checksum():
    try:
        build_registry(_protocol(), {"DAN": [1]}, {"1"}, source_sha256="")
    except ValueError as error:
        assert "sha256" in str(error)
    else:
        raise AssertionError("registry generation requires a source checksum")
