from __future__ import annotations

from dataclasses import replace

from drosophila_pd.workbench import CandidateSpec, StudySpec, build_confirmation_plan
from drosophila_pd.workbench.models import stable_hash


def _study() -> StudySpec:
    return StudySpec(
        name="confirmation fixture",
        hypothesis="a candidate changes the readout",
        falsifiable_prediction="the readout changes relative to control",
        assay="motor_flat_ground",
        primary_metric="path_speed",
        candidates=(
            CandidateSpec("candidate-a", "A"),
            CandidateSpec("candidate-b", "B"),
            CandidateSpec("control", "Control"),
        ),
        run_plan={
            "confirmation_seed_repetitions": 3,
            "sensitivity": {"controller.frequency_hz": [10, 12, 14]},
        },
    )


def _ranking(study: StudySpec) -> dict:
    report = {
        "report_path": ".workbench/study/ranking_report.json",
        "collection": {
            "status": "READY",
            "control_candidate_id": "control",
            "observations": [
                {"candidate_id": "candidate-a", "seed": seed, "value": 2.0, "control_value": 1.0}
                for seed in range(3)
            ],
        },
        "ranking": {
            "ranking_eligible": True,
            "policy": {"control_candidate_id": "control"},
            "ranked_candidates": [
                {"candidate_id": "candidate-a", "rank": 1, "status": "RANKED", "mean_delta": 1.0, "ci": {"lower": 1.0, "upper": 1.0}},
                {"candidate_id": "candidate-b", "rank": 2, "status": "RANKED", "mean_delta": 0.5, "ci": {"lower": 0.5, "upper": 0.5}},
            ],
        },
    }
    return report


def test_confirmation_plan_uses_fresh_seeds_and_declared_sensitivity() -> None:
    study = _study()
    ranking = _ranking(study)
    plan = build_confirmation_plan(
        study,
        ranking,
        {"decision": "approved", "ranking_report_hash": stable_hash(ranking)},
        top_k=2,
    )

    assert plan["status"] == "READY_FOR_SUBMISSION"
    assert plan["fresh_seeds"] == [3, 4, 5]
    assert set(plan["fresh_seeds"]).isdisjoint({0, 1, 2})
    assert len(plan["control_jobs"]) == 3
    assert [item["candidate_id"] for item in plan["candidates"]] == ["candidate-a", "candidate-b"]
    assert len(plan["candidates"][0]["confirmation_jobs"]) == 3
    assert plan["sensitivity"]["status"] == "DECLARED"
    assert plan["sensitivity"]["case_count"] == 3
    assert plan["sensitivity"]["cases"][1]["controller.frequency_hz"] == 12
    assert plan["provenance"]["ranking_report_hash"]


def test_confirmation_plan_blocks_unapproved_or_missing_sensitivity() -> None:
    study = _study()
    study_without_sensitivity = replace(study, run_plan={"confirmation_seed_repetitions": 3})
    plan = build_confirmation_plan(
        study_without_sensitivity,
        _ranking(study_without_sensitivity),
        {"decision": "pending"},
    )

    assert plan["status"] == "BLOCKED"
    assert plan["ready_for_submission"] is False
    assert "human_review_not_approved" in plan["blocked_reasons"]
    assert "sensitivity_grid_missing" in plan["blocked_reasons"]


def test_string_screening_seeds_require_explicit_nonoverlapping_fresh_seeds() -> None:
    study = _study()
    ranking = _ranking(study)
    ranking["collection"]["observations"] = [
        {"candidate_id": "candidate-a", "seed": "screen-a", "value": 2.0, "control_value": 1.0}
    ]
    approved = {"decision": "approved", "ranking_report_hash": stable_hash(ranking)}
    blocked = build_confirmation_plan(study, ranking, approved)
    assert "non_numeric_screening_seed_requires_explicit_new_seeds" in blocked["blocked_reasons"]

    valid = build_confirmation_plan(
        study,
        ranking,
        approved,
        explicit_seeds=["confirm-a", "confirm-b", "confirm-c"],
    )
    assert valid["status"] == "READY_FOR_SUBMISSION"

    overlap = build_confirmation_plan(
        study,
        ranking,
        approved,
        explicit_seeds=["screen-a", "confirm-b", "confirm-c"],
    )
    assert "explicit_new_seed_overlaps_screening_seed" in overlap["blocked_reasons"]


def test_confirmation_plan_blocks_backend_without_seed_contract() -> None:
    plan = build_confirmation_plan(
        _study(),
        _ranking(_study()),
        {"decision": "approved"},
        backend_name="neural_bridge",
        backend_seed_capable=False,
    )

    assert plan["status"] == "BLOCKED"
    assert plan["backend"]["status"] == "BLOCKED"
    assert "backend_does_not_declare_explicit_seed_passthrough" in plan["blocked_reasons"]


def test_invalid_sensitivity_grid_is_blocked_without_being_repaired() -> None:
    plan = build_confirmation_plan(
        _study(),
        _ranking(_study()),
        {"decision": "approved"},
        sensitivity_grid=[{"parameter": "controller.x", "values": []}],
    )

    assert plan["status"] == "BLOCKED"
    assert plan["sensitivity"]["status"] == "INVALID"
    assert "sensitivity_grid_requires_nonempty_parameter_values" in plan["blocked_reasons"]
