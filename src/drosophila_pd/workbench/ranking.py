"""Guardrailed candidate ranking for a single study/assay/metric.

This module ranks computational observations only.  A seed is a computational
repeat, not a biological replicate, and the report keeps QC failures and
out-of-scope observations separate from candidates that were actually ranked.
"""

from __future__ import annotations

import math
import random
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from .models import WORKBENCH_SCOPE, jsonable


RANKING_VERSION = "paired-delta-bootstrap-2"
_DIRECTIONS = {"increase", "decrease", "any"}


@dataclass(frozen=True)
class RankingObservation:
    """One paired computational observation for one candidate and seed."""

    candidate_id: str
    assay: str
    primary_metric: str
    seed: str | int
    value: Any
    control_value: Any
    study_id: str | None = None
    qc_pass: bool = True
    qc_status: str = "PASS"
    expected_direction: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    parse_error: str | None = None

    def __post_init__(self) -> None:
        required = {
            "candidate_id": self.candidate_id,
            "assay": self.assay,
            "primary_metric": self.primary_metric,
        }
        missing = [name for name, value in required.items() if not str(value).strip()]
        if missing:
            raise ValueError(f"ranking observation fields are required: {', '.join(missing)}")
        direction = _normalize_direction(self.expected_direction)
        if direction is not None and direction not in _DIRECTIONS:
            raise ValueError(f"unsupported expected_direction: {direction}")
        object.__setattr__(self, "expected_direction", direction)
        object.__setattr__(self, "metadata", dict(self.metadata))

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "RankingObservation":
        if not isinstance(data, Mapping):
            raise TypeError("each ranking observation must be an object")
        if "seed" not in data:
            raise ValueError("ranking observation requires seed")

        parse_error: str | None = None
        value = data.get("value")
        control_value = data.get("control_value")
        try:
            value = float(value)
            control_value = float(control_value)
        except (TypeError, ValueError):
            parse_error = "value and control_value must be numeric"
            value = math.nan
            control_value = math.nan

        return cls(
            candidate_id=str(data["candidate_id"]),
            assay=str(data["assay"]),
            primary_metric=str(data["primary_metric"]),
            seed=data["seed"],
            value=value,
            control_value=control_value,
            study_id=None if data.get("study_id") is None else str(data["study_id"]),
            qc_pass=bool(data.get("qc_pass", True)),
            qc_status=str(data.get("qc_status", "PASS")),
            expected_direction=data.get("expected_direction"),
            metadata=dict(data.get("metadata", {})),
            parse_error=parse_error,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "assay": self.assay,
            "primary_metric": self.primary_metric,
            "seed": self.seed,
            "value": self.value,
            "control_value": self.control_value,
            "study_id": self.study_id,
            "qc_pass": self.qc_pass,
            "qc_status": self.qc_status,
            "expected_direction": self.expected_direction,
            "metadata": jsonable(self.metadata),
            "parse_error": self.parse_error,
        }


@dataclass(frozen=True)
class RankingPolicy:
    """Predeclared policy controlling whether a candidate may be ranked."""

    assay: str
    primary_metric: str
    study_id: str | None = None
    expected_direction: str | None = None
    minimum_pairs: int = 3
    bootstrap_samples: int = 1000
    ci_level: float = 0.95
    minimum_effect_threshold: float | None = None
    minimum_direction_stability: float = 0.8
    bootstrap_seed: int = 0
    control_candidate_id: str | None = None

    def __post_init__(self) -> None:
        if not self.assay.strip() or not self.primary_metric.strip():
            raise ValueError("assay and primary_metric are required")
        direction = _normalize_direction(self.expected_direction)
        if direction is not None and direction not in _DIRECTIONS:
            raise ValueError(f"unsupported expected_direction: {direction}")
        object.__setattr__(self, "expected_direction", direction)
        if self.minimum_pairs < 1:
            raise ValueError("minimum_pairs must be positive")
        if self.bootstrap_samples < 50:
            raise ValueError("bootstrap_samples must be at least 50")
        if not 0 < self.ci_level < 1:
            raise ValueError("ci_level must be between 0 and 1")
        if self.minimum_effect_threshold is not None:
            threshold = float(self.minimum_effect_threshold)
            if not math.isfinite(threshold) or threshold < 0:
                raise ValueError("minimum_effect_threshold must be finite and non-negative")
            object.__setattr__(self, "minimum_effect_threshold", threshold)
        if not 0 <= self.minimum_direction_stability <= 1:
            raise ValueError("minimum_direction_stability must be between 0 and 1")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RankingPolicy":
        return cls(
            assay=str(data["assay"]),
            primary_metric=str(data["primary_metric"]),
            study_id=None if data.get("study_id") is None else str(data["study_id"]),
            control_candidate_id=(
                None
                if data.get("control_candidate_id") is None
                else str(data["control_candidate_id"])
            ),
            expected_direction=data.get("expected_direction"),
            minimum_pairs=int(data.get("minimum_pairs", 3)),
            bootstrap_samples=int(data.get("bootstrap_samples", 1000)),
            ci_level=float(data.get("ci_level", 0.95)),
            minimum_effect_threshold=(
                None
                if data.get("minimum_effect_threshold") is None
                else float(data["minimum_effect_threshold"])
            ),
            minimum_direction_stability=float(data.get("minimum_direction_stability", 0.8)),
            bootstrap_seed=int(data.get("bootstrap_seed", 0)),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "assay": self.assay,
            "primary_metric": self.primary_metric,
            "study_id": self.study_id,
            "control_candidate_id": self.control_candidate_id,
            "expected_direction": self.expected_direction,
            "minimum_pairs": self.minimum_pairs,
            "bootstrap_samples": self.bootstrap_samples,
            "ci_level": self.ci_level,
            "minimum_effect_threshold": self.minimum_effect_threshold,
            "minimum_direction_stability": self.minimum_direction_stability,
            "bootstrap_seed": self.bootstrap_seed,
        }


def bootstrap_mean_ci(
    deltas: Iterable[float],
    *,
    samples: int,
    ci_level: float,
    seed: int,
) -> tuple[float, float]:
    """Return a deterministic percentile bootstrap CI for the paired mean."""

    values = [float(value) for value in deltas]
    if not values:
        raise ValueError("at least one delta is required")
    if any(not math.isfinite(value) for value in values):
        raise ValueError("bootstrap deltas must be finite")
    rng = random.Random(seed)
    means = [sum(rng.choice(values) for _ in values) / len(values) for _ in range(samples)]
    alpha = (1.0 - ci_level) / 2.0
    return _percentile(means, alpha), _percentile(means, 1.0 - alpha)


def rank_candidates(
    observations: Iterable[RankingObservation | Mapping[str, Any]],
    policy: RankingPolicy,
) -> dict[str, Any]:
    """Evaluate and rank candidates under one explicit study/assay policy.

    Only candidates with enough paired seeds, passing QC, a declared effect
    threshold, stable direction, and a bootstrap interval excluding zero are
    put in ``ranked_candidates``.  Everything else remains visible in a
    separate section with a reason; it is never treated as a negative result.
    """

    normalized = [
        item if isinstance(item, RankingObservation) else RankingObservation.from_mapping(item)
        for item in observations
    ]
    scope_ids = {item.study_id for item in normalized if item.study_id is not None}
    scope_warnings: list[str] = []
    if policy.study_id is None:
        if len(scope_ids) > 1:
            scope_warnings.append("observations contain multiple study_id values")
        elif not scope_ids:
            scope_warnings.append("study_id was not supplied; caller must ensure one study")
    expected_study = policy.study_id or (next(iter(scope_ids)) if len(scope_ids) == 1 else None)

    grouped: dict[str, list[RankingObservation]] = defaultdict(list)
    out_of_scope: list[dict[str, Any]] = []
    out_of_scope_candidates: set[str] = set()
    for item in normalized:
        reason = _scope_reason(item, policy, expected_study, scope_ids)
        if reason is not None:
            out_of_scope.append({"observation": item.as_dict(), "reason": reason})
            out_of_scope_candidates.add(item.candidate_id)
            continue
        grouped[item.candidate_id].append(item)

    candidate_results: list[dict[str, Any]] = []
    qc_failures: list[dict[str, Any]] = []
    for candidate_id in sorted(set(grouped) | out_of_scope_candidates):
        items = grouped.get(candidate_id, [])
        candidate_result, failures = _evaluate_candidate(candidate_id, items, policy)
        if candidate_id in out_of_scope_candidates:
            candidate_result = _out_of_scope_candidate(candidate_id, policy)
        candidate_results.append(candidate_result)
        qc_failures.extend(failures)

    ranked = [item for item in candidate_results if item["ranking_eligible"]]
    not_ranked = [item for item in candidate_results if not item["ranking_eligible"]]
    ranked.sort(key=lambda item: (-float(item["ranking_score"]), item["candidate_id"]))
    for index, item in enumerate(ranked, start=1):
        item["rank"] = index
    for item in not_ranked:
        item["rank"] = None

    eligible = bool(ranked)
    return {
        "ranking_version": RANKING_VERSION,
        "status": "RANKED" if eligible else "NOT_RANKED",
        "ranking_eligible": eligible,
        "policy": policy.as_dict(),
        "ranked_candidates": ranked,
        "not_ranked": not_ranked,
        "qc_failures": qc_failures,
        "out_of_scope": out_of_scope,
        "scope_warnings": scope_warnings,
        "scientific_scope": WORKBENCH_SCOPE,
        "notes": [
            "Paired seeds are computational repeats, not biological replicates.",
            "The bootstrap interval covers seed-to-seed computational variation only; it does not cover missing model mechanisms or wet-lab variation.",
            "A ranking is exploratory until the assay, threshold, and evidence bundle are reviewed by a researcher.",
        ],
    }


def _evaluate_candidate(
    candidate_id: str,
    items: list[RankingObservation],
    policy: RankingPolicy,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    failures: list[dict[str, Any]] = []
    seed_values: dict[str, RankingObservation] = {}
    duplicate_seed = False
    for item in items:
        seed_key = str(item.seed)
        if seed_key in seed_values:
            duplicate_seed = True
            failures.append({"candidate_id": candidate_id, "seed": item.seed, "reason": "duplicate_seed"})
        else:
            seed_values[seed_key] = item

    bad_items: list[tuple[RankingObservation, str]] = []
    for item in seed_values.values():
        reason = _qc_reason(item)
        if reason is not None:
            bad_items.append((item, reason))
            failures.append({"candidate_id": candidate_id, "seed": item.seed, "reason": reason})

    base = {
        "candidate_id": candidate_id,
        "assay": policy.assay,
        "primary_metric": policy.primary_metric,
        "paired_seed_count": 0,
        "seed_ids": [],
        "mean_delta": None,
        "effect_direction": None,
        "hypothesis_alignment": "NOT_EVALUATED",
        "ci": None,
        "direction_stability": None,
        "expected_direction": policy.expected_direction,
        "minimum_effect_threshold": policy.minimum_effect_threshold,
        "threshold_met": False,
        "ranking_score": 0.0,
        "ranking_eligible": False,
        "rank": None,
        "status": "INSUFFICIENT_EVIDENCE",
        "reason": None,
        "computational_seed_note": "Seeds are computational repeats, not biological replicates.",
    }
    if duplicate_seed:
        base.update(status="OUT_OF_SCOPE", reason="duplicate seed prevents an unambiguous paired comparison")
        return base, failures
    if bad_items:
        base.update(status="QC_FAIL", reason="one or more paired observations failed QC")
        return base, failures

    valid = list(seed_values.values())
    deltas = [float(item.value) - float(item.control_value) for item in valid]
    base["paired_seed_count"] = len(deltas)
    base["seed_ids"] = [item.seed for item in valid]
    if len(deltas) < policy.minimum_pairs:
        base.update(
            mean_delta=sum(deltas) / len(deltas) if deltas else None,
            status="INSUFFICIENT_EVIDENCE",
            reason=f"{len(deltas)} paired seeds is below minimum_pairs={policy.minimum_pairs}",
        )
        return base, failures

    mean_delta = sum(deltas) / len(deltas)
    ci_lower, ci_upper = bootstrap_mean_ci(
        deltas,
        samples=policy.bootstrap_samples,
        ci_level=policy.ci_level,
        seed=_candidate_seed(policy.bootstrap_seed, candidate_id),
    )
    effect_direction = _observed_direction(mean_delta)
    effective_direction = _effective_direction(policy, valid, mean_delta)
    stability = _direction_stability(deltas, effect_direction, mean_delta)
    hypothesis_alignment = _hypothesis_alignment(mean_delta, effective_direction)
    magnitude_met = _effect_magnitude_met(mean_delta, policy.minimum_effect_threshold)
    threshold_met = _threshold_met(mean_delta, ci_lower, ci_upper, effective_direction, policy)
    stable = stability is not None and stability >= policy.minimum_direction_stability
    has_nonzero_ci = ci_lower > 0 or ci_upper < 0
    eligible = (
        policy.minimum_effect_threshold is not None
        and threshold_met
        and stable
        and has_nonzero_ci
    )
    reason: str | None = None
    status = "RANKED" if eligible else "EXPLORATORY"
    if policy.minimum_effect_threshold is None:
        reason = "minimum_effect_threshold was not declared; exploratory only"
        status = "EXPLORATORY_NO_THRESHOLD"
    elif magnitude_met and hypothesis_alignment == "CONTRADICTORY" and stable and has_nonzero_ci:
        reason = "stable effect contradicts the declared expected direction"
        status = "CONTRADICTORY"
    elif not threshold_met:
        reason = "absolute mean effect is below the declared threshold"
    elif not stable:
        reason = "direction stability is below the declared minimum"
    elif not has_nonzero_ci:
        reason = "bootstrap CI crosses zero"
    base.update(
        mean_delta=mean_delta,
        effect_direction=effect_direction,
        hypothesis_alignment=hypothesis_alignment,
        ci={"level": policy.ci_level, "lower": ci_lower, "upper": ci_upper},
        direction_stability=stability,
        expected_direction=effective_direction,
        threshold_met=threshold_met,
        ranking_score=abs(mean_delta) / max(ci_upper - ci_lower, 1e-12),
        ranking_eligible=eligible,
        status=status,
        reason=reason,
    )
    return base, failures


def _out_of_scope_candidate(candidate_id: str, policy: RankingPolicy) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "assay": policy.assay,
        "primary_metric": policy.primary_metric,
        "paired_seed_count": 0,
        "seed_ids": [],
        "mean_delta": None,
        "effect_direction": None,
        "hypothesis_alignment": "NOT_EVALUATED",
        "ci": None,
        "direction_stability": None,
        "expected_direction": policy.expected_direction,
        "minimum_effect_threshold": policy.minimum_effect_threshold,
        "threshold_met": False,
        "ranking_score": 0.0,
        "ranking_eligible": False,
        "rank": None,
        "status": "OUT_OF_SCOPE",
        "reason": "one or more observations for this candidate are outside the ranking scope",
        "computational_seed_note": "Seeds are computational repeats, not biological replicates.",
    }


def _scope_reason(
    item: RankingObservation,
    policy: RankingPolicy,
    expected_study: str | None,
    scope_ids: set[str | None],
) -> str | None:
    if item.assay != policy.assay:
        return f"assay mismatch: expected {policy.assay!r}"
    if item.primary_metric != policy.primary_metric:
        return f"primary_metric mismatch: expected {policy.primary_metric!r}"
    if policy.study_id is not None and item.study_id != policy.study_id:
        return f"study_id mismatch: expected {policy.study_id!r}"
    if policy.study_id is None and len(scope_ids) > 1:
        return "multiple study_id values require an explicit policy.study_id"
    if policy.study_id is None and scope_ids and item.study_id is None:
        return "study_id is missing while other observations declare a study"
    if expected_study is not None and item.study_id not in {None, expected_study}:
        return f"study_id mismatch: expected {expected_study!r}"
    return None


def _qc_reason(item: RankingObservation) -> str | None:
    if item.parse_error:
        return item.parse_error
    if not item.qc_pass or str(item.qc_status).upper() not in {"PASS", "PASSED", "OK"}:
        return f"qc_status={item.qc_status!r}"
    try:
        value = float(item.value)
        control = float(item.control_value)
    except (TypeError, ValueError):
        return "value and control_value must be numeric"
    if not math.isfinite(value) or not math.isfinite(control):
        return "value and control_value must be finite"
    return None


def _effective_direction(
    policy: RankingPolicy,
    items: list[RankingObservation],
    mean_delta: float,
) -> str:
    if policy.expected_direction is not None:
        return policy.expected_direction
    directions = {item.expected_direction for item in items if item.expected_direction is not None}
    if len(directions) == 1:
        return next(iter(directions))
    if mean_delta > 0:
        return "increase"
    if mean_delta < 0:
        return "decrease"
    return "any"


def _direction_stability(deltas: list[float], direction: str, mean_delta: float) -> float:
    if direction == "increase":
        return sum(delta > 0 for delta in deltas) / len(deltas)
    if direction == "decrease":
        return sum(delta < 0 for delta in deltas) / len(deltas)
    sign = 1 if mean_delta >= 0 else -1
    return sum((delta >= 0 if sign > 0 else delta <= 0) for delta in deltas) / len(deltas)


def _observed_direction(mean_delta: float) -> str:
    if mean_delta > 0:
        return "increase"
    if mean_delta < 0:
        return "decrease"
    return "null"


def _hypothesis_alignment(mean_delta: float, expected_direction: str) -> str:
    if expected_direction == "any":
        return "NOT_APPLICABLE"
    if mean_delta == 0:
        return "NULL"
    if expected_direction == "increase":
        return "CONSISTENT" if mean_delta > 0 else "CONTRADICTORY"
    if expected_direction == "decrease":
        return "CONSISTENT" if mean_delta < 0 else "CONTRADICTORY"
    return "NOT_EVALUATED"


def _effect_magnitude_met(mean_delta: float, threshold: float | None) -> bool:
    return threshold is not None and abs(mean_delta) >= threshold


def _threshold_met(
    mean_delta: float,
    ci_lower: float,
    ci_upper: float,
    direction: str,
    policy: RankingPolicy,
) -> bool:
    threshold = policy.minimum_effect_threshold
    if threshold is None:
        return False
    if direction == "increase":
        return mean_delta >= threshold
    if direction == "decrease":
        return mean_delta <= -threshold
    return abs(mean_delta) >= threshold


def _candidate_seed(base_seed: int, candidate_id: str) -> int:
    # A stable non-cryptographic seed avoids Python's process-randomized hash().
    return base_seed + sum((index + 1) * ord(char) for index, char in enumerate(candidate_id))


def _percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _normalize_direction(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    aliases = {"up": "increase", "down": "decrease", "either": "any", "": None}
    return aliases.get(normalized, normalized)


__all__ = [
    "RANKING_VERSION",
    "RankingObservation",
    "RankingPolicy",
    "bootstrap_mean_ci",
    "rank_candidates",
]
