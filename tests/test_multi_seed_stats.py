"""Tests for multi-seed statistical replication pipeline.

Covers:
  - _aggregate_seeds: correct mean/std/n computation
  - _wilcoxon_test: structure and key fields present
  - _ablation3_comparison: correct logic for EXPANDED_ADDS_VALUE
  - _write_summary_csv: file is created with correct columns
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
import sys
import tempfile

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Import functions to test
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from run_brain_driven_seeds import (
    ALL_METRICS,
    BASIC_METRICS,
    EXPANDED_METRICS,
    _ablation3_comparison,
    _aggregate_seeds,
    _wilcoxon_test,
    _write_summary_csv,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_seed_results(
    n: int,
    speed_values: list[float],
    duty_values: list[float] | None = None,
) -> list[dict]:
    """Build minimal fake seed results for testing."""
    if duty_values is None:
        duty_values = [0.8] * n
    results = []
    for i in range(n):
        metrics: dict = {k: float("nan") for k in ALL_METRICS}
        metrics["mean_planar_speed_mm_s"] = speed_values[i]
        metrics["walking_duty_cycle"] = duty_values[i]
        metrics["planar_displacement_mm"] = speed_values[i] * 5.0
        metrics["body_height_mean_mm"] = 1.2
        metrics["heading_yaw_change_rad"] = 0.1
        metrics["trajectory_efficiency"] = 0.9
        metrics["pause_bout_count"] = float(i + 1)
        metrics["left_right_asymmetry"] = 0.05 * (i + 1)
        metrics["cumulative_turning_rad"] = 0.2 * (i + 1)
        results.append({
            "seed": 42 + i * 100,
            "condition_id": "test",
            "overall_pass": True,
            "derived_locomotion_metrics": metrics,
        })
    return results


# ---------------------------------------------------------------------------
# Tests: _aggregate_seeds
# ---------------------------------------------------------------------------

class TestAggregateSeeds:
    def test_mean_correct(self) -> None:
        results = _make_seed_results(3, speed_values=[10.0, 12.0, 14.0])
        agg = _aggregate_seeds(results, metric_keys=["mean_planar_speed_mm_s"])
        assert agg["mean_planar_speed_mm_s"]["mean"] == pytest.approx(12.0)

    def test_std_correct(self) -> None:
        results = _make_seed_results(5, speed_values=[10.0, 11.0, 12.0, 13.0, 14.0])
        agg = _aggregate_seeds(results, metric_keys=["mean_planar_speed_mm_s"])
        # ddof=1 std of [10,11,12,13,14] = sqrt(10/4) = sqrt(2.5) ≈ 1.5811
        assert agg["mean_planar_speed_mm_s"]["std"] == pytest.approx(np.std([10, 11, 12, 13, 14], ddof=1))

    def test_n_correct(self) -> None:
        results = _make_seed_results(5, speed_values=[10.0] * 5)
        agg = _aggregate_seeds(results)
        assert agg["mean_planar_speed_mm_s"]["n"] == 5

    def test_values_stored(self) -> None:
        results = _make_seed_results(3, speed_values=[1.0, 2.0, 3.0])
        agg = _aggregate_seeds(results, metric_keys=["mean_planar_speed_mm_s"])
        assert sorted(agg["mean_planar_speed_mm_s"]["values"]) == [1.0, 2.0, 3.0]

    def test_nan_metric_excluded(self) -> None:
        results = _make_seed_results(3, speed_values=[10.0, 12.0, 14.0])
        # Inject NaN for cumulative_turning_rad in result 0
        results[0]["derived_locomotion_metrics"]["cumulative_turning_rad"] = float("nan")
        agg = _aggregate_seeds(results, metric_keys=["cumulative_turning_rad"])
        # Only 2 valid values
        assert agg["cumulative_turning_rad"]["n"] == 2

    def test_all_metrics_returned(self) -> None:
        results = _make_seed_results(2, speed_values=[10.0, 12.0])
        agg = _aggregate_seeds(results)
        for key in ALL_METRICS:
            assert key in agg, f"Missing metric: {key}"


# ---------------------------------------------------------------------------
# Tests: _wilcoxon_test
# ---------------------------------------------------------------------------

class TestWilcoxonTest:
    def test_structure_keys(self) -> None:
        b_results = _make_seed_results(5, speed_values=[15.0, 14.5, 15.5, 14.8, 15.2])
        p_results = _make_seed_results(5, speed_values=[10.0,  9.5, 10.5,  9.8, 10.2])
        b_agg = _aggregate_seeds(b_results)
        p_agg = _aggregate_seeds(p_results)
        result = _wilcoxon_test(b_agg, p_agg)
        for key in ["mean_planar_speed_mm_s", "walking_duty_cycle"]:
            assert key in result
            entry = result[key]
            for field in ["baseline_mean", "perturbed_mean", "delta_mean", "delta_pct", "n_seeds"]:
                assert field in entry, f"Missing field {field!r} in {key}"

    def test_delta_pct_direction(self) -> None:
        b_results = _make_seed_results(5, speed_values=[15.0] * 5)
        p_results = _make_seed_results(5, speed_values=[12.0] * 5)
        b_agg = _aggregate_seeds(b_results)
        p_agg = _aggregate_seeds(p_results)
        result = _wilcoxon_test(b_agg, p_agg, metric_keys=["mean_planar_speed_mm_s"])
        entry = result["mean_planar_speed_mm_s"]
        # delta_pct should be negative (perturbed slower)
        assert entry["delta_pct"] == pytest.approx(-20.0)

    def test_constant_pairs_are_reported_without_scipy_warning(self) -> None:
        b_results = _make_seed_results(5, speed_values=[10.0] * 5)
        p_results = _make_seed_results(5, speed_values=[10.0] * 5)
        b_agg = _aggregate_seeds(b_results)
        p_agg = _aggregate_seeds(p_results)
        result = _wilcoxon_test(
            b_agg,
            p_agg,
            metric_keys=["mean_planar_speed_mm_s"],
        )
        entry = result["mean_planar_speed_mm_s"]
        assert entry["p_value"] == pytest.approx(1.0)
        assert entry["significant_0.05"] is False
        assert entry["test_method"] == "wilcoxon_signed_rank_constant_zero"

    def test_significant_detection_when_scipy_available(self) -> None:
        """If scipy is available and N >= 6, clear difference should yield two-sided p < 0.05."""
        pytest.importorskip("scipy")
        b_results = _make_seed_results(6, speed_values=[15.0, 15.1, 14.9, 15.2, 14.8, 15.3])
        p_results = _make_seed_results(6, speed_values=[8.0,  8.1,  7.9,  8.2,  7.8,  8.0])
        b_agg = _aggregate_seeds(b_results)
        p_agg = _aggregate_seeds(p_results)
        result = _wilcoxon_test(b_agg, p_agg, metric_keys=["mean_planar_speed_mm_s"])
        entry = result["mean_planar_speed_mm_s"]
        # Should detect significant difference (p = 0.03125 < 0.05 for N=6)
        assert entry.get("significant_0.05") is True


# ---------------------------------------------------------------------------
# Tests: _ablation3_comparison
# ---------------------------------------------------------------------------

class TestAblation3:
    def _make_wilcoxon_with_expanded_sig(self) -> dict:
        """All basic metrics p>0.05, one expanded metric p<0.05."""
        w = {}
        for k in BASIC_METRICS:
            w[k] = {"significant_0.05": False, "p_value": 0.3, "delta_pct": -5.0}
        for k in EXPANDED_METRICS:
            w[k] = {"significant_0.05": False, "p_value": 0.3, "delta_pct": -5.0}
        # Make one expanded metric significant
        w[EXPANDED_METRICS[0]]["significant_0.05"] = True
        w[EXPANDED_METRICS[0]]["p_value"] = 0.02
        return w

    def _make_wilcoxon_all_nonsig(self) -> dict:
        w = {}
        for k in BASIC_METRICS + EXPANDED_METRICS:
            w[k] = {"significant_0.05": False, "p_value": 0.5, "delta_pct": -2.0}
        return w

    def test_expanded_adds_value(self) -> None:
        w = self._make_wilcoxon_with_expanded_sig()
        result = _ablation3_comparison(w)
        assert result["conclusion"] == "EXPANDED_ADDS_VALUE"
        assert result["expanded_significant_count"] >= 1

    def test_basic_sufficient_when_no_expanded_sig(self) -> None:
        w = self._make_wilcoxon_all_nonsig()
        result = _ablation3_comparison(w)
        assert result["conclusion"] == "BASIC_SUFFICIENT"

    def test_output_structure(self) -> None:
        w = self._make_wilcoxon_all_nonsig()
        result = _ablation3_comparison(w)
        for key in [
            "ablation", "description", "basic_metrics_count",
            "expanded_metrics_count", "basic_significant_count",
            "expanded_significant_count", "conclusion",
        ]:
            assert key in result


# ---------------------------------------------------------------------------
# Tests: _write_summary_csv
# ---------------------------------------------------------------------------

class TestWriteSummaryCSV:
    def test_csv_created_with_columns(self, tmp_path: Path) -> None:
        results = _make_seed_results(3, speed_values=[10.0, 12.0, 14.0])
        agg = _aggregate_seeds(results, metric_keys=["mean_planar_speed_mm_s"])
        model_stats = {"pink1": {"baseline": agg, "perturbed": agg}}
        csv_path = tmp_path / "summary.csv"
        _write_summary_csv(model_stats, csv_path)
        assert csv_path.is_file()
        with csv_path.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or []
        for col in ["model", "condition", "metric", "mean", "std", "n"]:
            assert col in fieldnames

    def test_csv_row_count(self, tmp_path: Path) -> None:
        results = _make_seed_results(3, speed_values=[10.0, 12.0, 14.0])
        agg = _aggregate_seeds(results, metric_keys=["mean_planar_speed_mm_s"])
        model_stats = {
            "pink1": {"baseline": agg, "perturbed": agg},
            "parkin": {"baseline": agg, "perturbed": agg},
        }
        csv_path = tmp_path / "summary.csv"
        _write_summary_csv(model_stats, csv_path)
        with csv_path.open(encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        # 2 models × 2 conditions × 1 metric = 4 rows
        assert len(rows) == 4
