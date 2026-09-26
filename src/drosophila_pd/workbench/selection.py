"""Budget-aware, uncertainty-conscious selection for researcher review."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .models import stable_hash
from .ranking import RankingPolicy, rank_candidates


@dataclass(frozen=True)
class SelectionPolicy:
    assay: str
    primary_metric: str
    budget_k: int
    study_id: str | None = None
    control_candidate_id: str | None = None
    minimum_pairs: int = 3
    bootstrap_samples: int = 1000
    ci_level: float = 0.95
    minimum_direction_stability: float = 0.8
    bootstrap_seed: int = 0

    def __post_init__(self) -> None:
        if not self.assay.strip() or not self.primary_metric.strip():
            raise ValueError("assay and primary_metric are required")
        if self.budget_k < 1:
            raise ValueError("budget_k must be positive")
        if self.minimum_pairs < 2:
            raise ValueError("minimum_pairs must be at least two")
        if self.bootstrap_samples < 50:
            raise ValueError("bootstrap_samples must be at least 50")
        if not 0 < self.ci_level < 1:
            raise ValueError("ci_level must be between zero and one")
        if not 0 <= self.minimum_direction_stability <= 1:
            raise ValueError("minimum_direction_stability must be between zero and one")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SelectionPolicy":
        return cls(
            assay=str(value["assay"]),
            primary_metric=str(value["primary_metric"]),
            budget_k=int(value["budget_k"]),
            study_id=None if value.get("study_id") is None else str(value["study_id"]),
            control_candidate_id=None if value.get("control_candidate_id") is None else str(value["control_candidate_id"]),
            minimum_pairs=int(value.get("minimum_pairs", 3)),
            bootstrap_samples=int(value.get("bootstrap_samples", 1000)),
            ci_level=float(value.get("ci_level", 0.95)),
            minimum_direction_stability=float(value.get("minimum_direction_stability", 0.8)),
            bootstrap_seed=int(value.get("bootstrap_seed", 0)),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "policy_version": "evidence-context-lower-bound-1",
            "assay": self.assay,
            "primary_metric": self.primary_metric,
            "budget_k": self.budget_k,
            "study_id": self.study_id,
            "control_candidate_id": self.control_candidate_id,
            "minimum_pairs": self.minimum_pairs,
            "bootstrap_samples": self.bootstrap_samples,
            "ci_level": self.ci_level,
            "minimum_direction_stability": self.minimum_direction_stability,
            "bootstrap_seed": self.bootstrap_seed,
            "score": "lower_ci_bound_in_declared_direction",
            "support_requirement": "reviewed_mapping_and_matching_context",
        }


def select_candidates(
    observations: Sequence[Mapping[str, Any]],
    support_assessment: Mapping[str, Any],
    policy: SelectionPolicy,
) -> dict[str, Any]:
    """Select up to k eligible candidates, abstaining on support or uncertainty."""

    declared_study = support_assessment.get("study_id")
    wrong_scope = bool(policy.study_id and declared_study and policy.study_id != declared_study)
    candidate_support = support_assessment.get("candidate_assessments", {})
    supported_ids = {
        str(candidate_id)
        for candidate_id, assessment in candidate_support.items()
        if isinstance(assessment, Mapping)
        and assessment.get("priority_eligible") is True
        and assessment.get("status") in {"SUPPORTED_COMPUTATIONALLY", "SUPPORTED_BIOLOGICALLY"}
        and not wrong_scope
    }

    eligible_observations = [
        item
        for item in observations
        if str(item.get("candidate_id", "")) in supported_ids
        and str(item.get("candidate_id", "")) != policy.control_candidate_id
    ]
    ranking_policy = RankingPolicy(
        assay=policy.assay,
        primary_metric=policy.primary_metric,
        study_id=policy.study_id,
        minimum_pairs=policy.minimum_pairs,
        bootstrap_samples=policy.bootstrap_samples,
        ci_level=policy.ci_level,
        minimum_effect_threshold=0.0,
        minimum_direction_stability=policy.minimum_direction_stability,
        bootstrap_seed=policy.bootstrap_seed,
        control_candidate_id=policy.control_candidate_id,
    )
    ranked = rank_candidates(eligible_observations, ranking_policy)
    ranked_by_id = {
        str(item["candidate_id"]): item
        for item in ranked.get("ranked_candidates", ())
        if isinstance(item, Mapping)
    }
    all_seen = sorted({str(item.get("candidate_id", "")) for item in observations if item.get("candidate_id")})
    excluded: list[dict[str, Any]] = []
    for candidate_id in all_seen:
        if candidate_id == policy.control_candidate_id:
            continue
        if candidate_id not in supported_ids:
            source = candidate_support.get(candidate_id, {}) if isinstance(candidate_support, Mapping) else {}
            status = str(source.get("status", "SUPPORT_ASSESSMENT_REQUIRED")) if isinstance(source, Mapping) else "SUPPORT_ASSESSMENT_REQUIRED"
            reason = "support_assessment_scope_mismatch" if wrong_scope else status.lower()
            excluded.append({"candidate_id": candidate_id, "reason": reason, "support_status": status})
            continue
        if candidate_id not in ranked_by_id:
            candidate_report = next(
                (item for item in ranked.get("not_ranked", ()) if str(item.get("candidate_id")) == candidate_id),
                None,
            )
            if candidate_report is None:
                reason = "no_assessable_observations"
            elif not candidate_report.get("ci") or candidate_report.get("ci", {}).get("lower", 0) <= 0 <= candidate_report.get("ci", {}).get("upper", 0):
                reason = "effect_uncertain"
            else:
                reason = str(candidate_report.get("status", "not_ranked")).lower()
            excluded.append({"candidate_id": candidate_id, "reason": reason})

    selected = sorted(
        ranked_by_id.values(),
        key=lambda item: (-_directional_lower_bound(item), str(item["candidate_id"])),
    )[: policy.budget_k]
    for rank, item in enumerate(selected, start=1):
        item["selection_rank"] = rank
        item["score"] = _directional_lower_bound(item)
        item["score_name"] = "lower_ci_bound_in_declared_direction"

    result = {
        "schema_version": "budget-selection-report-1",
        "study_id": policy.study_id or declared_study,
        "support_assessment_hash": support_assessment.get("assessment_hash"),
        "policy": policy.as_dict(),
        "policy_hash": stable_hash(policy.as_dict()),
        "status": "NO_ELIGIBLE_CANDIDATES" if not selected else "BUDGET_FILLED" if len(selected) == policy.budget_k else "BUDGET_UNFILLED",
        "selected": selected,
        "excluded": excluded,
        "budget": {"k": policy.budget_k, "used": len(selected), "unspent": policy.budget_k - len(selected), "unit": "candidates"},
        "candidate_evaluation": ranked,
        "notes": [
            "The score is a computational lower confidence bound, not biological confidence.",
            "Candidates without a reviewed mapping and matching context are not prioritized.",
            "Unassessable, QC-failed, and uncertain candidates are not labeled biological negatives.",
        ],
    }
    result["report_hash"] = stable_hash(result)
    return result


def _directional_lower_bound(candidate: Mapping[str, Any]) -> float:
    ci = candidate.get("ci")
    if not isinstance(ci, Mapping):
        return 0.0
    lower, upper = float(ci["lower"]), float(ci["upper"])
    direction = str(candidate.get("expected_direction", "any"))
    if direction == "increase":
        return lower
    if direction == "decrease":
        return -upper
    if lower > 0:
        return lower
    if upper < 0:
        return -upper
    return 0.0


__all__ = ["SelectionPolicy", "select_candidates"]
