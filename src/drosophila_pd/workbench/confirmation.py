"""Confirmation campaign planning after a reviewed computational ranking.

The planner creates an auditable submission plan; it does not submit or run
jobs.  This distinction is deliberate because each backend must explicitly
document how a seed reaches the simulator before a confirmation run is valid.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .models import StudySpec, WORKBENCH_SCOPE, stable_hash


CONFIRMATION_PLAN_VERSION = "confirmation-plan-1"


def build_confirmation_plan(
    study: StudySpec,
    ranking_report: Mapping[str, Any],
    review: Mapping[str, Any],
    *,
    top_k: int = 3,
    explicit_seeds: Sequence[int | str] | None = None,
    sensitivity_grid: Any = None,
    backend_name: str | None = None,
    backend_seed_capable: bool | None = None,
    backend_parameter_override_capable: bool | None = None,
) -> dict[str, Any]:
    """Build a fresh-seed, sensitivity-aware plan from a reviewed ranking."""

    if top_k < 1:
        raise ValueError("top_k must be positive")
    blocked_reasons: list[str] = []
    ranking = ranking_report.get("ranking", {}) if isinstance(ranking_report, Mapping) else {}
    collection = ranking_report.get("collection", {}) if isinstance(ranking_report, Mapping) else {}
    policy = ranking.get("policy", {}) if isinstance(ranking, Mapping) else {}
    if not ranking_report:
        blocked_reasons.append("ranking_report_missing")
    if not isinstance(collection, Mapping) or collection.get("status") != "READY":
        blocked_reasons.append("ranking_collection_incomplete")
    if not isinstance(ranking, Mapping) or not ranking.get("ranking_eligible"):
        blocked_reasons.append("no_reviewed_ranking_eligible_candidate")
    if str(review.get("decision", "pending")) != "approved":
        blocked_reasons.append("human_review_not_approved")
    if ranking_report and review.get("ranking_report_hash") != stable_hash(ranking_report):
        blocked_reasons.append("human_review_not_bound_to_current_ranking")

    declared_sensitivity = sensitivity_grid
    if declared_sensitivity is None:
        declared_sensitivity = study.run_plan.get("sensitivity")
    if not declared_sensitivity:
        blocked_reasons.append("sensitivity_grid_missing")
    sensitivity_cases, sensitivity_error = _expand_sensitivity_grid(declared_sensitivity)
    if sensitivity_error is not None:
        blocked_reasons.append(sensitivity_error)

    ranked_candidates = ranking.get("ranked_candidates", ()) if isinstance(ranking, Mapping) else ()
    if not isinstance(ranked_candidates, Sequence) or isinstance(ranked_candidates, (str, bytes)):
        ranked_candidates = ()
    selected = [item for item in ranked_candidates[:top_k] if isinstance(item, Mapping)]
    if not selected:
        blocked_reasons.append("top_k_candidates_missing")

    control_candidate_id = None
    if isinstance(policy, Mapping):
        control_candidate_id = policy.get("control_candidate_id")
    if control_candidate_id is None and isinstance(collection, Mapping):
        control_candidate_id = collection.get("control_candidate_id")
    if not control_candidate_id:
        blocked_reasons.append("control_candidate_id_missing")
    if backend_seed_capable is False:
        blocked_reasons.append("backend_does_not_declare_explicit_seed_passthrough")
    if declared_sensitivity and backend_parameter_override_capable is False:
        blocked_reasons.append("backend_does_not_declare_parameter_override_passthrough")

    observed_seeds = _observed_seeds(collection)
    requested_repetitions = int(
        study.run_plan.get("confirmation_seed_repetitions", 30)
    )
    if requested_repetitions < 1:
        raise ValueError("confirmation_seed_repetitions must be positive")
    fresh_seeds, seed_error = _fresh_seeds(
        observed_seeds,
        requested_repetitions,
        explicit_seeds,
    )
    if seed_error is not None:
        blocked_reasons.append(seed_error)

    candidate_plans = [
        {
            "candidate_id": str(item.get("candidate_id")),
            "source_rank": item.get("rank"),
            "source_status": item.get("status"),
            "mean_delta": item.get("mean_delta"),
            "ci": item.get("ci"),
            "confirmation_jobs": [
                {
                    "phase": "confirmation",
                    "candidate_id": str(item.get("candidate_id")),
                    "control_candidate_id": str(control_candidate_id) if control_candidate_id else None,
                    "seed": seed,
                    "fresh_seed": True,
                    "source_rank": item.get("rank"),
                }
                for seed in fresh_seeds
            ],
        }
        for item in selected
    ]
    control_jobs = [
        {
            "phase": "confirmation_control",
            "candidate_id": str(control_candidate_id) if control_candidate_id else None,
            "seed": seed,
            "fresh_seed": True,
        }
        for seed in fresh_seeds
    ]
    status = "READY_FOR_SUBMISSION" if not blocked_reasons else "BLOCKED"
    return {
        "confirmation_plan_version": CONFIRMATION_PLAN_VERSION,
        "study_id": study.study_id,
        "status": status,
        "ready_for_submission": status == "READY_FOR_SUBMISSION",
        "blocked_reasons": sorted(set(blocked_reasons)),
        "top_k": top_k,
        "selected_candidate_count": len(candidate_plans),
        "control_candidate_id": control_candidate_id,
        "backend": {
            "name": backend_name,
            "supports_explicit_seed": backend_seed_capable,
            "supports_parameter_overrides": backend_parameter_override_capable,
            "status": (
                "PASS"
                if backend_seed_capable is True
                else "BLOCKED" if backend_seed_capable is False else "NOT_CHECKED"
            ),
        },
        "observed_seeds": observed_seeds,
        "fresh_seeds": fresh_seeds,
        "confirmation_seed_repetitions": requested_repetitions,
        "control_jobs": control_jobs,
        "candidates": candidate_plans,
        "sensitivity": {
            "declared": bool(declared_sensitivity),
            "grid": declared_sensitivity,
            "cases": sensitivity_cases,
            "case_count": len(sensitivity_cases),
            "status": (
                "DECLARED"
                if declared_sensitivity and sensitivity_error is None
                else "INVALID" if declared_sensitivity else "MISSING"
            ),
        },
        "provenance": {
            "study_configuration_hash": study.configuration_hash,
            "ranking_report_hash": stable_hash(ranking_report) if ranking_report else None,
            "ranking_report_path": ranking_report.get("report_path") if isinstance(ranking_report, Mapping) else None,
            "review_decision": review.get("decision", "pending"),
            "reviewed_at": review.get("reviewed_at"),
        },
        "notes": [
            "This is a submission plan only; it does not run simulations or claim biological confirmation.",
            "Fresh seeds are computational repeats and are not biological replicates.",
            "Every backend must prove that the planned seed reaches the simulator before execution is considered valid.",
        ],
        "scientific_scope": WORKBENCH_SCOPE,
    }


def _observed_seeds(collection: Mapping[str, Any]) -> list[int | str]:
    values: list[int | str] = []
    observations = collection.get("observations", ())
    if not isinstance(observations, Sequence) or isinstance(observations, (str, bytes)):
        return values
    for item in observations:
        if not isinstance(item, Mapping) or "seed" not in item:
            continue
        seed = item["seed"]
        if isinstance(seed, bool) or not isinstance(seed, (int, str)):
            continue
        if isinstance(seed, str) and not seed.strip():
            continue
        if str(seed) not in {str(value) for value in values}:
            values.append(seed)
    return values


def _fresh_seeds(
    observed: Sequence[int | str],
    requested: int,
    explicit: Sequence[int | str] | None,
) -> tuple[list[int | str], str | None]:
    observed_keys = {str(seed) for seed in observed}
    if explicit is not None:
        if not explicit:
            return [], "explicit_new_seeds_empty"
        seeds: list[int | str] = []
        for seed in explicit:
            if isinstance(seed, bool) or not isinstance(seed, (int, str)):
                return [], "explicit_new_seeds_invalid"
            if isinstance(seed, str) and not seed.strip():
                return [], "explicit_new_seeds_invalid"
            if str(seed) in observed_keys:
                return [], "explicit_new_seed_overlaps_screening_seed"
            if str(seed) in {str(value) for value in seeds}:
                return [], "explicit_new_seeds_contain_duplicates"
            seeds.append(seed)
        if len(seeds) != requested:
            return [], f"explicit_new_seed_count={len(seeds)} does not match requested={requested}"
        return seeds, None

    if not observed:
        return [], "screening_seeds_missing"
    if not all(isinstance(seed, int) and not isinstance(seed, bool) for seed in observed):
        return [], "non_numeric_screening_seed_requires_explicit_new_seeds"
    start = max(int(seed) for seed in observed) + 1
    seeds = list(range(start, start + requested))
    if any(str(seed) in observed_keys for seed in seeds):
        return [], "generated_confirmation_seed_overlaps_screening_seed"
    return seeds, None


def _expand_sensitivity_grid(grid: Any) -> tuple[list[dict[str, Any]], str | None]:
    """Expand an explicit one-or-more-parameter grid with a bounded case count."""

    if not grid:
        return [], None
    entries: list[tuple[str, list[Any]]] = []
    if isinstance(grid, Mapping):
        raw_entries = grid.items()
    elif isinstance(grid, Sequence) and not isinstance(grid, (str, bytes)):
        raw_entries = []
        for item in grid:
            if not isinstance(item, Mapping):
                return [], "sensitivity_grid_invalid_entry"
            if "parameter" not in item or "values" not in item:
                return [], "sensitivity_grid_requires_parameter_and_values"
            raw_entries.append((item["parameter"], item["values"]))
    else:
        return [], "sensitivity_grid_must_be_mapping_or_list"
    for parameter, values in raw_entries:
        name = str(parameter).strip()
        if not name or not isinstance(values, Sequence) or isinstance(values, (str, bytes)) or not values:
            return [], "sensitivity_grid_requires_nonempty_parameter_values"
        entries.append((name, list(values)))
    if not entries:
        return [], "sensitivity_grid_empty"

    cases: list[dict[str, Any]] = [{}]
    for parameter, values in entries:
        expanded: list[dict[str, Any]] = []
        for case in cases:
            for value in values:
                expanded.append({**case, parameter: value})
                if len(expanded) > 100:
                    return [], "sensitivity_grid_exceeds_100_cases"
        cases = expanded
    return cases, None


__all__ = ["CONFIRMATION_PLAN_VERSION", "build_confirmation_plan"]
