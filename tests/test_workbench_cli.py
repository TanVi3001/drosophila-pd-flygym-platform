from __future__ import annotations

import json

from drosophila_pd.workbench.cli import main


def test_cli_benchmark_and_sensitivity_write_reports_without_ai_provider(tmp_path, capsys) -> None:
    protocol = {
        "protocol_id": "cli-fixture-v1",
        "source": {"status": "fixture_only"},
        "selection_rule": "two positive and two negative fixture cases",
        "min_case_count": 4,
        "precision_at_k": 2,
        "cases": [
            {"case_id": "p1", "condition": "p1", "reference_label": "positive"},
            {"case_id": "p2", "condition": "p2", "reference_label": "positive"},
            {"case_id": "n1", "condition": "n1", "reference_label": "negative"},
            {"case_id": "n2", "condition": "n2", "reference_label": "negative"},
        ],
    }
    protocol_path = tmp_path / "protocol.json"
    predictions_path = tmp_path / "predictions.json"
    benchmark_output = tmp_path / "benchmark_report.json"
    protocol_path.write_text(json.dumps(protocol), encoding="utf-8")
    predictions_path.write_text(
        json.dumps(
            {
                "p1": {"label": "positive", "score": 0.9},
                "p2": {"label": "negative", "score": 0.1},
                "n1": {"label": "negative", "score": 0.8},
                "n2": {"label": "positive", "score": 0.7},
            }
        ),
        encoding="utf-8",
    )

    assert main(["benchmark", "--protocol", str(protocol_path), "--predictions", str(predictions_path), "--output", str(benchmark_output)]) == 0
    assert json.loads(benchmark_output.read_text(encoding="utf-8"))["precision"] == 0.5
    capsys.readouterr()

    sensitivity_input = tmp_path / "sensitivity.json"
    sensitivity_output = tmp_path / "sensitivity_report.json"
    sensitivity_input.write_text(json.dumps({"runs": [{"precision": 0.5}, {"precision": 0.6}]}), encoding="utf-8")
    assert main(["sensitivity", "--runs", str(sensitivity_input), "--output", str(sensitivity_output)]) == 0
    assert json.loads(sensitivity_output.read_text(encoding="utf-8"))["status"] == "DESCRIPTIVE_ONLY"


def test_cli_rank_writes_guardrailed_report(tmp_path, capsys) -> None:
    observations_path = tmp_path / "observations.json"
    policy_path = tmp_path / "policy.json"
    output_path = tmp_path / "ranking.json"
    observations_path.write_text(
        json.dumps(
            {
                "observations": [
                    {
                        "study_id": "study-cli",
                        "candidate_id": "candidate-a",
                        "assay": "motor_flat_ground",
                        "primary_metric": "path_speed",
                        "seed": seed,
                        "value": 2.0,
                        "control_value": 1.0,
                        "expected_direction": "increase",
                    }
                    for seed in range(3)
                ]
            }
        ),
        encoding="utf-8",
    )
    policy_path.write_text(
        json.dumps(
            {
                "study_id": "study-cli",
                "assay": "motor_flat_ground",
                "primary_metric": "path_speed",
                "expected_direction": "increase",
                "minimum_pairs": 3,
                "bootstrap_samples": 100,
                "minimum_effect_threshold": 0.5,
            }
        ),
        encoding="utf-8",
    )

    assert main(["rank", "--observations", str(observations_path), "--policy", str(policy_path), "--output", str(output_path)]) == 0
    capsys.readouterr()
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["ranking_eligible"] is True
    assert report["ranked_candidates"][0]["candidate_id"] == "candidate-a"
