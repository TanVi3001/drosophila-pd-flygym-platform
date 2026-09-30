"""Deterministic, label-blind FlyWire graph projection for approved DEV cases."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .access import AccessClass, DevelopmentDataAccess


class MappingReviewRequired(ValueError):
    """An existing biological mapping is absent or ambiguous."""


def sha256_path(path: Path) -> str:
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


@dataclass(frozen=True)
class GraphCaseInputs:
    case_ids: tuple[str, ...]
    target_ids: tuple[tuple[int, ...], ...]
    mapping_sha256: str


@dataclass(frozen=True)
class DevelopmentCases:
    case_ids: tuple[str, ...]
    labels: np.ndarray
    effect_scores: np.ndarray
    target_ids: tuple[tuple[int, ...], ...]
    mapping_sha256: str
    development_artifact_sha256: str

    def graph_inputs(self) -> GraphCaseInputs:
        """Pass only unlabeled inputs to the graph adapter."""
        return GraphCaseInputs(self.case_ids, self.target_ids, self.mapping_sha256)


@dataclass(frozen=True)
class GraphProjection:
    case_ids: tuple[str, ...]
    target_ids: tuple[tuple[int, ...], ...]
    node_features: np.ndarray  # [case, max_targets, 4]
    incoming_neighbor_mean: np.ndarray  # same shape; one-layer GraphSAGE input
    target_mask: np.ndarray  # [case, max_targets]
    structural_case_features: np.ndarray  # [case, 4], mean target features
    graph_source_sha256: str
    mapping_source_sha256: str
    node_count: int
    edge_count: int
    mapped_target_count: int


def load_development_cases(
    access: DevelopmentDataAccess,
    *,
    approved_ids: tuple[str, ...],
    development_path: Path,
    mapping_path: Path,
    expected_development_sha256: str,
    expected_mapping_sha256: str,
) -> DevelopmentCases:
    if len(approved_ids) != 74 or len(set(approved_ids)) != 74:
        raise ValueError("approved development IDs must contain exactly 74 unique cases")
    if sha256_path(access.authorize_path(AccessClass.DEVELOPMENT_LABEL, development_path)) != expected_development_sha256:
        raise ValueError("development artifact hash mismatch")
    dev = json.loads(access.read_bytes(AccessClass.DEVELOPMENT_LABEL, development_path))
    rows = dev["comparison"]["systems"]["rewire_effect_only"]["evaluated_cases"]
    indexed = {row["case_id"]: row for row in rows}
    if len(rows) != 74 or len(indexed) != 74 or set(indexed) != set(approved_ids) or dev["evaluation_split"] != "development":
        raise ValueError("development evaluator rows do not match the approved partition")
    if sha256_path(access.authorize_path(AccessClass.DEVELOPMENT_INPUT, mapping_path)) != expected_mapping_sha256:
        raise ValueError("mapping source hash mismatch")
    mapping = json.loads(access.read_bytes(AccessClass.DEVELOPMENT_INPUT, mapping_path))
    records = {record["case_id"]: record for record in mapping["mapping_records"] if record["case_id"] in set(approved_ids)}
    if len(records) != 74:
        raise MappingReviewRequired("REQUIRES_REVIEW: incomplete mapping coverage")
    targets = []
    for case in approved_ids:
        record = records[case]
        ids = record["target_ids"]
        if record["mapping_status"] != "EXACT" or record["invalid_source_ids"] or not ids or len(ids) != len(set(ids)):
            raise MappingReviewRequired("REQUIRES_REVIEW: ambiguous or invalid target mapping")
        try:
            targets.append(tuple(int(value) for value in ids))
        except (TypeError, ValueError) as error:
            raise MappingReviewRequired("REQUIRES_REVIEW: nonnumeric target ID") from error
    labels = np.array([{"positive": 1, "negative": 0}[indexed[case]["reference_label"]] for case in approved_ids], dtype=np.int8)
    effects = np.array([float(indexed[case]["ranking_score"]) for case in approved_ids], dtype=np.float64)
    if not np.isfinite(effects).all():
        raise ValueError("nonfinite development effect score")
    return DevelopmentCases(approved_ids, labels, effects, tuple(targets), expected_mapping_sha256, expected_development_sha256)


def _add_grouped(stats: dict[int, list[float]], ids: np.ndarray, weights: np.ndarray, count_index: int, strength_index: int) -> None:
    unique, inverse = np.unique(ids, return_inverse=True)
    counts = np.bincount(inverse)
    strengths = np.bincount(inverse, weights=weights)
    for node, count, strength in zip(unique, counts, strengths):
        row = stats.setdefault(int(node), [0.0, 0.0, 0.0, 0.0])
        row[count_index] += float(count)
        row[strength_index] += float(strength)


def build_graph_projection(
    access: DevelopmentDataAccess,
    *,
    connectivity_path: Path,
    expected_graph_sha256: str,
    cases: GraphCaseInputs,
    batch_size: int = 1_000_000,
) -> GraphProjection:
    """Use full unlabeled topology; fit no statistics or model parameters here."""
    import pyarrow.parquet as pq

    graph_path = access.authorize_path(AccessClass.PUBLIC_UNLABELED, connectivity_path)
    if sha256_path(graph_path) != expected_graph_sha256:
        raise ValueError("graph source hash mismatch")
    parquet = pq.ParquetFile(graph_path)
    columns = ["Presynaptic_ID", "Postsynaptic_ID", "Connectivity"]
    if not set(columns) <= set(parquet.schema_arrow.names):
        raise ValueError("missing required connectivity columns")
    stats: dict[int, list[float]] = {}
    edge_count = 0
    for batch in parquet.iter_batches(batch_size=batch_size, columns=columns):
        src = batch.column(0).to_numpy(zero_copy_only=False).astype(np.int64, copy=False)
        dst = batch.column(1).to_numpy(zero_copy_only=False).astype(np.int64, copy=False)
        weights = batch.column(2).to_numpy(zero_copy_only=False).astype(np.float64, copy=False)
        if not np.isfinite(weights).all() or (weights < 0).any():
            raise ValueError("connectivity weights must be finite and nonnegative")
        _add_grouped(stats, dst, weights, 0, 2)
        _add_grouped(stats, src, weights, 1, 3)
        edge_count += len(src)
    wanted = sorted(set(node for target in cases.target_ids for node in target))
    missing = [node for node in wanted if node not in stats]
    if missing:
        raise MappingReviewRequired(f"REQUIRES_REVIEW: {len(missing)} mapped target IDs absent from connectivity graph")
    all_ids = np.array(sorted(stats), dtype=np.int64)
    all_features = np.log1p(np.array([stats[int(node)] for node in all_ids], dtype=np.float32))
    wanted_array = np.array(wanted, dtype=np.int64)
    neighbor_sum = np.zeros((len(wanted), 4), dtype=np.float64)
    neighbor_count = np.zeros(len(wanted), dtype=np.int64)
    for batch in parquet.iter_batches(batch_size=batch_size, columns=["Presynaptic_ID", "Postsynaptic_ID"]):
        src = batch.column(0).to_numpy(zero_copy_only=False).astype(np.int64, copy=False)
        dst = batch.column(1).to_numpy(zero_copy_only=False).astype(np.int64, copy=False)
        positions = np.searchsorted(wanted_array, dst)
        safe = np.minimum(positions, len(wanted_array) - 1)
        matched = wanted_array[safe] == dst
        if not matched.any():
            continue
        src_matched = src[matched]
        source_positions = np.searchsorted(all_ids, src_matched)
        if (source_positions >= len(all_ids)).any() or not np.array_equal(all_ids[source_positions], src_matched):
            raise ValueError("source node missing from graph statistics")
        np.add.at(neighbor_sum, positions[matched], all_features[source_positions])
        np.add.at(neighbor_count, positions[matched], 1)
    neighbor_mean = np.divide(neighbor_sum, neighbor_count[:, None], out=np.zeros_like(neighbor_sum), where=neighbor_count[:, None] > 0).astype(np.float32)
    target_positions = np.searchsorted(all_ids, wanted_array)
    target_features = all_features[target_positions]
    target_lookup = {node: index for index, node in enumerate(wanted)}
    max_targets = max(len(target) for target in cases.target_ids)
    self_tensor = np.zeros((len(cases.case_ids), max_targets, 4), dtype=np.float32)
    neighbor_tensor = np.zeros_like(self_tensor)
    mask = np.zeros((len(cases.case_ids), max_targets), dtype=np.float32)
    for case_index, target in enumerate(cases.target_ids):
        for node_index, node in enumerate(target):
            index = target_lookup[node]
            self_tensor[case_index, node_index] = target_features[index]
            neighbor_tensor[case_index, node_index] = neighbor_mean[index]
            mask[case_index, node_index] = 1.0
    structural = (self_tensor * mask[:, :, None]).sum(axis=1) / mask.sum(axis=1)[:, None]
    return GraphProjection(cases.case_ids, cases.target_ids, self_tensor, neighbor_tensor, mask, structural, expected_graph_sha256, cases.mapping_sha256, len(all_ids), edge_count, len(wanted))
