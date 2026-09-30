"""Validated, serialization-safe contracts for development experiments."""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass
from typing import Any

from drosophila_pd.workbench.models import StudySpec

SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _required(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")


def _hash(value: str, name: str) -> None:
    if not SHA256.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA-256")


@dataclass(frozen=True)
class EvidenceItem:
    source_id: str
    citation: str
    chunk_id: str
    retrieval_score: float
    provenance: str
    access_class: str

    def __post_init__(self) -> None:
        for name in ("source_id", "citation", "chunk_id", "provenance", "access_class"):
            _required(getattr(self, name), name)
        if not math.isfinite(self.retrieval_score):
            raise ValueError("retrieval_score must be finite")


@dataclass(frozen=True)
class AIStudySpec:
    study: StudySpec
    evidence_ids: tuple[str, ...]
    approval_status: str = "DRAFT"

    def __post_init__(self) -> None:
        if not isinstance(self.study, StudySpec):
            raise TypeError("study must be a Workbench StudySpec")
        if self.approval_status != "DRAFT":
            raise ValueError("AI StudySpec cannot self-approve")
        if not self.evidence_ids or any(not item for item in self.evidence_ids):
            raise ValueError("evidence IDs are required")


@dataclass(frozen=True)
class GraphEmbeddingArtifact:
    graph_source_sha256: str
    encoder_id: str
    encoder_config_sha256: str
    embedding_dimension: int
    pretraining_mode: str
    graph_scope: str
    source_commit: str

    def __post_init__(self) -> None:
        _hash(self.graph_source_sha256, "graph_source_sha256")
        _hash(self.encoder_config_sha256, "encoder_config_sha256")
        _required(self.encoder_id, "encoder_id")
        _required(self.source_commit, "source_commit")
        if self.embedding_dimension < 1 or self.graph_scope not in {"inductive", "transductive"}:
            raise ValueError("invalid graph dimension/scope")
        if self.graph_scope != "inductive":
            raise ValueError("transductive use requires a separate approved protocol")
        if self.pretraining_mode != "self_supervised_unlabeled":
            raise ValueError("only unlabeled self-supervised pretraining is defined")


@dataclass(frozen=True)
class UnifiedFeatures:
    case_id: str
    lif_effect: tuple[float, ...]
    graph_embedding: tuple[float, ...]
    uncertainty: tuple[float, ...]
    qc_provenance: tuple[float, ...]

    def __post_init__(self) -> None:
        _required(self.case_id, "case_id")
        families = (self.lif_effect, self.graph_embedding, self.uncertainty, self.qc_provenance)
        if any(not family for family in families):
            raise ValueError("all four feature families must be identified")
        if any(not math.isfinite(value) for family in families for value in family):
            raise ValueError("feature values must be finite")


@dataclass(frozen=True)
class RankingPrediction:
    case_id: str
    score: float
    uncertainty: float
    model_id: str
    config_sha256: str
    probability: float | None = None

    def __post_init__(self) -> None:
        _required(self.case_id, "case_id")
        _required(self.model_id, "model_id")
        _hash(self.config_sha256, "config_sha256")
        if not math.isfinite(self.score) or not math.isfinite(self.uncertainty) or self.uncertainty < 0:
            raise ValueError("invalid score/uncertainty")
        if self.probability is not None and (not math.isfinite(self.probability) or not 0 <= self.probability <= 1):
            raise ValueError("probability must be between 0 and 1")

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
