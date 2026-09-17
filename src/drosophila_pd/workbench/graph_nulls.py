"""Auditable directed graph null models for Workbench benchmarks.

The null model in this module is deliberately small and explicit.  A directed
double-edge swap preserves source and target degree while exchanging targets
between two edges.  Edge weights stay attached to their source edge, so the
outgoing weight multiset is also preserved per source.  Optional ``stratum``
values constrain swaps to declared edge classes (for example neurotransmitter
or sign classes); the constraint is part of the returned provenance.

This is a structural null model, not a biological model.  It must not be used
to claim that a rewired graph is an equally plausible connectome.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import Any, Mapping, Sequence

from .models import stable_hash


@dataclass(frozen=True)
class GraphEdge:
    """Minimal directed weighted edge used by the null-model helper."""

    source: str
    target: str
    weight: float = 1.0
    stratum: str = "default"

    def __post_init__(self) -> None:
        if not str(self.source).strip() or not str(self.target).strip():
            raise ValueError("graph edges require non-empty source and target IDs")
        value = float(self.weight)
        if not math.isfinite(value):
            raise ValueError("graph edge weights must be finite")
        object.__setattr__(self, "source", str(self.source))
        object.__setattr__(self, "target", str(self.target))
        object.__setattr__(self, "weight", value)
        object.__setattr__(self, "stratum", str(self.stratum))

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "weight": self.weight,
            "stratum": self.stratum,
        }


def _coerce_edge(value: GraphEdge | Mapping[str, Any]) -> GraphEdge:
    if isinstance(value, GraphEdge):
        return value
    if not isinstance(value, Mapping):
        raise TypeError("edges must be GraphEdge objects or mappings")
    return GraphEdge(
        source=str(value.get("source", value.get("pre", ""))),
        target=str(value.get("target", value.get("post", ""))),
        weight=float(value.get("weight", 1.0)),
        stratum=str(value.get("stratum", value.get("sign", "default"))),
    )


def degree_signature(edges: Sequence[GraphEdge | Mapping[str, Any]]) -> dict[str, dict[str, int]]:
    """Return integer in/out degree signatures for invariant checks."""

    normalized = [_coerce_edge(edge) for edge in edges]
    signature: dict[str, dict[str, int]] = {}
    for edge in normalized:
        signature.setdefault(edge.source, {"in_degree": 0, "out_degree": 0})["out_degree"] += 1
        signature.setdefault(edge.target, {"in_degree": 0, "out_degree": 0})["in_degree"] += 1
    return {node: signature[node] for node in sorted(signature)}


def outgoing_weight_signature(edges: Sequence[GraphEdge | Mapping[str, Any]]) -> dict[str, tuple[float, ...]]:
    """Return sorted outgoing weights per source for a stronger invariant."""

    result: dict[str, list[float]] = {}
    for edge in (_coerce_edge(item) for item in edges):
        result.setdefault(edge.source, []).append(edge.weight)
    return {node: tuple(sorted(values)) for node, values in sorted(result.items())}


def degree_preserving_rewire(
    edges: Sequence[GraphEdge | Mapping[str, Any]],
    *,
    seed: int,
    swaps: int,
    max_attempts: int | None = None,
    forbid_self_loops: bool = True,
) -> dict[str, Any]:
    """Generate one auditable directed degree-preserving null graph.

    Swaps are restricted to edges with the same ``stratum``.  A swap of
    ``(a -> b, c -> d)`` becomes ``(a -> d, c -> b)``.  Existing directed
    edges and self-loops are rejected.  The function returns ``PARTIAL`` when
    the requested number of valid swaps cannot be reached; callers must not
    silently treat that as a completed null graph.
    """

    if swaps < 0:
        raise ValueError("swaps must be non-negative")
    normalized = [_coerce_edge(edge) for edge in edges]
    if len({(edge.source, edge.target) for edge in normalized}) != len(normalized):
        raise ValueError("input graph must not contain duplicate directed edges")
    rng = random.Random(int(seed))
    limit = max_attempts if max_attempts is not None else max(100, swaps * 100)
    if limit < 0:
        raise ValueError("max_attempts must be non-negative")

    current = list(normalized)
    successful = 0
    attempts = 0
    while successful < swaps and attempts < limit and len(current) >= 2:
        attempts += 1
        first_index, second_index = rng.sample(range(len(current)), 2)
        first = current[first_index]
        second = current[second_index]
        if first.stratum != second.stratum or first.source == second.source or first.target == second.target:
            continue
        candidate_pairs = {
            (first.source, second.target),
            (second.source, first.target),
        }
        if forbid_self_loops and any(source == target for source, target in candidate_pairs):
            continue
        occupied = {(edge.source, edge.target) for index, edge in enumerate(current) if index not in {first_index, second_index}}
        if candidate_pairs & occupied or len(candidate_pairs) != 2:
            continue
        current[first_index] = GraphEdge(first.source, second.target, first.weight, first.stratum)
        current[second_index] = GraphEdge(second.source, first.target, second.weight, second.stratum)
        successful += 1

    output_edges = [edge.as_dict() for edge in current]
    original_edges = [edge.as_dict() for edge in normalized]
    return {
        "null_model": "directed_double_edge_swap",
        "status": "PASS" if successful == swaps else "PARTIAL",
        "seed": int(seed),
        "requested_swaps": int(swaps),
        "successful_swaps": int(successful),
        "attempts": int(attempts),
        "max_attempts": int(limit),
        "constraints": {
            "preserve": ["in_degree", "out_degree", "source_outgoing_weight_multiset", "stratum"],
            "forbid_self_loops": bool(forbid_self_loops),
        },
        "input_edge_count": len(normalized),
        "input_hash": stable_hash(original_edges),
        "output_hash": stable_hash(output_edges),
        "degree_preserved": degree_signature(normalized) == degree_signature(current),
        "outgoing_weights_preserved": outgoing_weight_signature(normalized)
        == outgoing_weight_signature(current),
        "edges": output_edges,
        "scientific_scope": (
            "Structural graph null model only; not an equally plausible biological "
            "connectome and not a causal ablation."
        ),
    }


__all__ = [
    "GraphEdge",
    "degree_preserving_rewire",
    "degree_signature",
    "outgoing_weight_signature",
]
