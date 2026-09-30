"""Future graph pretraining declaration; no trainer is implemented."""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import _hash, _required


@dataclass(frozen=True)
class GraphPretrainingContract:
    unlabeled_graph_source: str
    source_sha256: str
    feature_mask_policy: str
    encoder_type: str
    random_seed: int
    pretraining_task: str
    embedding_dimension: int
    graph_scope: str = "inductive"

    def __post_init__(self) -> None:
        for name in ("unlabeled_graph_source", "feature_mask_policy", "encoder_type", "pretraining_task"):
            _required(getattr(self, name), name)
        _hash(self.source_sha256, "source_sha256")
        if self.embedding_dimension < 1 or self.graph_scope != "inductive":
            raise ValueError("only positive-dimension inductive pretraining is available")
        if any(token in self.unlabeled_graph_source.casefold() for token in ("label", "outcome", "heldout", "held_out")):
            raise ValueError("graph source must be unlabeled")
