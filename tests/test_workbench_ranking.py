from __future__ import annotations

from drosophila_pd.workbench import RankingPolicy, rank_candidates


def _observations(*, values=(1.4, 1.5, 1.6, 1.5), control=1.0, **overrides):
    return [
        {
            "study_id": "study-a",
            "candidate_id": "candidate-a",
            "assay": "motor_flat_ground",
            "primary_metric": "mean_planar_path_speed_mm_s",
            "seed": index,
            "value": value,
            "control_value": control,
            "qc_pass": True,
            "qc_status": "PASS",
            "expected_direction": "increase",
            **overrides,
        }
        for index, value in enumerate(values)
    ]


def _policy(**overrides) -> RankingPolicy:
    payload = {
        "study_id": "study-a",
        "assay": "motor_flat_ground",
        "primary_metric": "mean_planar_path_speed_mm_s",
        "expected_direction": "increase",
        "minimum_pairs": 3,
        "bootstrap_samples": 250,
        "minimum_effect_threshold": 0.2,
        "minimum_direction_stability": 0.75,
        "bootstrap_seed": 11,
    }
    payload.update(overrides)
    return RankingPolicy(**payload)


def test_paired_seed_bootstrap_ranks_only_eligible_candidate() -> None:
    report = rank_candidates(_observations(), _policy())

    assert report["status"] == "RANKED"
    assert report["ranking_eligible"] is True
    assert [item["candidate_id"] for item in report["ranked_candidates"]] == ["candidate-a"]
    result = report["ranked_candidates"][0]
    assert result["paired_seed_count"] == 4
    assert result["mean_delta"] == 0.5
    assert result["direction_stability"] == 1.0
    assert result["ci"]["lower"] > 0
    assert result["threshold_met"] is True
    assert result["rank"] == 1
    assert "biological replicates" in report["notes"][0]


def test_missing_effect_threshold_is_exploratory_not_a_negative_result() -> None:
    report = rank_candidates(_observations(), _policy(minimum_effect_threshold=None))

    assert report["status"] == "NOT_RANKED"
    assert report["ranked_candidates"] == []
    candidate = report["not_ranked"][0]
    assert candidate["status"] == "EXPLORATORY_NO_THRESHOLD"
    assert candidate["ranking_eligible"] is False
    assert "threshold" in candidate["reason"]


def test_qc_failure_and_metric_mismatch_stay_out_of_ranking() -> None:
    observations = _observations()
    observations[1]["qc_pass"] = False
    observations[1]["qc_status"] = "FAIL_ORIENTATION"
    observations.append({**_observations()[0], "seed": 99, "primary_metric": "wrong_metric"})

    report = rank_candidates(observations, _policy())

    assert report["ranking_eligible"] is False
    assert report["ranked_candidates"] == []
    assert report["not_ranked"][0]["status"] == "OUT_OF_SCOPE"
    assert report["qc_failures"][0]["reason"] == "qc_status='FAIL_ORIENTATION'"
    assert report["out_of_scope"][0]["reason"] == "primary_metric mismatch: expected 'mean_planar_path_speed_mm_s'"


def test_multiple_studies_require_explicit_scope() -> None:
    observations = _observations()
    observations.append({**_observations()[0], "candidate_id": "candidate-b", "seed": 0, "study_id": "study-b"})

    report = rank_candidates(observations, _policy(study_id=None))

    assert report["ranking_eligible"] is False
    assert report["scope_warnings"] == ["observations contain multiple study_id values"]
    assert len(report["out_of_scope"]) == len(observations)
    assert all(
        item["reason"] == "multiple study_id values require an explicit policy.study_id"
        for item in report["out_of_scope"]
    )


def test_duplicate_seed_is_not_silently_used_as_an_extra_pair() -> None:
    observations = _observations()
    observations.append({**observations[0], "value": 9.0})

    report = rank_candidates(observations, _policy())

    assert report["ranked_candidates"] == []
    assert report["not_ranked"][0]["status"] == "OUT_OF_SCOPE"
    assert report["not_ranked"][0]["paired_seed_count"] == 0
    assert report["qc_failures"][0]["reason"] == "duplicate_seed"


def test_missing_study_scope_is_not_combined_with_tagged_observations() -> None:
    observations = _observations()
    observations[0].pop("study_id")

    report = rank_candidates(observations, _policy(study_id=None))

    assert report["ranking_eligible"] is False
    assert report["out_of_scope"][0]["reason"] == "study_id is missing while other observations declare a study"


def test_stable_opposite_effect_is_reported_as_hypothesis_contradiction() -> None:
    report = rank_candidates(
        _observations(values=(-1.0, -1.1, -0.9, -1.0), control=1.0),
        _policy(minimum_effect_threshold=0.5),
    )

    candidate = report["not_ranked"][0]
    assert candidate["status"] == "CONTRADICTORY"
    assert candidate["effect_direction"] == "decrease"
    assert candidate["hypothesis_alignment"] == "CONTRADICTORY"
    assert candidate["direction_stability"] == 1.0
    assert "contradicts" in candidate["reason"]
