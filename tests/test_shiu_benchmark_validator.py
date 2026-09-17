from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _validator_module():
    path = ROOT / "scripts" / "validate_shiu_benchmark_registry.py"
    spec = importlib.util.spec_from_file_location("validate_shiu_benchmark_registry", path)
    if spec is None or spec.loader is None:
        raise AssertionError("could not load benchmark validator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_source_label_column_is_resolved_per_section() -> None:
    validator = _validator_module()
    rows = {
        2: {5: "Correct (i.e., aligns with experimental results?)"},
        160: {5: "Correct (i.e., aligns with experimental results?)"},
        173: {5: "Correct (i.e., aligns with experimental results?)"},
        178: {6: "Correct (i.e., aligns with experimental results?)"},
    }
    wanted = "Correct (i.e., aligns with experimental results?)"

    assert validator._find_header_column(rows, 3, wanted) == (2, 5)
    assert validator._find_header_column(rows, 165, wanted) == (160, 5)
    assert validator._find_header_column(rows, 174, wanted) == (173, 5)
    assert validator._find_header_column(rows, 180, wanted) == (178, 6)


def test_source_label_column_requires_a_preceding_header() -> None:
    validator = _validator_module()
    with pytest.raises(ValueError, match="no preceding header"):
        validator._find_header_column(
            {2: {5: "Different column"}},
            3,
            "Correct (i.e., aligns with experimental results?)",
        )
