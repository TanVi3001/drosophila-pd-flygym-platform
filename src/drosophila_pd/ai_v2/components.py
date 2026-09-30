"""Replaceable interfaces; implementations must honor the development firewall."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Protocol

from .access import DevelopmentLabels
from .contracts import AIStudySpec, EvidenceItem, GraphEmbeddingArtifact, RankingPrediction, UnifiedFeatures


class EvidenceRetriever(Protocol):
    def retrieve(self, query: str) -> Sequence[EvidenceItem]: ...


class StudySpecGenerator(Protocol):
    def draft(self, query: str, evidence: Sequence[EvidenceItem]) -> AIStudySpec: ...


class GraphEncoder(Protocol):
    def encode(self, study: AIStudySpec) -> tuple[GraphEmbeddingArtifact, tuple[float, ...]]: ...


class FeatureFusion(Protocol):
    def fuse(self, case_id: str, *, lif_effect: tuple[float, ...], graph_embedding: tuple[float, ...], uncertainty: tuple[float, ...], qc_provenance: tuple[float, ...]) -> UnifiedFeatures: ...


class RankingHead(Protocol):
    def predict(self, features: UnifiedFeatures) -> RankingPrediction: ...


class UncertaintyEstimator(Protocol):
    def estimate(self, features: UnifiedFeatures) -> float: ...


class AIV2ExperimentRunner(Protocol):
    def run_fold(self, *, fold: int, labels: DevelopmentLabels, predict: Callable[[str], RankingPrediction], output_dir: Path, k: int = 5) -> dict[str, object]: ...
