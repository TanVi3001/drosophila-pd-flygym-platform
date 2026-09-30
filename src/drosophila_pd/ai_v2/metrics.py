"""Development ranking metrics. Higher scores rank earlier; ties use case ID."""

from __future__ import annotations

import math
from collections.abc import Mapping


def _ranked(labels: Mapping[str, int], scores: Mapping[str, float]) -> list[str]:
    if not labels or set(scores) - set(labels) or any(value not in (0, 1) for value in labels.values()):
        raise ValueError("binary labels and matching scored case IDs are required")
    if any(not math.isfinite(score) for score in scores.values()):
        raise ValueError("scores must be finite")
    return sorted(scores, key=lambda case: (-scores[case], case))


def average_precision(labels: Mapping[str, int], scores: Mapping[str, float]) -> float:
    ranked = _ranked(labels, scores)
    if set(scores) != set(labels):
        raise ValueError("AP requires complete scoring")
    positives = sum(labels.values())
    if not positives:
        raise ValueError("AP undefined without positive labels")
    hits = 0
    total = 0.0
    for position, case in enumerate(ranked, 1):
        if labels[case]:
            hits += 1
            total += hits / position
    return total / positives


def precision_at_k(labels: Mapping[str, int], scores: Mapping[str, float], k: int) -> float:
    ranked = _ranked(labels, scores)
    if k < 1 or len(ranked) < k:
        raise ValueError("K must fit the scored set")
    return sum(labels[case] for case in ranked[:k]) / k


def recall_at_k(labels: Mapping[str, int], scores: Mapping[str, float], k: int) -> float:
    ranked = _ranked(labels, scores)
    positives = sum(labels.values())
    if k < 1 or len(ranked) < k or not positives:
        raise ValueError("invalid K or no positive labels")
    return sum(labels[case] for case in ranked[:k]) / positives


def coverage(eligible_case_ids: set[str], scored_case_ids: set[str]) -> float:
    if not eligible_case_ids or not scored_case_ids <= eligible_case_ids:
        raise ValueError("scored IDs must be a subset of eligible IDs")
    return len(scored_case_ids) / len(eligible_case_ids)


METRIC_INTERPRETATION = {
    "average_precision": "Mean precision at each positive rank across the full ranked development fold.",
    "precision_at_k": "Fraction of the top K scored development cases with positive development labels.",
    "recall_at_k": "Fraction of all positive development cases retrieved in the top K.",
    "coverage": "Fraction of eligible development cases with a finite prediction.",
}
