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


def test_cli_imports_only_traceable_review_pending_mapping_records(tmp_path, capsys) -> None:
    registry = tmp_path / "registry.json"
    registry.write_text(
        json.dumps(
            {
                "schema_version": "registry-v1",
                "mapping_records": [
                    {
                        "mapping_id": "exact-v1",
                        "version": "1",
                        "biological_target": "target-a",
                        "source_mapping_key": "target-a",
                        "mapping_status": "EXACT",
                        "backend": "lif_2024",
                        "id_namespace": "flywire_root_id",
                        "dataset_id": "flywire-630",
                        "intervention_type": "activation",
                        "target_ids": ["123"],
                        "sources": [{"citation": "paper", "locator": "Table 3"}],
                        "review_status": "PENDING_SCIENTIFIC_REVIEW",
                        "context": {"assay": "proboscis_extension"},
                    },
                    {
                        "mapping_id": "invalid-v1",
                        "mapping_status": "INVALID_SOURCE_ID_SET",
                        "target_ids": [],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    code = main(
        [
            "--db",
            str(tmp_path / "state.sqlite3"),
            "--artifacts",
            str(tmp_path / "artifacts"),
            "mapping-import",
            "--file",
            str(registry),
        ]
    )
    assert code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["imported_count"] == 1
    assert output["imported"][0]["review_status"] == "PENDING_SCIENTIFIC_REVIEW"
    assert output["imported"][0]["context"]["source_name_match"] == "EXACT"
    assert output["skipped"] == [{"mapping_id": "invalid-v1", "reason": "INVALID_SOURCE_ID_SET"}]


def test_cli_research_study_uses_support_gated_contract(tmp_path, capsys) -> None:
    study_file = tmp_path / "study.json"
    study_file.write_text(
        json.dumps(
            {
                "name": "research study",
                "hypothesis": "target activation changes MN9 rate",
                "falsifiable_prediction": "the rate differs from control",
                "assay": "sensory_mn9",
                "primary_metric": "mn9_rate",
                "backend": "lif_2024",
                "candidates": [
                    {"candidate_id": "control", "label": "control", "intervention": {"type": "none"}},
                    {"candidate_id": "target", "label": "target", "target": "cell-type", "intervention": {"type": "activation"}, "metadata": {"mapping_id": "mapping-v1"}},
                ],
                "controls": [{"id": "control", "role": "negative_control"}],
                "sources": [],
                "run_plan": {"seed_repetitions": 3},
            }
        ),
        encoding="utf-8",
    )

    code = main(
        [
            "--db",
            str(tmp_path / "state.sqlite3"),
            "--artifacts",
            str(tmp_path / "artifacts"),
            "create-research-study",
            "--file",
            str(study_file),
        ]
    )
    assert code == 0
    result = json.loads(capsys.readouterr().out)
    study = result["study"]
    assert study["metadata"]["workflow_contract"] == "support-gated-1"
    assert result["support_assessment"]["status"] == "OUT_OF_SCOPE"
