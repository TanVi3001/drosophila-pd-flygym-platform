"""Label-blind representation diagnostics for the historical Task 1 graph view."""

from __future__ import annotations

import collections
from pathlib import Path

import numpy as np

from .graph_data import GraphProjection


def _distribution(values: np.ndarray) -> dict[str, float]:
    values = np.asarray(values, dtype=np.float64)
    return {"min": float(np.min(values)), "median": float(np.median(values)), "p95": float(np.percentile(values, 95)), "max": float(np.max(values))}


def _cross_fold_overlap(targets: tuple[tuple[int, ...], ...], ids: tuple[str, ...], folds: list[list[str]]) -> list[dict[str, int]]:
    by_id = {case: set(target) for case, target in zip(ids, targets)}
    if set(by_id) != set(case for fold in folds for case in fold):
        raise ValueError("folds must cover exactly the graph case IDs")
    answer = []
    for index, fold in enumerate(folds):
        validation = set(fold)
        training_targets = set().union(*(target for case, target in by_id.items() if case not in validation))
        answer.append({"fold": index, "validation_case_count": len(fold), "validation_cases_sharing_train_targets": sum(bool(by_id[case] & training_targets) for case in fold)})
    return answer


def _incoming_weight_concentration(graph_path: Path, wanted: list[int], batch_size: int = 1_000_000) -> dict[str, object]:
    import pyarrow.parquet as pq

    target_ids = np.array(wanted, dtype=np.int64)
    weight_sum = np.zeros(len(wanted), dtype=np.float64)
    weight_max = np.zeros(len(wanted), dtype=np.float64)
    incoming_count = np.zeros(len(wanted), dtype=np.int64)
    for batch in pq.ParquetFile(graph_path).iter_batches(batch_size=batch_size, columns=["Postsynaptic_ID", "Connectivity"]):
        dst = batch.column(0).to_numpy(zero_copy_only=False).astype(np.int64, copy=False)
        weight = batch.column(1).to_numpy(zero_copy_only=False).astype(np.float64, copy=False)
        position = np.searchsorted(target_ids, dst)
        matches = target_ids[np.minimum(position, len(target_ids) - 1)] == dst
        if matches.any():
            selected = position[matches]
            np.add.at(weight_sum, selected, weight[matches])
            np.maximum.at(weight_max, selected, weight[matches])
            np.add.at(incoming_count, selected, 1)
    fractions = np.divide(weight_max, weight_sum, out=np.zeros_like(weight_sum), where=weight_sum > 0)
    observed = fractions[weight_sum > 0]
    return {"mapped_targets_with_incoming_edges": int((incoming_count > 0).sum()), "mapped_targets_without_incoming_edges": int((incoming_count == 0).sum()), "top_single_edge_fraction_of_incoming_weight": _distribution(observed) if len(observed) else None, "fraction_targets_top_edge_over_half_incoming_weight": float((observed > 0.5).mean()) if len(observed) else None}


def audit_representation(graph: GraphProjection, original_folds: list[list[str]], stratified_folds: list[list[str]], *, graph_path: Path) -> dict[str, object]:
    target_count = np.array([len(target) for target in graph.target_ids], dtype=np.int64)
    shared_counts = collections.Counter(node for target in graph.target_ids for node in set(target))
    shared_ids = {node for node, count in shared_counts.items() if count > 1}
    target_features = {node: graph.node_features[case, index] for case, targets in enumerate(graph.target_ids) for index, node in enumerate(targets)}
    node_matrix = np.array([target_features[node] for node in sorted(target_features)], dtype=np.float64)
    case_self = np.asarray(graph.structural_case_features, dtype=np.float64)
    case_neighbor = (graph.incoming_neighbor_mean * graph.target_mask[:, :, None]).sum(axis=1) / graph.target_mask.sum(axis=1)[:, None]
    combined = np.concatenate((case_self, case_neighbor), axis=1)
    duplicate_pairs = 0
    near_duplicate_pairs = 0
    duplicate_cases: set[int] = set()
    for i in range(len(combined)):
        for j in range(i + 1, len(combined)):
            if np.array_equal(combined[i], combined[j]):
                duplicate_pairs += 1
                duplicate_cases.update((i, j))
            if np.max(np.abs(combined[i] - combined[j])) <= 1e-3:
                near_duplicate_pairs += 1
    multi_case_ranges = [np.ptp(graph.node_features[index, :count], axis=0) for index, count in enumerate(target_count) if count > 1]
    feature_names = ("log1p_in_degree", "log1p_out_degree", "log1p_in_strength", "log1p_out_strength")
    node_degree_values = np.expm1(node_matrix)
    return {
        "schema_version": "ai-v2-task1b-representation-audit-v1",
        "partition": "DEVELOPMENT",
        "labels_used": False,
        "case_count": len(graph.case_ids),
        "graph_source_sha256": graph.graph_source_sha256,
        "mapping_source_sha256": graph.mapping_source_sha256,
        "graph_node_count": graph.node_count,
        "graph_edge_count": graph.edge_count,
        "node_feature_dimension": int(graph.node_features.shape[-1]),
        "graphsage_input_dimension_per_target": int(graph.node_features.shape[-1] + graph.incoming_neighbor_mean.shape[-1]),
        "structural_case_feature_dimension": int(case_self.shape[-1]),
        "target_count_per_case": _distribution(target_count),
        "unique_mapped_target_neurons": len(shared_counts),
        "target_neurons_shared_across_cases": len(shared_ids),
        "cases_sharing_any_target": sum(bool(set(target) & shared_ids) for target in graph.target_ids),
        "fraction_cases_sharing_any_target": sum(bool(set(target) & shared_ids) for target in graph.target_ids) / len(graph.case_ids),
        "case_feature_variance": {name: float(np.var(case_self[:, index])) for index, name in enumerate(feature_names)},
        "case_neighbor_mean_feature_variance": {name: float(np.var(case_neighbor[:, index])) for index, name in enumerate(feature_names)},
        "near_zero_variance_threshold": 1e-8,
        "near_zero_variance_case_features": [name for index, name in enumerate(feature_names) if np.var(case_self[:, index]) < 1e-8],
        "identical_combined_input_pairs": duplicate_pairs,
        "cases_in_identical_input_pairs": len(duplicate_cases),
        "near_duplicate_combined_input_pairs_max_abs_1e_minus_3": near_duplicate_pairs,
        "multi_target_case_count": len(multi_case_ranges),
        "multi_target_cases_any_node_feature_range_gt_1_log_unit": sum(bool((row > 1).any()) for row in multi_case_ranges),
        "target_node_degree_strength_distribution": {name.replace("log1p_", ""): _distribution(node_degree_values[:, index]) for index, name in enumerate(feature_names)},
        "mapped_targets_total_degree_le_1": int(((node_degree_values[:, 0] + node_degree_values[:, 1]) <= 1.0001).sum()),
        "mapped_targets_zero_in_degree": int((node_degree_values[:, 0] < 0.0001).sum()),
        "mapped_targets_zero_out_degree": int((node_degree_values[:, 1] < 0.0001).sum()),
        "incoming_weight_concentration": _incoming_weight_concentration(graph_path, sorted(shared_counts)),
        "original_cv_cross_fold_target_overlap": _cross_fold_overlap(graph.target_ids, graph.case_ids, original_folds),
        "stratified_cv_cross_fold_target_overlap": _cross_fold_overlap(graph.target_ids, graph.case_ids, stratified_folds),
    }
