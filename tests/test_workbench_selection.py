from __future__ import annotations

from drosophila_pd.workbench.selection import SelectionPolicy, select_candidates


def _observations(candidate, deltas):
    return [
        {
            "study_id": "study-1",
            "candidate_id": candidate,
            "assay": "sensory_mn9",
            "primary_metric": "mn9_rate",
            "seed": seed,
            "value": 5.0 + delta,
            "control_value": 5.0,
            "expected_direction": "increase",
        }
        for seed, delta in enumerate(deltas)
    ]


def _support(*, blocked=()):
    return {
        "candidate_assessments": {
            candidate: {
                "status": "MAPPING_REVIEW_REQUIRED" if candidate in blocked else "SUPPORTED_COMPUTATIONALLY",
                "priority_eligible": candidate not in blocked,
            }
        for candidate in ("a", "b", "c", "z")
        }
    }


def test_select_candidates_respects_budget_and_uses_conservative_ci_score():
    observations = (
        _observations("a", (1, 1, 1, 1))
        + _observations("b", (2, 2, 2, 2))
        + _observations("c", (0.2, 0.2, 0.2, 0.2))
    )

    result = select_candidates(
        observations,
        _support(),
        SelectionPolicy(assay="sensory_mn9", primary_metric="mn9_rate", budget_k=2),
    )

    assert [candidate["candidate_id"] for candidate in result["selected"]] == ["b", "a"]
    assert result["budget"]["k"] == 2
    assert result["budget"]["used"] == 2
    assert result["status"] == "BUDGET_FILLED"
    assert result["selected"][0]["score_name"] == "lower_ci_bound_in_declared_direction"


def test_ineligible_candidate_is_excluded_and_budget_remains_unspent():
    observations = _observations("a", (2, 2, 2, 2)) + _observations("b", (1, 1, 1, 1))

    result = select_candidates(
        observations,
        _support(blocked=("a",)),
        SelectionPolicy(assay="sensory_mn9", primary_metric="mn9_rate", budget_k=3),
    )

    assert [candidate["candidate_id"] for candidate in result["selected"]] == ["b"]
    assert result["budget"]["used"] == 1
    assert result["budget"]["unspent"] == 2
    assert result["excluded"][0]["candidate_id"] == "a"
    assert result["excluded"][0]["reason"] == "mapping_review_required"


def test_selection_abstains_on_uncertain_effect_and_breaks_ties_by_id():
    observations = (
        _observations("z", (1, -1, 1, -1))
        + _observations("b", (1, 1, 1, 1))
        + _observations("a", (1, 1, 1, 1))
    )

    result = select_candidates(
        observations,
        _support(),
        SelectionPolicy(assay="sensory_mn9", primary_metric="mn9_rate", budget_k=3),
    )

    assert [candidate["candidate_id"] for candidate in result["selected"]] == ["a", "b"]
    assert result["status"] == "BUDGET_UNFILLED"
    assert any(item["candidate_id"] == "z" and item["reason"] == "effect_uncertain" for item in result["excluded"])


def test_selection_rejects_support_for_a_different_study_scope():
    policy = SelectionPolicy(assay="sensory_mn9", primary_metric="mn9_rate", budget_k=1, study_id="study-2")

    result = select_candidates(_observations("a", (1, 1, 1, 1)), _support(), policy)

    assert result["selected"] == []
    assert result["status"] == "NO_ELIGIBLE_CANDIDATES"


def test_selection_does_not_consume_reference_outcomes():
    observations = _observations("a", (1, 1, 1, 1))
    policy = SelectionPolicy(assay="sensory_mn9", primary_metric="mn9_rate", budget_k=1)
    without_outcomes = select_candidates(observations, _support(), policy)
    with_outcomes = select_candidates(
        [{**item, "reference_label": "positive", "held_out": True} for item in observations],
        _support(),
        policy,
    )

    assert with_outcomes["selected"] == without_outcomes["selected"]
    assert with_outcomes["report_hash"] == without_outcomes["report_hash"]
