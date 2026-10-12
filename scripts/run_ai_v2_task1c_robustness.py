"""Run the preregistered Task 1C robustness evaluation on DEV-74 only."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import statistics
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

import numpy as np

from drosophila_pd.ai_v2.access import AccessClass, DevelopmentDataAccess
from drosophila_pd.ai_v2.cv import canonical_hash
from drosophila_pd.ai_v2.graph_data import GraphCaseInputs, build_graph_projection, sha256_path
from drosophila_pd.ai_v2.graph_models import fit_graphsage, fit_linear_baseline
from drosophila_pd.ai_v2.metrics import average_precision, coverage, precision_at_k, recall_at_k
from drosophila_pd.ai_v2.task1b_audit import load_sanitized_development_inputs
from drosophila_pd.ai_v2.task1c import (
    TASK1_CONFIG_SHA256,
    TASK1_FOLD_SHA256,
    TASK1C_FOLD_SHA256,
    decide_task1c,
    load_task1c_cv,
    load_task1c_development_labels,
    validate_fold_label_counts,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs/ai_v2/graphsage_dev_search_v1.json"
CV_PATH = ROOT / "configs/ai_v2/development_cv_stratified_5fold_v2.json"
APPROVED_IDS_PATH = ROOT / "configs/ai_v2/approved_development_ids_v1.json"
SANITIZED_MANIFEST_PATH = ROOT / "data/ai_v2_dev/sanitized_manifest_v1.json"
EFFECT_PATH = ROOT / "data/ai_v2_dev/development_effect_features_v1.json"
SANITIZED_MAPPING_PATH = ROOT / "data/ai_v2_dev/development_mapping_v1.json"
OLD_RUN = ROOT / "results/ai_v2_dev/graph_signal_v1"
OUTPUT_ROOT = ROOT / "results/ai_v2_dev"
OUTPUT = OUTPUT_ROOT / "task1c_robustness_v1"
SPEC_PATH = ROOT / "docs/ai_v2/task1c_robustness_experiment_spec.md"
SYSTEMS = ("B0_effect", "B1_structural", "B2_effect_structural", "B3_graphsage", "B4_effect_graphsage")


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def _summary(values: list[float]) -> dict[str, float]:
    return {
        "mean": statistics.mean(values),
        "sample_std": statistics.stdev(values) if len(values) > 1 else 0.0,
        "median": statistics.median(values),
    }


def _verify_original_effect_parity(effects: dict[str, float], approved_ids: set[str]) -> dict[str, object]:
    """Compare only label-free B0 predictions with sanitized DEV effect inputs."""
    manifest_path = OLD_RUN / "experiment_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("execution_partition") != "DEVELOPMENT" or manifest.get("internal_heldout_executed") is not False:
        raise ValueError("historical reference run is not a development-only artifact")
    if manifest.get("config_sha256") != TASK1_CONFIG_SHA256 or manifest.get("fold_membership_sha256") != TASK1_FOLD_SHA256:
        raise ValueError("historical reference run identity differs from frozen Task 1")
    for name, expected in manifest["output_hashes"].items():
        if sha256_path(OLD_RUN / name) != expected:
            raise ValueError("historical Task 1 output checksum mismatch")
    prediction_path = OLD_RUN / "fold_predictions.json"
    rows = json.loads(prediction_path.read_text(encoding="utf-8"))
    if any(set(row) != {"case_id", "fold", "model_config_sha256", "score", "system"} for row in rows):
        raise ValueError("historical prediction artifact contains an unexpected field")
    b0 = [row for row in rows if row["system"] == "B0_effect"]
    indexed = {row["case_id"]: float(row["score"]) for row in b0}
    if len(indexed) != 74 or set(indexed) != approved_ids or set(indexed) != set(effects):
        raise ValueError("historical B0 reference IDs differ from the approved development set")
    if any(indexed[case_id] != effects[case_id] for case_id in approved_ids):
        raise ValueError("B0 score parity failed against sanitized effect inputs")
    return {
        "status": "PASS",
        "case_count": 74,
        "comparison": "historical label-free B0 predictions vs sanitized development effect_hz",
        "all_scores_exact": True,
        "reference_config_sha256": manifest["config_sha256"],
        "reference_prediction_sha256": sha256_path(prediction_path),
    }


def _run() -> Path:
    if _git("branch", "--show-current") != "feature/ai-v2-dev":
        raise RuntimeError("Task 1C requires the isolated feature/ai-v2-dev branch")
    if _git("diff", "--name-only", "b48edd0", "--", "configs/workbench/shiu_workbench_score_v1.json", "configs/workbench/comparator_lock_v1.json", "configs/workbench/shiu_public_benchmark_v2.json"):
        raise RuntimeError("frozen V1 scientific inputs changed; refusing Task 1C")
    if _git("diff", "--name-only", "HEAD", "--", "docs/ai_v2/task1c_robustness_experiment_spec.md"):
        raise RuntimeError("Task 1C preregistration document changed in the worktree")
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite existing Task 1C output: {OUTPUT}")
    if sha256_path(CONFIG_PATH) != TASK1_CONFIG_SHA256:
        raise ValueError("Task 1 model/configuration hash differs from preregistration")

    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if config.get("development_case_count") != 74 or config.get("metric_k") != 5 or len(config.get("graphsage_candidates", [])) != 1:
        raise ValueError("Task 1C model settings differ from the fixed Task 1 configuration")
    approved = tuple(json.loads(APPROVED_IDS_PATH.read_text(encoding="utf-8"))["case_ids"])
    approved_set = frozenset(approved)
    cv = load_task1c_cv(CV_PATH, approved_ids=approved_set)
    dev_path = Path(config["development_artifact"])
    graph_path = Path(config["graph_source"])
    mapping_registry_path = ROOT / config["mapping_source"]
    if not dev_path.is_file() or not graph_path.is_file():
        raise FileNotFoundError("a preregistered development input or public connectivity input is unavailable")
    if not mapping_registry_path.is_file() or sha256_path(mapping_registry_path) != config["mapping_source_sha256"]:
        raise ValueError("mapping registry identity check failed")

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    start_dirty = bool(_git("status", "--porcelain"))
    fixed = config["graphsage_candidates"][0]
    with tempfile.TemporaryDirectory(prefix=".task1c-robustness-", dir=OUTPUT_ROOT) as temporary:
        staging = Path(temporary)
        access = DevelopmentDataAccess(
            {
                AccessClass.DEVELOPMENT_INPUT: ROOT / "data/ai_v2_dev",
                AccessClass.DEVELOPMENT_LABEL: dev_path.parent,
                AccessClass.PUBLIC_UNLABELED: graph_path.parent,
            },
            {
                AccessClass.DEVELOPMENT_INPUT: frozenset({SANITIZED_MANIFEST_PATH, EFFECT_PATH, SANITIZED_MAPPING_PATH}),
                AccessClass.DEVELOPMENT_LABEL: frozenset({dev_path}),
                AccessClass.PUBLIC_UNLABELED: frozenset({graph_path}),
            },
            staging / "access_audit.jsonl",
        )
        effects_payload, mapping_payload = load_sanitized_development_inputs(
            access,
            approved_ids=tuple(sorted(approved_set)),
            manifest_path=SANITIZED_MANIFEST_PATH,
            effect_path=EFFECT_PATH,
            mapping_path=SANITIZED_MAPPING_PATH,
        )
        effects = {row["case_id"]: float(row["effect_hz"]) for row in effects_payload["features"]}
        mapping_by_id = {row["case_id"]: row for row in mapping_payload["mappings"]}
        if any(row.get("technical_state") != "TECHNICAL_EXACT_MATCH" for row in mapping_by_id.values()):
            raise ValueError("Task 1C requires the exact technical mapping set frozen for Task 1")
        if any(row.get("review_state") != "REQUIRES_SCIENTIFIC_REVIEW" for row in mapping_by_id.values()):
            raise ValueError("unexpected mapping review state; do not silently change biological mappings")
        target_ids = tuple(tuple(int(value) for value in mapping_by_id[case]["target_ids"]) for case in cv.case_ids)
        graph_cases = GraphCaseInputs(cv.case_ids, target_ids, config["mapping_source_sha256"])

        labels = load_task1c_development_labels(
            access,
            path=dev_path,
            expected_sha256=config["development_artifact_sha256"],
            approved_ids=approved_set,
        )
        fold_counts = validate_fold_label_counts(cv, labels)
        registered_counts = json.loads(CV_PATH.read_text(encoding="utf-8"))["fold_class_counts"]
        if fold_counts != [
            {key: row[key] for key in ("fold", "case_count", "positive_count", "negative_count")}
            for row in registered_counts
        ]:
            raise ValueError("observed development class counts differ from the frozen fold manifest")

        parity = _verify_original_effect_parity(effects, set(approved_set))
        graph = build_graph_projection(
            access,
            connectivity_path=graph_path,
            expected_graph_sha256=config["graph_source_sha256"],
            cases=graph_cases,
        )
        if graph.case_ids != cv.case_ids:
            raise ValueError("graph projection order differs from the preregistered folds")

        label_array = np.asarray([labels.values[case] for case in cv.case_ids], dtype=np.int8)
        effect_array = np.asarray([effects[case] for case in cv.case_ids], dtype=np.float64)
        structural = graph.structural_case_features.astype(np.float64)
        index_by_id = {case: index for index, case in enumerate(cv.case_ids)}
        fold_rows: list[dict[str, object]] = []
        prediction_rows: list[dict[str, object]] = []
        training_rows: list[dict[str, object]] = []

        for fold_index, validation_cases in enumerate(cv.folds):
            train_cases, _ = cv.train_validation(fold_index)
            train_index = np.asarray([index_by_id[case] for case in train_cases], dtype=np.int64)
            validation_index = np.asarray([index_by_id[case] for case in validation_cases], dtype=np.int64)
            if set(train_cases) & set(validation_cases) or len(train_cases) + len(validation_cases) != 74:
                raise ValueError("Task 1C train/validation fold overlap or omission")
            outcomes: dict[str, tuple[np.ndarray, int, float, float, tuple[dict[str, float], ...], tuple[float, ...] | None]] = {}
            start = perf_counter()
            outcomes["B0_effect"] = (effect_array[validation_index], 0, 0.0, perf_counter() - start, (), None)
            effect_structural = np.column_stack((effect_array, structural))
            for system, features in (("B1_structural", structural), ("B2_effect_structural", effect_structural)):
                fitted = fit_linear_baseline(features, label_array, train_index, validation_index, seed=fixed["seed"] + fold_index)
                outcomes[system] = (fitted.validation_scores, fitted.parameter_count, fitted.training_seconds, fitted.inference_seconds, fitted.training_log, fitted.train_feature_mean)
            for system, include_effect in (("B3_graphsage", False), ("B4_effect_graphsage", True)):
                fitted = fit_graphsage(
                    graph.node_features,
                    graph.incoming_neighbor_mean,
                    graph.target_mask,
                    effect_array,
                    label_array,
                    train_index,
                    validation_index,
                    include_effect=include_effect,
                    hidden_dim=fixed["hidden_dim"],
                    dropout=fixed["dropout"],
                    learning_rate=fixed["learning_rate"],
                    epochs=fixed["epochs"],
                    weight_decay=fixed["weight_decay"],
                    seed=fixed["seed"] + fold_index + int(include_effect) * 100,
                )
                outcomes[system] = (fitted.validation_scores, fitted.parameter_count, fitted.training_seconds, fitted.inference_seconds, fitted.training_log, fitted.train_feature_mean)

            for system, (scores_array, parameter_count, train_seconds, inference_seconds, train_log, train_mean) in outcomes.items():
                scores = {case: float(value) for case, value in zip(validation_cases, scores_array)}
                fold_labels = {case: int(labels.values[case]) for case in validation_cases}
                if set(scores) != set(validation_cases) or not np.isfinite(list(scores.values())).all():
                    raise ValueError("Task 1C produced missing or non-finite validation scores")
                row: dict[str, object] = {
                    "fold": fold_index,
                    "system": system,
                    "average_precision": average_precision(fold_labels, scores),
                    "precision_at_5": precision_at_k(fold_labels, scores, 5),
                    "recall_at_5": recall_at_k(fold_labels, scores, 5),
                    "coverage": coverage(set(validation_cases), set(scores)),
                    "parameter_count": parameter_count,
                    "training_seconds": train_seconds,
                    "inference_seconds": inference_seconds,
                    "train_feature_mean": train_mean,
                    "validation_labels_used_for_training": False,
                    "peak_memory_bytes": None,
                }
                if system != "B0_effect":
                    from sklearn.metrics import average_precision_score, roc_auc_score

                    row["auroc"] = float(roc_auc_score(list(fold_labels.values()), list(scores.values())))
                    row["auprc"] = float(average_precision_score(list(fold_labels.values()), list(scores.values())))
                fold_rows.append(row)
                for case_id in validation_cases:
                    prediction_rows.append({
                        "fold": fold_index,
                        "system": system,
                        "case_id": case_id,
                        "score": scores[case_id],
                        "model_config_sha256": TASK1_CONFIG_SHA256,
                        "fold_membership_sha256": TASK1C_FOLD_SHA256,
                    })
                for item in train_log:
                    training_rows.append({"fold": fold_index, "system": system, **item})

        metrics_summary: dict[str, object] = {}
        for system in SYSTEMS:
            rows = [row for row in fold_rows if row["system"] == system]
            metrics_summary[system] = {
                metric: _summary([float(row[metric]) for row in rows])
                for metric in ("average_precision", "precision_at_5", "recall_at_5", "coverage")
            }
            metrics_summary[system]["parameter_count"] = int(rows[0]["parameter_count"])
            metrics_summary[system]["mean_training_seconds"] = statistics.mean(float(row["training_seconds"]) for row in rows)
            metrics_summary[system]["mean_inference_seconds"] = statistics.mean(float(row["inference_seconds"]) for row in rows)
        decision = decide_task1c(fold_rows)
        label_hash = canonical_hash([[case, labels.values[case]] for case in sorted(labels.values)])
        mapping_review_summary = {
            "case_count": len(mapping_by_id),
            "all_mappings_pending_scientific_review": all(row["review_state"] == "REQUIRES_SCIENTIFIC_REVIEW" for row in mapping_by_id.values()),
            "unique_target_count": len({target for row in mapping_by_id.values() for target in row["target_ids"]}),
            "cases_with_shared_targets": sum(bool(row["shared_target_with_other_case_count"]) for row in mapping_by_id.values()),
        }
        summary = {
            "status": "DEVELOPMENT_ONLY_COMPLETE",
            "experiment_id": "ai_v2_task1c_robustness_v1",
            "partition": "DEVELOPMENT",
            "case_count": 74,
            "fold_count": 5,
            "fold_metrics_by_system": metrics_summary,
            "graph_signal_decision": decision,
            "effect_score_parity": parity,
            "fold_class_counts": fold_counts,
            "mapping_review_state": mapping_review_summary,
            "claim_boundary": "Does not establish independent replication, biological correctness, external generalization, or wet-lab utility.",
            "heldout_status": "LOCKED_NOT_RUN",
        }

        _write_json(staging / "config.json", config)
        _write_json(staging / "stratified_cv_manifest.json", json.loads(CV_PATH.read_text(encoding="utf-8")))
        _write_json(staging / "effect_parity_report.json", parity)
        _write_json(staging / "graph_hashes.json", {
            "graph_source_sha256": graph.graph_source_sha256,
            "mapping_registry_sha256": config["mapping_source_sha256"],
            "sanitized_mapping_sha256": sha256_path(SANITIZED_MAPPING_PATH),
            "sanitized_effect_sha256": sha256_path(EFFECT_PATH),
            "sanitized_manifest_sha256": sha256_path(SANITIZED_MANIFEST_PATH),
            "node_count": graph.node_count,
            "edge_count": graph.edge_count,
            "mapped_target_count": graph.mapped_target_count,
            "graph_setting": config["graph_setting"],
        })
        import pyarrow
        import sklearn
        import torch

        _write_json(staging / "environment.json", {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
            "torch": torch.__version__,
            "sklearn": sklearn.__version__,
            "pyarrow": pyarrow.__version__,
            "source_commit": _git("rev-parse", "HEAD"),
            "source_worktree_dirty_at_start": start_dirty,
        })
        _write_json(staging / "fold_metrics.json", fold_rows)
        _write_json(staging / "fold_predictions.json", prediction_rows)
        with (staging / "training_logs.jsonl").open("w", encoding="utf-8") as stream:
            for row in training_rows:
                stream.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")
        _write_json(staging / "summary.json", summary)
        _write_json(staging / "development_label_provenance.json", {
            "access_class": "DEVELOPMENT_LABEL",
            "source_file_sha256": config["development_artifact_sha256"],
            "development_label_vector_sha256": label_hash,
            "case_count": 74,
            "heldout_labels_accessed": False,
            "raw_labels_persisted": False,
        })
        source_files = [Path(__file__), ROOT / "src/drosophila_pd/ai_v2/task1c.py"]
        input_hashes = {
            "task1_model_config_sha256": TASK1_CONFIG_SHA256,
            "task1_original_fold_membership_sha256": TASK1_FOLD_SHA256,
            "task1c_fold_membership_sha256": TASK1C_FOLD_SHA256,
            "approved_development_ids_sha256": sha256_path(APPROVED_IDS_PATH),
            "stratified_cv_file_sha256": sha256_path(CV_PATH),
            "sanitized_manifest_sha256": sha256_path(SANITIZED_MANIFEST_PATH),
            "sanitized_effect_sha256": sha256_path(EFFECT_PATH),
            "sanitized_mapping_sha256": sha256_path(SANITIZED_MAPPING_PATH),
            "development_evaluator_sha256": config["development_artifact_sha256"],
            "task1c_preregistration_sha256": sha256_path(SPEC_PATH),
            "connectivity_sha256": graph.graph_source_sha256,
            "mapping_registry_sha256": config["mapping_source_sha256"],
            "development_label_vector_sha256": label_hash,
        }
        _write_json(staging / "input_manifest.json", input_hashes)
        output_hashes = {path.name: sha256_path(path) for path in sorted(staging.iterdir()) if path.is_file() and path.name != "experiment_manifest.json"}
        runner_hashes = {str(path.relative_to(ROOT)): sha256_path(path) for path in source_files}
        experiment_manifest = {
            "experiment_id": "ai_v2_task1c_robustness_v1",
            "timestamp_utc": datetime.now(UTC).isoformat(),
            "source_commit": _git("rev-parse", "HEAD"),
            "source_worktree_dirty_at_start": start_dirty,
            "runner_source_hashes": runner_hashes,
            "task1_config_sha256": TASK1_CONFIG_SHA256,
            "task1c_fold_membership_sha256": TASK1C_FOLD_SHA256,
            "task1c_preregistration_sha256": sha256_path(SPEC_PATH),
            "input_hashes": input_hashes,
            "output_hashes": output_hashes,
            "execution_partition": "DEVELOPMENT",
            "internal_heldout_executed": False,
            "external_validation_executed": False,
            "biological_validation_executed": False,
        }
        _write_json(staging / "experiment_manifest.json", experiment_manifest)
        os.replace(staging, OUTPUT)
    return OUTPUT


def main() -> int:
    output = _run()
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    print(json.dumps({
        "status": summary["status"],
        "output": str(output),
        "decision": summary["graph_signal_decision"]["decision"],
        "effect_parity_cases": summary["effect_score_parity"]["case_count"],
        "heldout_status": summary["heldout_status"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
