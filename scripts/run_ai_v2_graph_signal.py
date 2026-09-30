"""Run the predeclared graph-signal comparison on the 74 DEV cases only."""

from __future__ import annotations

import csv
import hashlib
import json
import platform
import statistics
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

import numpy as np

from drosophila_pd.ai_v2.access import AccessClass, DevelopmentDataAccess
from drosophila_pd.ai_v2.cv import load_cv
from drosophila_pd.ai_v2.graph_data import build_graph_projection, load_development_cases, sha256_path
from drosophila_pd.ai_v2.graph_models import fit_graphsage, fit_linear_baseline
from drosophila_pd.ai_v2.metrics import average_precision, coverage, precision_at_k, recall_at_k


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs/ai_v2/graphsage_dev_search_v1.json"
CONFIG_SHA256 = "55909e29f6f876407965e50f1be9b2cb61cf6e4da86624c3c9041f4c909ca137"
FOLD_SHA256 = "6b054c6ff0a6669cb6038b0cd365a6787f5fa5f2d0e5018094badd6cce256dab"
SYSTEMS = ("B0_effect", "B1_structural", "B2_effect_structural", "B3_graphsage", "B4_effect_graphsage")


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def _save_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def _summarize(values: list[float]) -> dict[str, float]:
    return {"mean": statistics.mean(values), "std": statistics.stdev(values) if len(values) > 1 else 0.0, "median": statistics.median(values)}


def _decision(rows: list[dict[str, object]]) -> str:
    by_system = {system: [row for row in rows if row["system"] == system] for system in SYSTEMS}
    means = {system: statistics.mean(row["average_precision"] for row in cases) for system, cases in by_system.items()}
    b0 = {row["fold"]: row for row in by_system["B0_effect"]}
    b4 = by_system["B4_effect_graphsage"]
    b4_p5 = statistics.mean(row["precision_at_5"] for row in b4)
    b0_p5 = statistics.mean(row["precision_at_5"] for row in by_system["B0_effect"])
    supported = (
        means["B4_effect_graphsage"] - means["B0_effect"] >= 0.05
        and sum(row["average_precision"] > b0[row["fold"]]["average_precision"] for row in b4) >= 4
        and b4_p5 >= b0_p5
        and means["B4_effect_graphsage"] > means["B2_effect_structural"]
    )
    if supported:
        return "GRAPH_SIGNAL_SUPPORTED"
    if any(means[system] > means["B0_effect"] for system in SYSTEMS[1:]):
        return "GRAPH_SIGNAL_WEAK"
    return "GRAPH_SIGNAL_NOT_SUPPORTED"


def run() -> Path:
    if _git("branch", "--show-current") != "feature/ai-v2-dev":
        raise RuntimeError("AI V2 graph experiment requires feature/ai-v2-dev")
    if _git("diff", "--name-only", "b48edd0", "--", "configs/workbench/shiu_workbench_score_v1.json", "configs/workbench/comparator_lock_v1.json", "configs/workbench/shiu_public_benchmark_v2.json"):
        raise RuntimeError("V1 scientific inputs changed")
    if sha256_path(CONFIG_PATH) != CONFIG_SHA256:
        raise RuntimeError("predeclared graph experiment config hash mismatch")
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    approved = json.loads((ROOT / "configs/ai_v2/approved_development_ids_v1.json").read_text(encoding="utf-8"))
    ids = tuple(approved["case_ids"])
    cv = load_cv(ROOT / "configs/ai_v2/development_cv_5fold_v1.json", frozenset(ids))
    ids = cv.case_ids
    if len(ids) != config["development_case_count"] or cv.membership_sha256 != FOLD_SHA256 or config["fold_membership_sha256"] != FOLD_SHA256:
        raise RuntimeError("development fold identity mismatch")
    if len(config["graphsage_candidates"]) != 1 or config["graph_setting"] != "TRANSDUCTIVE_STRUCTURE_LABEL_ISOLATED":
        raise RuntimeError("this runner accepts one fixed transductive GraphSAGE configuration")
    output = ROOT / "results/ai_v2_dev/graph_signal_v1"
    if output.exists():
        raise FileExistsError(f"output already exists: {output}")
    output.mkdir(parents=True)
    _save_json(output / "config.json", config)
    mapping_path = ROOT / config["mapping_source"]
    dev_path = Path(config["development_artifact"])
    graph_path = Path(config["graph_source"])
    access = DevelopmentDataAccess(
        {AccessClass.DEVELOPMENT_INPUT: mapping_path.parent, AccessClass.DEVELOPMENT_LABEL: dev_path.parent, AccessClass.PUBLIC_UNLABELED: graph_path.parent},
        {AccessClass.DEVELOPMENT_INPUT: frozenset({mapping_path}), AccessClass.DEVELOPMENT_LABEL: frozenset({dev_path}), AccessClass.PUBLIC_UNLABELED: frozenset({graph_path})},
        output / "access_audit.jsonl",
    )
    cases = load_development_cases(access, approved_ids=ids, development_path=dev_path, mapping_path=mapping_path, expected_development_sha256=config["development_artifact_sha256"], expected_mapping_sha256=config["mapping_source_sha256"])
    graph = build_graph_projection(access, connectivity_path=graph_path, expected_graph_sha256=config["graph_source_sha256"], cases=cases.graph_inputs())
    if graph.case_ids != cv.case_ids:
        raise RuntimeError("graph projection case order differs from fixed CV")
    _save_json(output / "graph_hashes.json", {"graph_source_sha256": graph.graph_source_sha256, "mapping_source_sha256": graph.mapping_source_sha256, "development_artifact_sha256": cases.development_artifact_sha256, "node_count": graph.node_count, "edge_count": graph.edge_count, "feature_dimension": int(graph.node_features.shape[-1]), "mapped_target_count": graph.mapped_target_count, "case_mapping_count": len(graph.case_ids), "graph_setting": config["graph_setting"]})
    import torch
    import sklearn
    import pyarrow
    _save_json(output / "environment.json", {"python": sys.version, "platform": platform.platform(), "numpy": np.__version__, "torch": torch.__version__, "sklearn": sklearn.__version__, "pyarrow": pyarrow.__version__, "source_commit": _git("rev-parse", "HEAD"), "worktree_state_at_start": "dirty" if _git("status", "--porcelain") else "clean"})
    fold_rows: list[dict[str, object]] = []
    prediction_rows: list[dict[str, object]] = []
    logs: list[dict[str, object]] = []
    fixed = config["graphsage_candidates"][0]
    structural = graph.structural_case_features.astype(np.float64)
    for fold_index, validation_cases in enumerate(cv.folds):
        train_cases, _ = cv.train_validation(fold_index)
        lookup = {case: index for index, case in enumerate(ids)}
        train = np.array([lookup[case] for case in train_cases], dtype=np.int64)
        validation = np.array([lookup[case] for case in validation_cases], dtype=np.int64)
        labels = cases.labels
        if len(set(train) & set(validation)) or len(train) + len(validation) != 74:
            raise RuntimeError("train/validation fold overlap")
        effect = cases.effect_scores
        effect_structural = np.column_stack((effect, structural))
        outputs = {}
        b0_start = perf_counter()
        outputs["B0_effect"] = (effect[validation], 0, 0.0, perf_counter() - b0_start, (), None)
        for system, features in (("B1_structural", structural), ("B2_effect_structural", effect_structural)):
            fitted = fit_linear_baseline(features, labels, train, validation, seed=fixed["seed"] + fold_index)
            outputs[system] = (fitted.validation_scores, fitted.parameter_count, fitted.training_seconds, fitted.inference_seconds, fitted.training_log, fitted.train_feature_mean)
        for system, include_effect in (("B3_graphsage", False), ("B4_effect_graphsage", True)):
            fitted = fit_graphsage(graph.node_features, graph.incoming_neighbor_mean, graph.target_mask, effect, labels, train, validation, include_effect=include_effect, hidden_dim=fixed["hidden_dim"], dropout=fixed["dropout"], learning_rate=fixed["learning_rate"], epochs=fixed["epochs"], weight_decay=fixed["weight_decay"], seed=fixed["seed"] + fold_index + int(include_effect) * 100)
            outputs[system] = (fitted.validation_scores, fitted.parameter_count, fitted.training_seconds, fitted.inference_seconds, fitted.training_log, fitted.train_feature_mean)
        for system, (values, parameters, train_s, infer_s, training_log, train_feature_mean) in outputs.items():
            label_map = {case: int(labels[lookup[case]]) for case in validation_cases}
            scores = {case: float(value) for case, value in zip(validation_cases, values)}
            row = {"fold": fold_index, "system": system, "average_precision": average_precision(label_map, scores), "precision_at_5": precision_at_k(label_map, scores, 5), "recall_at_5": recall_at_k(label_map, scores, 5), "coverage": coverage(set(validation_cases), set(scores)), "parameter_count": parameters, "training_seconds": train_s, "inference_seconds": infer_s, "train_feature_mean": train_feature_mean, "validation_labels_used_for_training": False, "peak_memory_bytes": None}
            if system != "B0_effect":
                from sklearn.metrics import roc_auc_score, average_precision_score
                row["auroc"] = float(roc_auc_score([label_map[c] for c in validation_cases], [scores[c] for c in validation_cases]))
                row["auprc"] = float(average_precision_score([label_map[c] for c in validation_cases], [scores[c] for c in validation_cases]))
            fold_rows.append(row)
            for case in validation_cases:
                prediction_rows.append({"fold": fold_index, "system": system, "case_id": case, "score": scores[case], "model_config_sha256": CONFIG_SHA256})
            for item in training_log:
                logs.append({"fold": fold_index, "system": system, **item})
    _save_json(output / "fold_metrics.json", fold_rows)
    _save_json(output / "fold_predictions.json", prediction_rows)
    with (output / "training_logs.jsonl").open("w", encoding="utf-8") as stream:
        for row in logs:
            stream.write(json.dumps(row, sort_keys=True) + "\n")
    summary = {system: {metric: _summarize([float(row[metric]) for row in fold_rows if row["system"] == system]) for metric in ("average_precision", "precision_at_5", "recall_at_5", "coverage")} for system in SYSTEMS}
    for system in SYSTEMS:
        summary[system]["delta_ap_vs_b0"] = summary[system]["average_precision"]["mean"] - summary["B0_effect"]["average_precision"]["mean"]
        summary[system]["delta_p5_vs_b0"] = summary[system]["precision_at_5"]["mean"] - summary["B0_effect"]["precision_at_5"]["mean"]
    decision = _decision(fold_rows)
    aggregate = {"status": "DEVELOPMENT_ONLY", "graph_setting": config["graph_setting"], "validation_labels_used_for_training": False, "fold_membership_sha256": cv.membership_sha256, "config_sha256": CONFIG_SHA256, "case_count": 74, "systems": summary, "graph_signal_decision": decision, "limitations": ["One connectome and a 74-case development set; no unseen-connectome generalization claim.", "Small positive counts in some validation folds make AP/P@5 unstable.", "Training time is wall-clock CPU time; peak native memory was not reliably measured."]}
    _save_json(output / "aggregate_summary.json", aggregate)
    with (output / "ablation_table.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(("system", "effect", "structural_graph", "graphsage", "ap_mean", "ap_std", "p5_mean", "p5_std", "recall5_mean", "recall5_std", "coverage_mean", "coverage_std", "delta_ap_vs_b0", "delta_p5_vs_b0"))
        for system in SYSTEMS:
            item = summary[system]
            writer.writerow((system, int(system in {"B0_effect", "B2_effect_structural", "B4_effect_graphsage"}), int(system in {"B1_structural", "B2_effect_structural"}), int(system in {"B3_graphsage", "B4_effect_graphsage"}), item["average_precision"]["mean"], item["average_precision"]["std"], item["precision_at_5"]["mean"], item["precision_at_5"]["std"], item["recall_at_5"]["mean"], item["recall_at_5"]["std"], item["coverage"]["mean"], item["coverage"]["std"], item["delta_ap_vs_b0"], item["delta_p5_vs_b0"]))
    artifact_hashes = {path.name: sha256_path(path) for path in sorted(output.iterdir()) if path.is_file()}
    _save_json(output / "experiment_manifest.json", {"experiment_id": "ai_v2_graph_signal_v1", "timestamp_utc": datetime.now(UTC).isoformat(), "source_commit": _git("rev-parse", "HEAD"), "development_split_sha256": cv.split_sha256, "fold_membership_sha256": cv.membership_sha256, "config_sha256": CONFIG_SHA256, "graph_source_sha256": graph.graph_source_sha256, "mapping_source_sha256": graph.mapping_source_sha256, "development_artifact_sha256": cases.development_artifact_sha256, "model_ids": list(SYSTEMS), "seed": fixed["seed"], "feature_set": config["node_features"] + ["effect_score"], "metrics_requested": ["average_precision", "precision_at_5", "recall_at_5", "coverage", "auroc", "auprc"], "output_hashes": artifact_hashes, "execution_partition": "DEVELOPMENT", "internal_heldout_executed": False, "external_validation_executed": False})
    return output


if __name__ == "__main__":
    result = run()
    print(json.dumps({"status": "DEVELOPMENT_ONLY_COMPLETE", "output": str(result), "config_sha256": CONFIG_SHA256}))
