from __future__ import annotations

import pytest

from drosophila_pd.workbench import (
    BenchmarkProtocol,
    RetrospectiveCase,
    apply_calibration,
    calibrate_threshold,
    compare_benchmark_systems,
    evaluate_retrospective_benchmark,
    freeze_benchmark_protocol,
    prepare_benchmark_comparison,
    seeded_random_scores,
    summarize_sensitivity,
    validate_score_mapping,
)


def _protocol() -> BenchmarkProtocol:
    return BenchmarkProtocol(
        protocol_id="test-retrospective-v1",
        source={"citation": "public test fixture", "status": "fixture_only"},
        selection_rule="four frozen cases with two positive and two negative reference labels",
        min_case_count=4,
        precision_at_k=2,
        cases=tuple(
            RetrospectiveCase(
                case_id=f"case-{index}",
                condition=f"condition-{index}",
                reference_label="positive" if index < 2 else "negative",
            )
            for index in range(4)
        ),
    )


def test_retrospective_benchmark_reports_confusion_metrics_and_false_negatives() -> None:
    report = evaluate_retrospective_benchmark(
        _protocol(),
        {
            "case-0": {"label": "positive", "score": 0.9},
            "case-1": {"label": "negative", "score": 0.2},
            "case-2": {"label": "negative", "score": 0.8},
            "case-3": {"label": "positive", "score": 0.7},
        },
    )

    assert report["coverage"] == 1.0
    assert report["confusion_matrix"] == {
        "true_positive": 1,
        "true_negative": 1,
        "false_positive": 1,
        "false_negative": 1,
    }
    assert report["precision"] == 0.5
    assert report["recall"] == 0.5
    assert report["precision_at_k"]["value"] == 0.5
    assert report["false_negatives"] == ["case-1"]


def test_unassessable_case_reduces_coverage_without_becoming_negative() -> None:
    report = evaluate_retrospective_benchmark(
        _protocol(),
        {
            "case-0": {"label": "positive", "score": 0.9},
            "case-1": {"assessable": False, "reason": "missing_readout"},
            "case-2": {"label": "negative", "score": 0.8},
            "case-3": {"label": "negative", "score": 0.7},
        },
    )

    assert report["coverage"] == 0.75
    assert report["confusion_matrix"]["false_negative"] == 0
    assert report["unassessable_cases"][0]["case_id"] == "case-1"


def test_protocol_requires_frozen_minimum_and_both_reference_classes() -> None:
    with pytest.raises(ValueError, match="at least 20"):
        BenchmarkProtocol(
            protocol_id="too-small",
            source={},
            selection_rule="not enough cases",
            cases=(RetrospectiveCase("one", "one", "positive"),),
        )

    with pytest.raises(ValueError, match="both positive and negative"):
        BenchmarkProtocol(
            protocol_id="one-class",
            source={},
            selection_rule="four positive cases",
            min_case_count=2,
            cases=(
                RetrospectiveCase("one", "one", "positive"),
                RetrospectiveCase("two", "two", "positive"),
            ),
        )


def test_sensitivity_summary_is_descriptive_and_does_not_infer_thresholds() -> None:
    report = summarize_sensitivity(
        [
            {"precision": 0.5, "recall": 0.4, "precision_at_k": 0.5, "coverage": 1.0},
            {"precision": 0.6, "recall": 0.3, "precision_at_k": 0.5, "coverage": 0.75},
        ]
    )

    assert report["status"] == "DESCRIPTIVE_ONLY"
    assert report["run_count"] == 2
    assert report["metrics"]["precision"]["range"] == 0.1
    assert "threshold" in report["note"]


def test_public_benchmark_freeze_requires_reviewed_split_and_preserves_held_out() -> None:
    cases = tuple(
        RetrospectiveCase(
            case_id=f"public-{index:02d}",
            condition=f"condition-{index:02d}",
            reference_label="positive" if index < 10 else "negative",
            source={
                "locator": "https://example.org/public-table",
                "label_basis": "reviewed_experimental_outcome",
            },
        )
        for index in range(20)
    )
    draft = BenchmarkProtocol(
        protocol_id="public-freeze-fixture-v1",
        source={"citation": "public fixture"},
        selection_rule="predeclared fixture selection",
        cases=cases,
        min_case_count=20,
        precision_at_k=3,
    )
    frozen = freeze_benchmark_protocol(
        draft,
        development_case_ids=[f"public-{index:02d}" for index in list(range(8)) + list(range(10, 18))],
        held_out_case_ids=["public-08", "public-09", "public-18", "public-19"],
        frozen_at="2026-09-16T00:00:00+00:00",
        label_policy="positive means the public experimental outcome supports the declared effect",
        freeze_commit="abc123",
    )
    assert frozen.freeze_validation()["status"] == "READY"
    assert frozen.freeze_status == "FROZEN"
    assert frozen.held_out_case_ids == ("public-08", "public-09", "public-18", "public-19")

    report = evaluate_retrospective_benchmark(
        frozen,
        {
            case.case_id: {"label": case.reference_label, "score": 1.0 if case.reference_label == "positive" else 0.0}
            for case in cases
        },
        evaluation_split="held_out",
    )
    assert report["evaluation_split"] == "held_out"
    assert report["case_count"] == 4
    assert report["coverage"] == 1.0
    assert report["freeze_validation"]["status"] == "READY"


def test_held_out_evaluation_rejects_an_unfrozen_protocol() -> None:
    cases = tuple(
        RetrospectiveCase(
            case_id=f"case-{index}",
            condition=f"condition-{index}",
            reference_label="positive" if index < 10 else "negative",
            source={"locator": "https://example.org/table", "label_basis": "reviewed"},
        )
        for index in range(20)
    )
    protocol = BenchmarkProtocol(
        "draft-held-out-v1",
        {},
        "fixed",
        cases,
        development_case_ids=tuple(f"case-{index}" for index in range(10)),
        held_out_case_ids=tuple(f"case-{index}" for index in range(10, 20)),
    )
    with pytest.raises(ValueError, match="frozen, validated protocol"):
        evaluate_retrospective_benchmark(protocol, {}, evaluation_split="held_out")


def test_benchmark_system_comparison_uses_the_same_split() -> None:
    cases = tuple(
        RetrospectiveCase(
            f"case-{index}",
            f"condition-{index}",
            "positive" if index < 10 else "negative",
            source={"locator": "https://example.org/table", "label_basis": "reviewed"},
        )
        for index in range(20)
    )
    protocol = freeze_benchmark_protocol(
        BenchmarkProtocol("compare-v1", {}, "fixed", cases),
        development_case_ids=[f"case-{index}" for index in list(range(8)) + list(range(10, 18))],
        held_out_case_ids=["case-8", "case-9", "case-18", "case-19"],
        frozen_at="2026-09-16T00:00:00+00:00",
        label_policy="reviewed public outcome",
    )
    predictions = {
        case.case_id: {"label": case.reference_label, "score": float(case.reference_label == "positive")}
        for case in cases
    }
    result = compare_benchmark_systems(
        protocol,
        {"workbench": predictions, "effect_only": predictions},
    )
    assert result["evaluation_split"] == "held_out"
    assert set(result["systems"]) == {"workbench", "effect_only"}
    assert all(report["case_count"] == 4 for report in result["systems"].values())
    assert result["matched_evaluation"]["status"] == "COMPLETE"
    assert result["matched_evaluation"]["common_assessable_case_count"] == 4
    assert result["matched_evaluation"]["systems"]["workbench"]["average_precision"] == 1.0


def test_common_denominator_excludes_unassessable_cases_without_relabeling_them() -> None:
    protocol = _calibration_protocol()
    complete = {
        case.case_id: {"label": case.reference_label, "score": float(case.reference_label == "positive")}
        for case in protocol.cases
    }
    incomplete = dict(complete)
    incomplete[protocol.held_out_case_ids[0]] = {"assessable": False, "reason": "missing_readout"}
    result = compare_benchmark_systems(
        protocol,
        {"workbench": complete, "effect_only": incomplete},
    )
    assert result["matched_evaluation"]["common_assessable_case_count"] == 9
    assert result["systems"]["effect_only"]["unassessable_cases"]


def _calibration_protocol() -> BenchmarkProtocol:
    cases = tuple(
        RetrospectiveCase(
            f"cal-{index:02d}",
            f"condition-{index:02d}",
            "positive" if index % 2 == 0 else "negative",
            source={"locator": "https://example.org/table", "label_basis": "reviewed"},
        )
        for index in range(20)
    )
    return freeze_benchmark_protocol(
        BenchmarkProtocol("calibration-v1", {}, "fixed", cases),
        development_case_ids=[f"cal-{index:02d}" for index in range(10)],
        held_out_case_ids=[f"cal-{index:02d}" for index in range(10, 20)],
        frozen_at="2026-09-16T00:00:00+00:00",
        label_policy="reviewed public agreement",
    )


def test_calibration_uses_development_only_and_preserves_held_out_coverage() -> None:
    protocol = _calibration_protocol()
    scores = {
        case.case_id: (0.9 if case.reference_label == "positive" else 0.1)
        for case in protocol.cases
    }
    calibration = calibrate_threshold(protocol, scores)
    predictions = apply_calibration(protocol, scores, calibration, evaluation_split="held_out")

    assert calibration["split"] == "development"
    assert calibration["development_balanced_accuracy"] == 1.0
    assert set(predictions) == set(protocol.held_out_case_ids)
    assert {row["label"] for row in predictions.values()} == {"positive", "negative"}


def test_calibration_keeps_missing_development_scores_unassessable() -> None:
    protocol = _calibration_protocol()
    scores = {
        case.case_id: (0.9 if case.reference_label == "positive" else 0.1)
        for case in protocol.cases
    }
    missing_case = protocol.development_case_ids[0]
    scores.pop(missing_case)
    calibration = calibrate_threshold(protocol, scores)

    assert calibration["status"] == "CALIBRATED_PARTIAL"
    assert calibration["unassessable_case_ids"] == [missing_case]
    assert calibration["assessable_development_case_count"] == 9


def test_evaluation_uses_declared_ranking_score_for_lower_is_better_systems() -> None:
    protocol = _protocol()
    predictions = {
        "case-0": {"label": "positive", "score": 0.1, "ranking_score": -0.1},
        "case-1": {"label": "positive", "score": 0.2, "ranking_score": -0.2},
        "case-2": {"label": "negative", "score": 0.9, "ranking_score": -0.9},
        "case-3": {"label": "negative", "score": 0.8, "ranking_score": -0.8},
    }

    report = evaluate_retrospective_benchmark(protocol, predictions, evaluation_split="all")

    assert report["precision_at_k"]["case_ids"] == ["case-0", "case-1"]
    assert report["precision_at_k"]["value"] == 1.0


def test_score_mapping_and_random_baseline_are_deterministic() -> None:
    protocol = _calibration_protocol()
    case_ids = [case.case_id for case in protocol.cases]
    first = seeded_random_scores(case_ids, seed=19)
    second = seeded_random_scores(case_ids, seed=19)
    assert first == second
    assert validate_score_mapping(protocol, first)["status"] == "READY"
    incomplete = dict(first)
    incomplete.pop(case_ids[0])
    assert validate_score_mapping(protocol, incomplete)["status"] == "INCOMPLETE"


def test_prepare_benchmark_comparison_calibrates_required_systems_on_development() -> None:
    protocol = _calibration_protocol()
    scores = {
        case.case_id: (0.9 if case.reference_label == "positive" else 0.1)
        for case in protocol.cases
    }
    result = prepare_benchmark_comparison(
        protocol,
        {
            "workbench": scores,
            "effect_only": scores,
            "heuristic": scores,
        },
        random_seed=17,
    )

    assert result["evaluation_split"] == "held_out"
    assert set(result["systems"]) == {"workbench", "random", "effect_only", "heuristic"}
    assert result["baseline_protocol"]["random_seed"] == 17
    assert all(report["case_count"] == 10 for report in result["systems"].values())
    assert result["matched_evaluation"]["status"] == "COMPLETE"
    assert result["matched_evaluation"]["common_assessable_case_count"] == 10


def test_prepare_benchmark_comparison_rejects_unknown_case_ids() -> None:
    protocol = _calibration_protocol()
    scores = {
        case.case_id: 0.5
        for case in protocol.cases
    }
    scores["not-in-protocol"] = 0.5
    with pytest.raises(ValueError, match="unknown case IDs"):
        prepare_benchmark_comparison(
            protocol,
            {"workbench": scores, "effect_only": scores, "heuristic": scores},
        )
