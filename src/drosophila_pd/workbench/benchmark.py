"""Retrospective benchmark contracts for Workbench v0.1.

The evaluator consumes a frozen case list and externally supplied model
predictions. It never runs a simulation, changes model parameters, or treats a
retrospective public benchmark as prospective biological validation.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field, replace
from typing import Any, Mapping, Sequence

from .models import jsonable, stable_hash, utc_timestamp


BENCHMARK_LABELS = frozenset({"positive", "negative"})
DEFAULT_SENSITIVITY_METRICS = ("precision", "recall", "precision_at_k", "coverage")


@dataclass(frozen=True)
class RetrospectiveCase:
    case_id: str
    condition: str
    reference_label: str
    source: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.case_id.strip() or not self.condition.strip():
            raise ValueError("case_id and condition are required")
        label = str(self.reference_label).lower().strip()
        if label not in BENCHMARK_LABELS:
            raise ValueError(f"reference_label must be one of {sorted(BENCHMARK_LABELS)}")
        object.__setattr__(self, "reference_label", label)

    def as_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "condition": self.condition,
            "reference_label": self.reference_label,
            "source": jsonable(self.source),
            "metadata": jsonable(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RetrospectiveCase":
        return cls(
            case_id=str(data["case_id"]),
            condition=str(data.get("condition", data["case_id"])),
            reference_label=str(data["reference_label"]).lower(),
            source=dict(data.get("source", {})),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class BenchmarkProtocol:
    protocol_id: str
    source: Mapping[str, Any]
    selection_rule: str
    cases: tuple[RetrospectiveCase, ...]
    evaluation_contract: Mapping[str, Any] = field(default_factory=dict)
    frozen_at: str = ""
    min_case_count: int = 20
    precision_at_k: int = 3
    notes: tuple[str, ...] = ()
    development_case_ids: tuple[str, ...] = ()
    held_out_case_ids: tuple[str, ...] = ()
    split_metadata: Mapping[str, Any] = field(default_factory=dict)
    freeze_status: str = "DRAFT"
    label_policy: str = ""
    freeze_commit: str | None = None

    def __post_init__(self) -> None:
        if not self.protocol_id.strip() or not self.selection_rule.strip():
            raise ValueError("protocol_id and selection_rule are required")
        if self.min_case_count < 1:
            raise ValueError("min_case_count must be positive")
        if self.precision_at_k < 1:
            raise ValueError("precision_at_k must be positive")
        if len(self.cases) < self.min_case_count:
            raise ValueError(
                f"benchmark protocol requires at least {self.min_case_count} cases; got {len(self.cases)}"
            )
        normalized = tuple(
            case if isinstance(case, RetrospectiveCase) else RetrospectiveCase.from_dict(case)
            for case in self.cases
        )
        ids = [case.case_id for case in normalized]
        if len(ids) != len(set(ids)):
            raise ValueError("benchmark case_id values must be unique")
        labels = {case.reference_label for case in normalized}
        if labels != BENCHMARK_LABELS:
            raise ValueError("benchmark protocol must contain both positive and negative reference cases")
        object.__setattr__(self, "cases", normalized)
        object.__setattr__(self, "evaluation_contract", jsonable(self.evaluation_contract))
        object.__setattr__(self, "split_metadata", jsonable(self.split_metadata))
        object.__setattr__(self, "notes", tuple(str(item) for item in self.notes))
        case_ids = set(ids)
        development = tuple(str(value) for value in self.development_case_ids)
        held_out = tuple(str(value) for value in self.held_out_case_ids)
        if len(development) != len(set(development)) or len(held_out) != len(set(held_out)):
            raise ValueError("benchmark split case IDs must be unique")
        if set(development).intersection(held_out):
            raise ValueError("development and held-out benchmark splits must be disjoint")
        if set(development).union(held_out) - case_ids:
            raise ValueError("benchmark split contains an unknown case_id")
        status = str(self.freeze_status).upper().strip() or "DRAFT"
        if status not in {"DRAFT", "FROZEN"}:
            raise ValueError("freeze_status must be DRAFT or FROZEN")
        object.__setattr__(self, "development_case_ids", development)
        object.__setattr__(self, "held_out_case_ids", held_out)
        object.__setattr__(self, "freeze_status", status)
        object.__setattr__(self, "label_policy", str(self.label_policy).strip())

    @property
    def protocol_hash(self) -> str:
        return stable_hash(self.as_dict(include_hash=False))

    def as_dict(self, *, include_hash: bool = True) -> dict[str, Any]:
        payload = {
            "protocol_id": self.protocol_id,
            "source": jsonable(self.source),
            "selection_rule": self.selection_rule,
            "cases": [case.as_dict() for case in self.cases],
            "evaluation_contract": jsonable(self.evaluation_contract),
            "frozen_at": self.frozen_at,
            "min_case_count": self.min_case_count,
            "precision_at_k": self.precision_at_k,
            "notes": list(self.notes),
            "split": {
                "development_case_ids": list(self.development_case_ids),
                "held_out_case_ids": list(self.held_out_case_ids),
                "metadata": jsonable(self.split_metadata),
            },
            "freeze_status": self.freeze_status,
            "label_policy": self.label_policy,
            "freeze_commit": self.freeze_commit,
        }
        if include_hash:
            payload["protocol_hash"] = self.protocol_hash
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "BenchmarkProtocol":
        raw_split = data.get("split", {})
        split = raw_split if isinstance(raw_split, Mapping) else {}
        split_metadata = dict(split.get("metadata", {})) if isinstance(split.get("metadata", {}), Mapping) else {}
        split_metadata.update(
            {
                str(key): value
                for key, value in split.items()
                if str(key) not in {"development_case_ids", "held_out_case_ids", "metadata"}
            }
        )
        return cls(
            protocol_id=str(data["protocol_id"]),
            source=dict(data.get("source", {})),
            selection_rule=str(data["selection_rule"]),
            cases=tuple(RetrospectiveCase.from_dict(item) for item in data.get("cases", ())),
            evaluation_contract=dict(data.get("evaluation_contract", {})),
            frozen_at=str(data.get("frozen_at", "")),
            min_case_count=int(data.get("min_case_count", 20)),
            precision_at_k=int(data.get("precision_at_k", 3)),
            notes=tuple(data.get("notes", ())),
            development_case_ids=tuple(
                split.get("development_case_ids", ())
                if isinstance(split, Mapping)
                else ()
            ),
            held_out_case_ids=tuple(
                split.get("held_out_case_ids", ())
                if isinstance(split, Mapping)
                else ()
            ),
            split_metadata=split_metadata,
            freeze_status=str(data.get("freeze_status", "DRAFT")),
            label_policy=str(data.get("label_policy", "")),
            freeze_commit=None if data.get("freeze_commit") is None else str(data["freeze_commit"]),
        )

    def freeze_validation(self) -> dict[str, Any]:
        """Return explicit release-gate errors without changing the protocol."""

        errors: list[str] = []
        case_by_id = {case.case_id: case for case in self.cases}
        if self.freeze_status != "FROZEN":
            errors.append("benchmark_not_frozen")
        if not self.frozen_at.strip() or self.frozen_at.startswith("REPLACE_"):
            errors.append("freeze_timestamp_missing")
        if self.min_case_count < 20:
            errors.append("minimum_case_count_must_be_at_least_20")
        if len(self.cases) < max(20, self.min_case_count):
            errors.append("frozen_benchmark_has_fewer_than_20_cases")
        if not self.label_policy:
            errors.append("label_policy_missing")
        if not self.development_case_ids or not self.held_out_case_ids:
            errors.append("held_out_split_missing")
        if set(self.development_case_ids).union(self.held_out_case_ids) != set(case_by_id):
            errors.append("development_and_held_out_split_is_not_complete")
        for split_name, split_ids in (
            ("development", self.development_case_ids),
            ("held_out", self.held_out_case_ids),
        ):
            labels = {case_by_id[case_id].reference_label for case_id in split_ids if case_id in case_by_id}
            if labels != BENCHMARK_LABELS:
                errors.append(f"{split_name}_split_must_contain_positive_and_negative_cases")
        for case in self.cases:
            locator = case.source.get("locator") or case.source.get("doi") or case.source.get("url")
            if not locator:
                errors.append(f"case_source_locator_missing:{case.case_id}")
            if not case.source.get("label_basis"):
                errors.append(f"case_label_basis_missing:{case.case_id}")
        return {
            "status": "READY" if not errors else "BLOCKED",
            "errors": errors,
            "case_count": len(self.cases),
            "development_case_count": len(self.development_case_ids),
            "held_out_case_count": len(self.held_out_case_ids),
            "protocol_hash": self.protocol_hash,
        }


def freeze_benchmark_protocol(
    protocol: BenchmarkProtocol,
    *,
    development_case_ids: Sequence[str],
    held_out_case_ids: Sequence[str],
    frozen_at: str,
    label_policy: str,
    freeze_commit: str | None = None,
) -> BenchmarkProtocol:
    """Create a validated immutable benchmark snapshot.

    This function deliberately refuses to manufacture cases, labels, sources,
    or a split. The caller must provide the reviewed public case registry and
    the exact split that was selected before evaluation.
    """

    frozen = replace(
        protocol,
        development_case_ids=tuple(str(value) for value in development_case_ids),
        held_out_case_ids=tuple(str(value) for value in held_out_case_ids),
        frozen_at=str(frozen_at).strip(),
        freeze_status="FROZEN",
        label_policy=str(label_policy).strip(),
        freeze_commit=None if freeze_commit is None else str(freeze_commit).strip(),
    )
    validation = frozen.freeze_validation()
    if validation["status"] != "READY":
        raise ValueError("benchmark freeze is blocked: " + "; ".join(validation["errors"]))
    return frozen


@dataclass(frozen=True)
class BenchmarkPrediction:
    label: str | None
    score: float | None = None
    ranking_score: float | None = None
    assessable: bool = True
    reason: str | None = None

    @classmethod
    def from_value(cls, value: Any) -> "BenchmarkPrediction":
        if isinstance(value, Mapping):
            label = value.get("label")
            score = value.get("score")
            if score is not None:
                try:
                    score = float(score)
                except (TypeError, ValueError):
                    return cls(label=None, assessable=False, reason="score_not_numeric")
                if not math.isfinite(score):
                    return cls(label=None, assessable=False, reason="score_non_finite")
            ranking_score = value.get("ranking_score", score)
            if ranking_score is not None:
                try:
                    ranking_score = float(ranking_score)
                except (TypeError, ValueError):
                    return cls(label=None, assessable=False, reason="ranking_score_not_numeric")
                if not math.isfinite(ranking_score):
                    return cls(label=None, assessable=False, reason="ranking_score_non_finite")
            return cls(
                label=None if label is None else str(label).lower(),
                score=score,
                ranking_score=ranking_score,
                assessable=bool(value.get("assessable", label is not None)),
                reason=None if value.get("reason") is None else str(value["reason"]),
            )
        if value is None:
            return cls(label=None, assessable=False, reason="prediction_missing")
        return cls(label=str(value).lower())


def evaluate_retrospective_benchmark(
    protocol: BenchmarkProtocol,
    predictions: Mapping[str, Any],
    *,
    evaluation_split: str = "all",
    case_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Evaluate labels without counting unassessable cases as negatives.

    ``case_ids`` is an optional precomputed common denominator.  It is checked
    against the declared split so a caller cannot accidentally evaluate a
    held-out report with development cases or unknown IDs.
    """

    split = str(evaluation_split).strip().lower()
    if split not in {"all", "development", "held_out"}:
        raise ValueError("evaluation_split must be all, development, or held_out")
    if split == "development":
        split_ids = set(protocol.development_case_ids)
    elif split == "held_out":
        freeze_validation = protocol.freeze_validation()
        if freeze_validation["status"] != "READY":
            raise ValueError(
                "held-out benchmark evaluation requires a frozen, validated protocol: "
                + "; ".join(freeze_validation["errors"])
            )
        split_ids = set(protocol.held_out_case_ids)
    else:
        split_ids = {case.case_id for case in protocol.cases}
    selected_ids = split_ids if case_ids is None else {str(case_id) for case_id in case_ids}
    unknown_selected = selected_ids - split_ids
    if unknown_selected:
        raise ValueError(
            "case_ids must be a subset of the declared evaluation split: "
            + ", ".join(sorted(unknown_selected))
        )
    if not selected_ids:
        raise ValueError(f"benchmark has no {split} split")

    confusion = {"true_positive": 0, "true_negative": 0, "false_positive": 0, "false_negative": 0}
    evaluated: list[dict[str, Any]] = []
    unassessable: list[dict[str, Any]] = []
    warnings: list[str] = []
    for case in protocol.cases:
        if case.case_id not in selected_ids:
            continue
        prediction = BenchmarkPrediction.from_value(predictions.get(case.case_id))
        if not prediction.assessable or prediction.label not in BENCHMARK_LABELS:
            unassessable.append(
                {
                    "case_id": case.case_id,
                    "reference_label": case.reference_label,
                    "reason": prediction.reason or "prediction_unassessable",
                }
            )
            continue
        row = {
            "case_id": case.case_id,
            "reference_label": case.reference_label,
            "predicted_label": prediction.label,
            "score": prediction.score,
            "ranking_score": prediction.ranking_score if prediction.ranking_score is not None else prediction.score,
        }
        evaluated.append(row)
        if case.reference_label == "positive" and prediction.label == "positive":
            confusion["true_positive"] += 1
        elif case.reference_label == "negative" and prediction.label == "negative":
            confusion["true_negative"] += 1
        elif case.reference_label == "negative" and prediction.label == "positive":
            confusion["false_positive"] += 1
        else:
            confusion["false_negative"] += 1

    ranked = [row for row in evaluated if _finite(row.get("ranking_score", row.get("score")))]
    ranked.sort(key=lambda row: (-float(row.get("ranking_score", row["score"])), str(row["case_id"])))
    top_k = min(protocol.precision_at_k, len(ranked))
    top_rows = ranked[:top_k]
    top_positive = sum(row["reference_label"] == "positive" for row in top_rows)
    top_10_k = min(10, len(ranked))
    top_10_rows = ranked[:top_10_k]
    false_negatives = [row["case_id"] for row in evaluated if row["reference_label"] == "positive" and row["predicted_label"] == "negative"]
    selected_cases = [case for case in protocol.cases if case.case_id in selected_ids]
    positive_cases = sum(case.reference_label == "positive" for case in selected_cases)
    negative_cases = sum(case.reference_label == "negative" for case in selected_cases)
    evaluated_positive = sum(row["reference_label"] == "positive" for row in evaluated)
    evaluated_negative = sum(row["reference_label"] == "negative" for row in evaluated)
    total = len(selected_cases)
    assessed = len(evaluated)
    accuracy = _ratio(confusion["true_positive"] + confusion["true_negative"], assessed)
    precision = _ratio(confusion["true_positive"], confusion["true_positive"] + confusion["false_positive"])
    recall = _ratio(confusion["true_positive"], confusion["true_positive"] + confusion["false_negative"])
    ranked_positive_count = sum(row["reference_label"] == "positive" for row in ranked)
    average_precision = None
    if ranked_positive_count:
        precision_sum = 0.0
        seen_positive = 0
        for index, row in enumerate(ranked, start=1):
            if row["reference_label"] == "positive":
                seen_positive += 1
                precision_sum += seen_positive / index
        average_precision = precision_sum / ranked_positive_count
    try:
        bootstrap_samples = int(protocol.evaluation_contract.get("bootstrap_samples", 10000))
    except (TypeError, ValueError):
        bootstrap_samples = 10000
    bootstrap_samples = max(0, bootstrap_samples)
    bootstrap = bootstrap_rank_metrics(
        ranked,
        k=protocol.precision_at_k,
        samples=bootstrap_samples,
        seed=int(protocol.protocol_hash[:12], 16),
    )
    if assessed == 0:
        warnings.append("no assessable predictions were supplied")
    if len(ranked) < protocol.precision_at_k:
        warnings.append("fewer scored predictions than the declared precision@k")

    report = {
        "benchmark_version": 1,
        "status": "EVALUATED" if assessed else "NO_ASSESSABLE_CASES",
        "protocol": protocol.as_dict(),
        "protocol_hash": protocol.protocol_hash,
        "evaluation_contract": jsonable(protocol.evaluation_contract),
        "evaluation_split": split,
        "freeze_validation": protocol.freeze_validation(),
        "case_count": total,
        "assessable_case_count": assessed,
        "coverage": _ratio(assessed, total),
        "selected_case_ids": sorted(selected_ids),
        "class_balance": {"positive": positive_cases, "negative": negative_cases},
        "assessable_class_balance": {"positive": evaluated_positive, "negative": evaluated_negative},
        "confusion_matrix": confusion,
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "average_precision": average_precision,
        "ranked_case_count": len(ranked),
        "ranked_coverage": _ratio(len(ranked), assessed),
        "bootstrap": bootstrap,
        "precision_at_k": {
            "k_requested": protocol.precision_at_k,
            "k_used": top_k,
            "value": _ratio(top_positive, top_k),
            "case_ids": [row["case_id"] for row in top_rows],
        },
        "precision_at_10": {
            "k_used": top_10_k,
            "value": _ratio(
                sum(row["reference_label"] == "positive" for row in top_10_rows),
                top_10_k,
            ),
            "case_ids": [row["case_id"] for row in top_10_rows],
        },
        "false_negatives": false_negatives,
        "unassessable_cases": unassessable,
        "evaluated_cases": evaluated,
        "warnings": warnings,
        "scientific_scope": (
            "Retrospective public-data benchmark only. This does not establish "
            "prospective performance, biological validity, or wet-lab utility."
        ),
    }
    return report


def bootstrap_rank_metrics(
    ranked_rows: Sequence[Mapping[str, Any]],
    *,
    k: int,
    samples: int = 10000,
    seed: int = 0,
) -> dict[str, Any]:
    """Bootstrap ranking metrics over declared benchmark cases.

    The resampling unit is a benchmark case, not a fly or a simulation seed.
    Rows without finite ranking scores are excluded by the caller.  The result
    is descriptive uncertainty for retrospective ranking metrics and must not
    be interpreted as biological uncertainty.
    """

    rows = [dict(row) for row in ranked_rows]
    if k < 1:
        raise ValueError("k must be positive")
    if samples < 0:
        raise ValueError("samples must be non-negative")
    if not rows or samples == 0:
        return {"samples": samples, "status": "UNAVAILABLE", "precision_at_k": None, "average_precision": None}
    rng = random.Random(int(seed))
    precision_values: list[float] = []
    average_precision_values: list[float] = []
    for _ in range(samples):
        sample = []
        for draw_index in range(len(rows)):
            row = dict(rows[rng.randrange(len(rows))])
            row["case_id"] = f"{row.get('case_id', 'case')}#{draw_index}"
            sample.append(row)
        sample.sort(key=lambda row: (-float(row["ranking_score"]), str(row["case_id"])))
        top = sample[: min(k, len(sample))]
        precision_values.append(
            sum(row["reference_label"] == "positive" for row in top) / len(top)
            if top
            else 0.0
        )
        positive_count = sum(row["reference_label"] == "positive" for row in sample)
        if positive_count:
            seen = 0
            precision_sum = 0.0
            for index, row in enumerate(sample, start=1):
                if row["reference_label"] == "positive":
                    seen += 1
                    precision_sum += seen / index
            average_precision_values.append(precision_sum / positive_count)

    return {
        "samples": samples,
        "status": "AVAILABLE",
        "seed": int(seed),
        "confidence_level": 0.95,
        "precision_at_k": _percentile_interval(precision_values),
        "average_precision": _percentile_interval(average_precision_values),
        "scientific_scope": "Case-level retrospective ranking uncertainty; not biological uncertainty.",
    }


def _percentile_interval(values: Sequence[float]) -> dict[str, float] | None:
    if not values:
        return None
    ordered = sorted(float(value) for value in values)
    return {
        "lower": ordered[max(0, int(round(0.025 * (len(ordered) - 1))))],
        "upper": ordered[min(len(ordered) - 1, int(round(0.975 * (len(ordered) - 1))))],
        "mean": sum(ordered) / len(ordered),
    }


def compare_benchmark_systems(
    protocol: BenchmarkProtocol,
    predictions_by_system: Mapping[str, Mapping[str, Any]],
    *,
    evaluation_split: str = "held_out",
) -> dict[str, Any]:
    """Evaluate Workbench and baselines on the same frozen split."""

    if not predictions_by_system:
        raise ValueError("at least one benchmark system is required")
    reports: dict[str, Any] = {}
    for name, predictions in predictions_by_system.items():
        system_name = str(name).strip()
        if not system_name:
            raise ValueError("benchmark system names must be non-empty")
        if not isinstance(predictions, Mapping):
            raise ValueError(f"predictions for {system_name!r} must be an object")
        reports[system_name] = evaluate_retrospective_benchmark(
            protocol,
            predictions,
            evaluation_split=evaluation_split,
        )
    declared_ids = (
        set(protocol.development_case_ids)
        if evaluation_split == "development"
        else set(protocol.held_out_case_ids)
        if evaluation_split == "held_out"
        else {case.case_id for case in protocol.cases}
    )
    assessable_sets = [
        {str(row["case_id"]) for row in report.get("evaluated_cases", [])}
        for report in reports.values()
    ]
    common_assessable = sorted(declared_ids.intersection(*assessable_sets)) if assessable_sets else []
    matched_reports: dict[str, Any] = {}
    if common_assessable:
        for name, predictions in predictions_by_system.items():
            matched_reports[name] = evaluate_retrospective_benchmark(
                protocol,
                predictions,
                evaluation_split=evaluation_split,
                case_ids=common_assessable,
            )
    else:
        matched_reports = {
            name: {
                "status": "NO_COMMON_ASSESSABLE_CASES",
                "case_count": 0,
                "assessable_case_count": 0,
            }
            for name in reports
        }
    return {
        "comparison_version": 2,
        "protocol_hash": protocol.protocol_hash,
        "evaluation_split": evaluation_split,
        "systems": reports,
        "metrics": {
            name: {
                "precision": report.get("precision"),
                "recall": report.get("recall"),
                "average_precision": report.get("average_precision"),
                "precision_at_k": report.get("precision_at_k", {}).get("value"),
                "precision_at_10": report.get("precision_at_10", {}).get("value"),
                "coverage": report.get("coverage"),
                "false_negative_count": len(report.get("false_negatives", [])),
            }
            for name, report in reports.items()
        },
        "matched_evaluation": {
            "status": "COMPLETE" if len(common_assessable) == len(declared_ids) else "PARTIAL",
            "declared_case_count": len(declared_ids),
            "held_out_case_count": len(declared_ids),
            "common_assessable_case_count": len(common_assessable),
            "common_assessable_case_ids": common_assessable,
            "systems": matched_reports,
            "metrics": {
                name: {
                    "precision": report.get("precision"),
                    "recall": report.get("recall"),
                    "average_precision": report.get("average_precision"),
                    "precision_at_k": report.get("precision_at_k", {}).get("value"),
                    "precision_at_10": report.get("precision_at_10", {}).get("value"),
                }
                for name, report in matched_reports.items()
            },
            "note": (
                "The common denominator is used for cross-system interpretation. "
                "It does not turn unassessable cases into negative outcomes."
            ),
        },
        "scientific_scope": (
            "Matched retrospective comparison on a declared public split; it does not establish "
            "prospective biological validity or wet-lab utility."
        ),
    }


def summarize_sensitivity(
    runs: Sequence[Mapping[str, Any]],
    *,
    metric_names: Sequence[str] = DEFAULT_SENSITIVITY_METRICS,
) -> dict[str, Any]:
    """Describe supplied sensitivity results without selecting a threshold."""

    if not runs:
        raise ValueError("at least one sensitivity result is required")
    metrics: dict[str, Any] = {}
    warnings: list[str] = []
    for name in metric_names:
        values = [float(row[name]) for row in runs if _finite(row.get(name))]
        if not values:
            metrics[name] = {"available": False, "values": []}
            warnings.append(f"no finite values for {name}")
            continue
        minimum = min(values)
        maximum = max(values)
        metrics[name] = {
            "available": True,
            "values": values,
            "minimum": minimum,
            "maximum": maximum,
            "range": round(maximum - minimum, 12),
            "mean": round(sum(values) / len(values), 12),
            "reference": values[0],
            "absolute_change_from_reference": maximum if len(values) == 1 else round(values[-1] - values[0], 12),
        }
    return {
        "sensitivity_version": 1,
        "status": "DESCRIPTIVE_ONLY",
        "run_count": len(runs),
        "metrics": metrics,
        "warnings": warnings,
        "note": (
            "No stability threshold was inferred. Declare an effect and stability "
            "threshold before using sensitivity results for prioritization."
        ),
        "scientific_scope": "Parameter/configuration sensitivity summary; not biological uncertainty quantification.",
    }


def _finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def _ratio(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator


__all__ = [
    "BENCHMARK_LABELS",
    "BenchmarkPrediction",
    "BenchmarkProtocol",
    "bootstrap_rank_metrics",
    "compare_benchmark_systems",
    "DEFAULT_SENSITIVITY_METRICS",
    "freeze_benchmark_protocol",
    "RetrospectiveCase",
    "evaluate_retrospective_benchmark",
    "summarize_sensitivity",
]
