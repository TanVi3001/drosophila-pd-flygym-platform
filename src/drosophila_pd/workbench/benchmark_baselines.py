"""Development-only calibration and baseline score helpers.

The public Shiu labels describe model-versus-experiment agreement. A raw
Workbench effect score is therefore not itself a binary benchmark prediction.
This module fits a deterministic score threshold on the declared development
split and applies that frozen threshold to held-out scores. It never reads
held-out labels during calibration.
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable, Sequence
from typing import Any, Mapping

from .benchmark import BenchmarkProtocol, compare_benchmark_systems
from .graph_nulls import GraphEdge, degree_preserving_rewire


def _finite_score(value: Any) -> float | None:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    return score if math.isfinite(score) else None


def _confusion(protocol: BenchmarkProtocol, case_ids: list[str], scores: Mapping[str, float], threshold: float, direction: str) -> dict[str, int]:
    by_id = {case.case_id: case for case in protocol.cases}
    confusion = {"true_positive": 0, "true_negative": 0, "false_positive": 0, "false_negative": 0}
    for case_id in case_ids:
        score = scores[case_id]
        positive = score >= threshold if direction == "higher_is_positive" else score <= threshold
        actual = by_id[case_id].reference_label
        if actual == "positive" and positive:
            confusion["true_positive"] += 1
        elif actual == "negative" and not positive:
            confusion["true_negative"] += 1
        elif actual == "negative" and positive:
            confusion["false_positive"] += 1
        else:
            confusion["false_negative"] += 1
    return confusion


def _balanced_accuracy(confusion: Mapping[str, int]) -> float:
    positive_denominator = confusion["true_positive"] + confusion["false_negative"]
    negative_denominator = confusion["true_negative"] + confusion["false_positive"]
    if not positive_denominator or not negative_denominator:
        return 0.0
    sensitivity = confusion["true_positive"] / positive_denominator
    specificity = confusion["true_negative"] / negative_denominator
    return (sensitivity + specificity) / 2.0


def calibrate_threshold(
    protocol: BenchmarkProtocol,
    development_scores: Mapping[str, Any],
    *,
    direction: str = "higher_is_positive",
) -> dict[str, Any]:
    """Fit one deterministic threshold using only the development split.

    The objective is balanced accuracy so the 17/4 class imbalance cannot make
    an always-negative rule look attractive. Ties prefer the threshold with
    the highest positive precision, then the smallest threshold in the
    declared score direction. The complete calibration record is returned for
    provenance and must be stored with the held-out report.
    """

    if direction not in {"higher_is_positive", "lower_is_positive"}:
        raise ValueError("direction must be higher_is_positive or lower_is_positive")
    development_ids = list(protocol.development_case_ids)
    if not development_ids:
        raise ValueError("protocol has no development split")
    scores: dict[str, float] = {}
    missing: list[str] = []
    for case_id in development_ids:
        score = _finite_score(development_scores.get(case_id))
        if score is None:
            missing.append(case_id)
        else:
            scores[case_id] = score
    if not scores:
        raise ValueError("development calibration requires at least one finite score")
    assessable_labels = {
        protocol_case.reference_label
        for protocol_case in protocol.cases
        if protocol_case.case_id in scores
    }
    if assessable_labels != {"positive", "negative"}:
        raise ValueError("development calibration requires both reference classes among assessable cases")

    calibration_ids = [case_id for case_id in development_ids if case_id in scores]
    unique_scores = sorted(set(scores.values()))
    candidates = [unique_scores[0] - 1.0]
    candidates.extend((left + right) / 2.0 for left, right in zip(unique_scores, unique_scores[1:]))
    candidates.append(unique_scores[-1] + 1.0)
    ranked: list[tuple[float, float, float, dict[str, int]]] = []
    for threshold in candidates:
        confusion = _confusion(protocol, calibration_ids, scores, threshold, direction)
        balanced = _balanced_accuracy(confusion)
        precision_denominator = confusion["true_positive"] + confusion["false_positive"]
        precision = (
            confusion["true_positive"] / precision_denominator
            if precision_denominator
            else 0.0
        )
        tie_threshold = -threshold if direction == "higher_is_positive" else threshold
        ranked.append((balanced, precision, tie_threshold, confusion))
    best_index = max(range(len(ranked)), key=lambda index: ranked[index][:3])
    best = ranked[best_index]
    threshold = candidates[best_index]
    return {
        "calibration_version": 1,
        "status": "CALIBRATED" if not missing else "CALIBRATED_PARTIAL",
        "protocol_hash": protocol.protocol_hash,
        "split": "development",
        "case_ids": [case_id for case_id in development_ids if case_id in scores],
        "unassessable_case_ids": missing,
        "development_case_count": len(development_ids),
        "assessable_development_case_count": len(scores),
        "direction": direction,
        "threshold": threshold,
        "objective": "balanced_accuracy",
        "development_balanced_accuracy": best[0],
        "development_confusion_matrix": best[3],
        "development_score_range": {"min": min(scores.values()), "max": max(scores.values())},
    }


def apply_calibration(
    protocol: BenchmarkProtocol,
    scores: Mapping[str, Any],
    calibration: Mapping[str, Any],
    *,
    evaluation_split: str = "held_out",
) -> dict[str, dict[str, Any]]:
    """Turn scores into evaluator predictions using a frozen calibration."""

    if str(calibration.get("protocol_hash", "")) != protocol.protocol_hash:
        raise ValueError("calibration protocol hash does not match benchmark protocol")
    if str(calibration.get("split", "")).lower() != "development":
        raise ValueError("calibration must be fitted on the development split")
    direction = str(calibration.get("direction", ""))
    threshold = _finite_score(calibration.get("threshold"))
    if direction not in {"higher_is_positive", "lower_is_positive"} or threshold is None:
        raise ValueError("calibration has an invalid direction or threshold")
    split = str(evaluation_split).lower()
    if split == "held_out":
        case_ids = list(protocol.held_out_case_ids)
    elif split == "development":
        case_ids = list(protocol.development_case_ids)
    elif split == "all":
        case_ids = [case.case_id for case in protocol.cases]
    else:
        raise ValueError("evaluation_split must be all, development, or held_out")

    predictions: dict[str, dict[str, Any]] = {}
    for case_id in case_ids:
        score = _finite_score(scores.get(case_id))
        if score is None:
            predictions[case_id] = {
                "assessable": False,
                "reason": "score_missing_or_non_finite",
            }
            continue
        positive = score >= threshold if direction == "higher_is_positive" else score <= threshold
        predictions[case_id] = {
            "label": "positive" if positive else "negative",
            "score": score,
            "ranking_score": score if direction == "higher_is_positive" else -score,
            "assessable": True,
            "calibration_version": calibration.get("calibration_version"),
            "score_direction": direction,
        }
    return predictions


def seeded_random_scores(case_ids: list[str], *, seed: int) -> dict[str, float]:
    """Return reproducible random ranking scores for the declared case IDs."""

    rng = random.Random(seed)
    return {str(case_id): rng.random() for case_id in case_ids}


def degree_preserving_rewire_scores(
    edges: Sequence[GraphEdge | Mapping[str, Any]],
    score_fn: Callable[[Sequence[Mapping[str, Any]]], Mapping[str, Any]],
    *,
    seeds: Sequence[int],
    swaps: int,
    max_attempts: int | None = None,
) -> dict[str, Any]:
    """Run a declared graph-null scorer and aggregate finite case scores.

    ``score_fn`` is supplied by the backend-specific benchmark adapter.  This
    helper owns only null-graph generation, finite-value handling and
    provenance.  A partial null graph is retained in the manifest and never
    silently treated as a completed replicate.
    """

    if not seeds:
        raise ValueError("at least one rewire seed is required")
    if len(set(int(seed) for seed in seeds)) != len(seeds):
        raise ValueError("rewire seeds must be unique")
    score_replicates: list[dict[str, float]] = []
    null_manifests: list[dict[str, Any]] = []
    for seed in seeds:
        null = degree_preserving_rewire(
            edges,
            seed=int(seed),
            swaps=swaps,
            max_attempts=max_attempts,
        )
        null_manifests.append({key: value for key, value in null.items() if key != "edges"})
        if null["status"] != "PASS":
            continue
        raw_scores = score_fn(null["edges"])
        if not isinstance(raw_scores, Mapping):
            raise ValueError("rewired score_fn must return a mapping keyed by case_id")
        finite_scores = {
            str(case_id): score
            for case_id, value in raw_scores.items()
            if (score := _finite_score(value)) is not None
        }
        score_replicates.append(finite_scores)

    case_ids = sorted({case_id for replicate in score_replicates for case_id in replicate})
    aggregate: dict[str, float] = {}
    missing_by_case: dict[str, int] = {}
    for case_id in case_ids:
        values = [replicate[case_id] for replicate in score_replicates if case_id in replicate]
        missing_by_case[case_id] = len(score_replicates) - len(values)
        if values:
            aggregate[case_id] = sum(values) / len(values)
    return {
        "status": "PASS" if len(score_replicates) == len(seeds) else "PARTIAL",
        "system": "degree_preserving_rewire",
        "seeds": [int(seed) for seed in seeds],
        "requested_replicates": len(seeds),
        "completed_replicates": len(score_replicates),
        "swaps": int(swaps),
        "scores": aggregate,
        "missing_replicates_by_case": missing_by_case,
        "null_manifests": null_manifests,
        "scientific_scope": (
            "Aggregate structural graph-null scores; not a biological uncertainty "
            "interval and not an equally plausible connectome ensemble."
        ),
    }


def validate_score_mapping(protocol: BenchmarkProtocol, scores: Mapping[str, Any]) -> dict[str, Any]:
    """Report score coverage without turning missing values into negatives."""

    known = {case.case_id for case in protocol.cases}
    finite = [case_id for case_id in known if _finite_score(scores.get(case_id)) is not None]
    missing = sorted(known - set(finite))
    extra = sorted(set(str(key) for key in scores) - known)
    return {
        "status": "READY" if not missing else "INCOMPLETE",
        "case_count": len(known),
        "finite_score_count": len(finite),
        "coverage": len(finite) / len(known) if known else 0.0,
        "missing_case_ids": missing,
        "unknown_case_ids": extra,
    }


def prepare_benchmark_comparison(
    protocol: BenchmarkProtocol,
    scores_by_system: Mapping[str, Mapping[str, Any]],
    *,
    directions: Mapping[str, str] | None = None,
    random_seed: int = 0,
    required_systems: tuple[str, ...] = ("workbench", "random", "effect_only", "heuristic"),
) -> dict[str, Any]:
    """Calibrate declared score systems and build one held-out comparison.

    ``effect_only`` and ``heuristic`` scores must be supplied by the caller.
    The random baseline is generated here when omitted, with its seed recorded
    in the output. All systems use the same development-only calibration rule.
    """

    supplied = {str(name): values for name, values in scores_by_system.items()}
    missing_systems = [name for name in required_systems if name not in supplied and name != "random"]
    if missing_systems:
        raise ValueError("missing score systems: " + ", ".join(missing_systems))
    case_ids = [case.case_id for case in protocol.cases]
    if "random" not in supplied:
        supplied["random"] = seeded_random_scores(case_ids, seed=random_seed)
    directions = {str(name): str(value) for name, value in (directions or {}).items()}

    calibrations: dict[str, Any] = {}
    predictions: dict[str, dict[str, dict[str, Any]]] = {}
    score_validation: dict[str, Any] = {}
    for name, scores in supplied.items():
        if not isinstance(scores, Mapping):
            raise ValueError(f"scores for {name!r} must be an object keyed by case_id")
        score_validation[name] = validate_score_mapping(protocol, scores)
        if score_validation[name]["unknown_case_ids"]:
            raise ValueError(
                f"scores for {name!r} contain unknown case IDs: "
                + ", ".join(score_validation[name]["unknown_case_ids"])
            )
        calibration = calibrate_threshold(
            protocol,
            scores,
            direction=directions.get(name, "higher_is_positive"),
        )
        calibrations[name] = calibration
        predictions[name] = apply_calibration(protocol, scores, calibration, evaluation_split="held_out")
    comparison = {
        **compare_benchmark_systems(
            protocol,
            predictions,
            evaluation_split="held_out",
        ),
        "baseline_protocol": {
            "calibration": "development_only_balanced_accuracy_threshold",
            "random_seed": random_seed,
            "random_scores_generated": "random" not in scores_by_system,
            "required_systems": list(required_systems),
        },
    }
    held_out_ids = list(protocol.held_out_case_ids)
    assessable_by_system = {
        name: sorted(
            case_id
            for case_id in held_out_ids
            if bool(predictions[name].get(case_id, {}).get("assessable"))
        )
        for name in predictions
    }
    common_assessable = sorted(
        set(held_out_ids).intersection(*(set(case_ids) for case_ids in assessable_by_system.values()))
    )
    comparison["matched_evaluation"] = {
        "status": "COMPLETE" if len(common_assessable) == len(held_out_ids) else "PARTIAL",
        "held_out_case_count": len(held_out_ids),
        "common_assessable_case_count": len(common_assessable),
        "common_assessable_case_ids": common_assessable,
        "coverage_by_system": {
            name: len(case_ids) / len(held_out_ids) if held_out_ids else 0.0
            for name, case_ids in assessable_by_system.items()
        },
        "unassessable_case_ids_by_system": {
            name: sorted(set(held_out_ids) - set(case_ids))
            for name, case_ids in assessable_by_system.items()
        },
        "note": (
            "System-level reports retain their own assessable coverage; this intersection is the "
            "predeclared matched denominator for cross-system interpretation."
        ),
    }
    return {
        **comparison,
        "calibration_by_system": calibrations,
        "score_validation_by_system": score_validation,
        "predictions_by_system": predictions,
    }


__all__ = [
    "apply_calibration",
    "calibrate_threshold",
    "degree_preserving_rewire_scores",
    "prepare_benchmark_comparison",
    "seeded_random_scores",
    "validate_score_mapping",
]
