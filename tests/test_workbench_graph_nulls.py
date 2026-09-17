from __future__ import annotations

from drosophila_pd.workbench import (
    GraphEdge,
    degree_preserving_rewire,
    degree_signature,
    degree_preserving_rewire_scores,
    outgoing_weight_signature,
)


def _graph() -> list[GraphEdge]:
    return [
        GraphEdge("a", "x", 2.0, "excitatory"),
        GraphEdge("a", "y", 3.0, "excitatory"),
        GraphEdge("b", "y", 5.0, "excitatory"),
        GraphEdge("b", "z", 7.0, "excitatory"),
        GraphEdge("c", "x", 11.0, "inhibitory"),
        GraphEdge("c", "z", 13.0, "inhibitory"),
    ]


def test_degree_preserving_rewire_keeps_declared_invariants() -> None:
    original = _graph()
    result = degree_preserving_rewire(original, seed=19, swaps=4, max_attempts=1000)

    assert result["status"] == "PASS"
    assert result["degree_preserved"] is True
    assert result["outgoing_weights_preserved"] is True
    assert degree_signature(original) == degree_signature(result["edges"])
    assert outgoing_weight_signature(original) == outgoing_weight_signature(result["edges"])
    assert result["input_hash"]
    assert result["output_hash"]


def test_rewire_is_deterministic_for_seed_and_rejects_partial_as_partial() -> None:
    original = _graph()
    first = degree_preserving_rewire(original, seed=7, swaps=2, max_attempts=100)
    second = degree_preserving_rewire(original, seed=7, swaps=2, max_attempts=100)
    assert first == second

    partial = degree_preserving_rewire(original, seed=7, swaps=100, max_attempts=1)
    assert partial["status"] == "PARTIAL"
    assert partial["successful_swaps"] < partial["requested_swaps"]


def test_rewire_does_not_cross_strata() -> None:
    result = degree_preserving_rewire(_graph(), seed=3, swaps=10, max_attempts=1000)
    assert all(edge["stratum"] in {"excitatory", "inhibitory"} for edge in result["edges"])


def test_rewire_score_adapter_keeps_partial_replicates_out_of_aggregate() -> None:
    result = degree_preserving_rewire_scores(
        _graph(),
        lambda edges: {"case": sum(float(edge["weight"]) for edge in edges)},
        seeds=[1, 2],
        swaps=1,
        max_attempts=1000,
    )
    assert result["status"] == "PASS"
    assert result["completed_replicates"] == 2
    assert result["scores"]["case"] == 41.0
