"""Tests for Gap 4: Quantitative Literature Validation Matrix."""

from pathlib import Path
import sys
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_literature_benchmarks import (
    LITERATURE_BENCHMARKS,
    classify_concordance,
    evaluate_model_benchmarks,
)


def test_classify_concordance_levels():
    # Close match in same direction (<= 15 percentage points)
    assert classify_concordance(-0.15, -0.20) == "HIGH_QUANTITATIVE_CONCORDANCE"
    assert classify_concordance(0.14, 0.12) == "HIGH_QUANTITATIVE_CONCORDANCE"

    # Moderate match in same direction (<= 30 percentage points)
    assert classify_concordance(-0.15, -0.40) == "MODERATE_QUANTITATIVE_CONCORDANCE"

    # Opposing directions
    assert classify_concordance(-0.15, 0.20) == "DISCORDANT"
    assert classify_concordance(0.10, -0.05) == "DISCORDANT"


def test_literature_benchmarks_curated_for_all_models():
    expected_models = {
        "pink1",
        "parkin",
        "lrrk2",
        "dj1",
        "complexI",
        "pink1_age25",
        "pink1_parkin_OE_age25",
    }
    assert expected_models.issubset(set(LITERATURE_BENCHMARKS.keys()))


def test_evaluate_model_benchmarks_with_real_colab_results():
    results_dir = Path("colab_results_7models")
    if not results_dir.is_dir():
        pytest.skip("colab_results_7models directory not present in current test environment.")

    report = results_dir / "pink1_locomotion.json"
    evals = evaluate_model_benchmarks("pink1", report)
    assert len(evals) == 1
    assert evals[0]["concordance"] == "HIGH_QUANTITATIVE_CONCORDANCE"
