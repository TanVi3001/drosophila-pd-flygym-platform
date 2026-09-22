from __future__ import annotations

import numpy as np

from drosophila_pd.workbench import rewire_connectome_targets


def _inputs() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    return (
        np.array([1, 1, 2, 2, 3, 3], dtype=np.int64),
        np.array([10, 11, 11, 12, 10, 12], dtype=np.int64),
        np.array([0, 1, 1, 2, 0, 2], dtype=np.int64),
        np.array([1, 1, 1, 1, -1, -1], dtype=np.int64),
    )


def test_large_graph_rewire_preserves_degree_and_target_index_mapping() -> None:
    source, target, target_index, stratum = _inputs()
    result = rewire_connectome_targets(
        source,
        target,
        target_index,
        stratum,
        seed=19,
        swaps=2,
        max_attempts=1000,
    )

    assert result["status"] == "PASS"
    assert result["in_degree_preserved"] is True
    assert result["out_degree_preserved"] is True
    assert result["target_id_multiset_preserved"] is True
    assert result["output_self_loops"] == 0
    assert result["target_indices"].tolist() == [target_index[np.where(target == value)[0][0]] for value in result["target_ids"]]


def test_large_graph_rewire_is_deterministic_and_partial_is_visible() -> None:
    source, target, target_index, stratum = _inputs()
    first = rewire_connectome_targets(
        source, target, target_index, stratum, seed=7, swaps=2, max_attempts=100
    )
    second = rewire_connectome_targets(
        source, target, target_index, stratum, seed=7, swaps=2, max_attempts=100
    )
    assert first["status"] == "PASS"
    assert np.array_equal(first["target_ids"], second["target_ids"])
    partial = rewire_connectome_targets(
        source, target, target_index, stratum, seed=7, swaps=100, max_attempts=1
    )
    assert partial["status"] == "PARTIAL"
    assert partial["successful_swaps"] < partial["requested_swaps"]
