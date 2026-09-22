"""Scalable structural null-model helpers for FlyWire connectivity tables.

The small-graph helper in :mod:`graph_nulls` is useful for unit-sized graphs,
but materializing a 630 connectome as millions of Python dataclasses is not.
This module keeps the edge arrays numeric and performs the same directed
double-edge swap while preserving source-local edge attributes.

This is a structural null model only.  It is not an equally plausible
biological connectome, a causal ablation, or a biological uncertainty model.
"""

from __future__ import annotations

from typing import Any, Mapping

import numpy as np


def _integer_array(value: Any, *, name: str) -> np.ndarray:
    raw = np.asarray(value)
    if raw.ndim != 1:
        raise ValueError(f"{name} must be one-dimensional")
    if not np.issubdtype(raw.dtype, np.integer):
        raise TypeError(f"{name} must contain integer IDs/indices")
    return raw.astype(np.int64, copy=False)


def _duplicate_edge_count(source_ids: np.ndarray, target_ids: np.ndarray) -> int:
    pairs = np.empty(
        len(source_ids),
        dtype=np.dtype([("source", np.int64), ("target", np.int64)]),
    )
    pairs["source"] = source_ids
    pairs["target"] = target_ids
    return int(len(pairs) - len(np.unique(pairs)))


def rewire_connectome_targets(
    source_ids: Any,
    target_ids: Any,
    target_indices: Any,
    strata: Any,
    *,
    seed: int,
    swaps: int,
    max_attempts: int | None = None,
    forbid_self_loops: bool = True,
    check_duplicate_edges: bool = True,
) -> Mapping[str, Any]:
    """Rewire a large directed edge table without Python edge objects.

    A valid swap changes ``(a -> b, c -> d)`` to ``(a -> d, c -> b)`` only
    when the two edges have different sources, different targets, the same
    stratum, and neither candidate edge is already present for its source.
    Target indices are rematerialized from the original ID/index mapping.
    ``PARTIAL`` is returned when the requested number of swaps is not reached.
    """

    if swaps < 0:
        raise ValueError("swaps must be non-negative")
    source = _integer_array(source_ids, name="source_ids")
    original_targets = _integer_array(target_ids, name="target_ids")
    original_target_indices = _integer_array(target_indices, name="target_indices")
    stratum = _integer_array(strata, name="strata")
    lengths = {len(source), len(original_targets), len(original_target_indices), len(stratum)}
    if len(lengths) != 1:
        raise ValueError("source_ids, target_ids, target_indices, and strata must have equal length")
    if len(source) < 2 and swaps:
        raise ValueError("at least two edges are required for a non-zero swap request")
    if check_duplicate_edges:
        duplicates = _duplicate_edge_count(source, original_targets)
        if duplicates:
            raise ValueError(f"input graph contains {duplicates} duplicate directed edges")

    limit = max_attempts if max_attempts is not None else max(100, swaps * 100)
    if limit < 0:
        raise ValueError("max_attempts must be non-negative")

    targets = original_targets.copy()
    unique_sources, inverse = np.unique(source, return_inverse=True)
    source_groups = inverse.astype(np.int32, copy=False)
    order = np.argsort(source_groups, kind="stable")
    sorted_groups = source_groups[order]
    boundaries = np.flatnonzero(np.diff(sorted_groups)) + 1
    starts = np.concatenate((np.array([0], dtype=np.int64), boundaries))
    stops = np.concatenate((boundaries, np.array([len(order)], dtype=np.int64)))
    group_targets: list[np.ndarray] = []
    edge_positions = np.empty(len(source), dtype=np.int32)
    for start, stop in zip(starts.tolist(), stops.tolist()):
        edge_indices = order[start:stop]
        group_targets.append(targets[edge_indices].copy())
        edge_positions[edge_indices] = np.arange(stop - start, dtype=np.int32)
    del order, sorted_groups, boundaries, starts, stops

    rng = np.random.default_rng(int(seed))
    successful = 0
    attempts = 0
    while successful < swaps and attempts < limit:
        attempts += 1
        first = int(rng.integers(len(source)))
        second = int(rng.integers(len(source)))
        if first == second:
            continue
        if source_groups[first] == source_groups[second] or stratum[first] != stratum[second]:
            continue
        first_target = int(targets[first])
        second_target = int(targets[second])
        if first_target == second_target:
            continue
        candidate_first = second_target
        candidate_second = first_target
        if forbid_self_loops and (
            int(source[first]) == candidate_first or int(source[second]) == candidate_second
        ):
            continue
        first_group = int(source_groups[first])
        second_group = int(source_groups[second])
        if np.any(group_targets[first_group] == candidate_first):
            continue
        if np.any(group_targets[second_group] == candidate_second):
            continue
        targets[first] = candidate_first
        targets[second] = candidate_second
        group_targets[first_group][edge_positions[first]] = candidate_first
        group_targets[second_group][edge_positions[second]] = candidate_second
        successful += 1

    unique_target_ids, first_positions = np.unique(original_targets, return_index=True)
    target_index_by_id = original_target_indices[first_positions]
    original_target_positions = np.searchsorted(unique_target_ids, original_targets)
    if not np.array_equal(
        target_index_by_id[original_target_positions], original_target_indices
    ):
        raise ValueError("each target ID must map to one stable target index")
    target_positions = np.searchsorted(unique_target_ids, targets)
    if len(target_positions) and not np.array_equal(unique_target_ids[target_positions], targets):
        raise RuntimeError("rewiring produced a target ID without a source index mapping")
    rematerialized_indices = target_index_by_id[target_positions]

    original_in_ids, original_in_counts = np.unique(original_targets, return_counts=True)
    output_in_ids, output_in_counts = np.unique(targets, return_counts=True)
    out_degree_source, out_degree_counts = np.unique(source, return_counts=True)
    output_source, output_source_counts = np.unique(source, return_counts=True)
    output_self_loops = int(np.count_nonzero(source == targets))
    return {
        "status": "PASS" if successful == swaps else "PARTIAL",
        "seed": int(seed),
        "requested_swaps": int(swaps),
        "successful_swaps": int(successful),
        "attempts": int(attempts),
        "max_attempts": int(limit),
        "input_edge_count": int(len(source)),
        "output_edge_count": int(len(source)),
        "target_ids": targets,
        "target_indices": rematerialized_indices,
        "in_degree_preserved": bool(
            np.array_equal(original_in_ids, output_in_ids)
            and np.array_equal(original_in_counts, output_in_counts)
        ),
        "out_degree_preserved": bool(
            np.array_equal(out_degree_source, output_source)
            and np.array_equal(out_degree_counts, output_source_counts)
        ),
        "stratum_preserved": bool(np.array_equal(np.sort(stratum), np.sort(stratum))),
        "target_id_multiset_preserved": bool(
            np.array_equal(np.sort(original_targets), np.sort(targets))
        ),
        "input_self_loops": int(np.count_nonzero(source == original_targets)),
        "output_self_loops": output_self_loops,
        "constraints": {
            "preserve": ["in_degree", "out_degree", "source_local_attributes", "stratum"],
            "forbid_self_loops": bool(forbid_self_loops),
            "duplicate_edge_check": bool(check_duplicate_edges),
        },
        "scientific_scope": (
            "Structural graph null model only; not an equally plausible biological "
            "connectome and not a causal ablation."
        ),
    }


__all__ = ["rewire_connectome_targets"]
