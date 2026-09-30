"""Synthetic-only tests for graph projection, fold fitting and decisions."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from drosophila_pd.ai_v2.access import AccessClass, DataAccessDenied, DevelopmentDataAccess
from drosophila_pd.ai_v2.graph_data import MappingReviewRequired, build_graph_projection, load_development_cases
from drosophila_pd.ai_v2.graph_models import fit_graphsage, fit_linear_baseline


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture(tmp_path: Path, *, ambiguous: bool = False):
    import pyarrow as pa
    import pyarrow.parquet as pq

    ids = tuple(f"DEV_{i:03d}" for i in range(74))
    dev = tmp_path / "dev.json"
    dev.write_text(json.dumps({"evaluation_split": "development", "comparison": {"systems": {"rewire_effect_only": {"evaluated_cases": [{"case_id": case, "reference_label": "positive" if i % 7 == 0 else "negative", "ranking_score": float(i)} for i, case in enumerate(ids)]}}}}), encoding="utf-8")
    mapping = tmp_path / "mapping.json"
    records = [{"case_id": case, "mapping_status": "AMBIGUOUS" if ambiguous and i == 0 else "EXACT", "invalid_source_ids": [], "target_ids": [1 + (i % 2)]} for i, case in enumerate(ids)]
    mapping.write_text(json.dumps({"mapping_records": records}), encoding="utf-8")
    graph = tmp_path / "graph.parquet"
    pq.write_table(pa.table({"Presynaptic_ID": [1, 2, 3, 3], "Postsynaptic_ID": [2, 1, 1, 2], "Connectivity": [4, 3, 2, 1]}), graph)
    roots = {AccessClass.DEVELOPMENT_LABEL: tmp_path, AccessClass.DEVELOPMENT_INPUT: tmp_path, AccessClass.PUBLIC_UNLABELED: tmp_path}
    allow = {AccessClass.DEVELOPMENT_LABEL: frozenset({dev}), AccessClass.DEVELOPMENT_INPUT: frozenset({mapping}), AccessClass.PUBLIC_UNLABELED: frozenset({graph})}
    return ids, dev, mapping, graph, DevelopmentDataAccess(roots, allow, tmp_path / "audit.jsonl")


def test_graph_projection_deterministic_and_mapping_review(tmp_path: Path) -> None:
    ids, dev, mapping, graph, access = _fixture(tmp_path)
    cases = load_development_cases(access, approved_ids=ids, development_path=dev, mapping_path=mapping, expected_development_sha256=_hash(dev), expected_mapping_sha256=_hash(mapping))
    assert cases.graph_inputs().__dict__.keys() == {"case_ids", "target_ids", "mapping_sha256"}
    first = build_graph_projection(access, connectivity_path=graph, expected_graph_sha256=_hash(graph), cases=cases.graph_inputs(), batch_size=2)
    second = build_graph_projection(access, connectivity_path=graph, expected_graph_sha256=_hash(graph), cases=cases.graph_inputs(), batch_size=3)
    assert first.node_count == 3 and first.edge_count == 4 and first.mapped_target_count == 2
    assert first.node_features.shape == (74, 1, 4)
    np.testing.assert_array_equal(first.node_features, second.node_features)
    np.testing.assert_array_equal(first.incoming_neighbor_mean, second.incoming_neighbor_mean)
    assert first.graph_source_sha256 == _hash(graph)
    with pytest.raises(ValueError):
        build_graph_projection(access, connectivity_path=graph, expected_graph_sha256="0" * 64, cases=cases.graph_inputs())
    with pytest.raises(DataAccessDenied):
        access.authorize_path(AccessClass.EXTERNAL_VALIDATION_LABEL, graph)
    with pytest.raises(DataAccessDenied):
        access.authorize_path(AccessClass.INTERNAL_HELDOUT_LABEL, graph)


def test_ambiguous_case_requires_review(tmp_path: Path) -> None:
    ids, dev, mapping, _, access = _fixture(tmp_path, ambiguous=True)
    with pytest.raises(MappingReviewRequired, match="REQUIRES_REVIEW"):
        load_development_cases(access, approved_ids=ids, development_path=dev, mapping_path=mapping, expected_development_sha256=_hash(dev), expected_mapping_sha256=_hash(mapping))


def test_train_only_scaler_ignores_validation_outlier() -> None:
    x = np.array([[0.0, 2.0], [1.0, 3.0], [2.0, 4.0], [3.0, 5.0], [1000.0, 2000.0], [999.0, 1999.0]])
    labels = np.array([0, 1, 0, 1, 0, 1])
    train = np.array([0, 1, 2, 3])
    validation = np.array([4, 5])
    fitted = fit_linear_baseline(x, labels, train, validation, seed=7)
    np.testing.assert_allclose(fitted.train_feature_mean, x[train].mean(axis=0))
    assert fitted.parameter_count == 3 and fitted.validation_scores.shape == (2,)


def test_graphsage_shape_and_fixed_seed_inference() -> None:
    n = 12
    self_x = np.arange(n * 2 * 4, dtype=np.float32).reshape(n, 2, 4) / 100
    neighbor_x = self_x / 2
    mask = np.ones((n, 2), dtype=np.float32)
    effect = np.arange(n, dtype=np.float64)
    labels = np.array([0, 1] * 6, dtype=np.int8)
    train = np.arange(10)
    validation = np.array([10, 11])
    options = dict(include_effect=True, hidden_dim=8, dropout=0.1, learning_rate=0.01, epochs=5, weight_decay=0.001, seed=5)
    one = fit_graphsage(self_x, neighbor_x, mask, effect, labels, train, validation, **options)
    two = fit_graphsage(self_x, neighbor_x, mask, effect, labels, train, validation, **options)
    assert one.validation_scores.shape == (2,) and one.parameter_count > 0
    np.testing.assert_array_equal(one.validation_scores, two.validation_scores)
    assert len(one.training_log) == 5
