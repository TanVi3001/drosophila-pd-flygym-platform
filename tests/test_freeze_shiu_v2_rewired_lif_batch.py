from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "scripts" / "freeze_shiu_v2_rewired_lif_batch.py"
SPEC = importlib.util.spec_from_file_location("freeze_shiu_batch", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _write_case(root: Path, case_id: str, *, rate: float = 0.0) -> None:
    for state in ("control", "condition"):
        state_root = root / case_id / state
        state_root.mkdir(parents=True)
        metrics = {
            "status": "PASS",
            "metrics": {
                "spike_count_total": 0,
                "trial_count": 1,
                "active_neurons_per_trial": {"mean": 0},
                "readout_rates_hz": {
                    "720575940645521262": rate,
                    "720575940660219265": rate,
                },
            },
        }
        (state_root / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
        (state_root / "status.json").write_text(json.dumps({"status": "PASS"}), encoding="utf-8")


def _fixture(tmp_path: Path, count: int = 106) -> tuple[Path, Path, Path, Path, Path, Path]:
    batch = tmp_path / "batch"
    batch.mkdir()
    scores = {}
    for index in range(2, count + 2):
        case_id = f"shiu_table3_row_{index:03d}"
        _write_case(batch, case_id, rate=1.0 if index == 2 else 0.0)
        scores[case_id] = 1.0 if index == 2 else 0.0
    (batch / "batch_summary.json").write_text(
        json.dumps({"status": "COMPLETE", "scores": scores, "score_contract": {}}),
        encoding="utf-8",
    )
    sources = []
    for name in ("protocol.json", "mapping.csv", "connectivity.parquet", "benchmark.json"):
        path = tmp_path / name
        path.write_text(name, encoding="utf-8")
        sources.append(path)
    return batch, *sources


def test_freeze_requires_all_106_cases(tmp_path: Path) -> None:
    batch, protocol, mapping, connectivity, report = _fixture(tmp_path, count=2)
    with pytest.raises(ValueError, match="exactly 106"):
        MODULE.freeze_batch(
            batch_root=batch,
            output_root=tmp_path / "freeze",
            protocol=protocol,
            mapping=mapping,
            connectivity=connectivity,
            benchmark_report=report,
        )


def test_freeze_writes_checksums_and_zero_audit(tmp_path: Path) -> None:
    batch, protocol, mapping, connectivity, report = _fixture(tmp_path)
    output = tmp_path / "freeze"
    manifest = MODULE.freeze_batch(
        batch_root=batch,
        output_root=output,
        protocol=protocol,
        mapping=mapping,
        connectivity=connectivity,
        benchmark_report=report,
    )
    assert manifest["status"] == "FROZEN"
    assert manifest["case_count"] == 106
    assert manifest["zero_score_count"] == 105
    assert (output / "checksums.sha256").is_file()
    audit = json.loads((output / "zero_score_audit.json").read_text(encoding="utf-8"))
    assert audit["class_counts"] == {"control_and_condition_silent": 105}
