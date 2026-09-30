"""One case through replaceable interfaces. Produces a draft and a prediction."""

from __future__ import annotations

from dataclasses import dataclass

from .components import EvidenceRetriever, FeatureFusion, GraphEncoder, RankingHead, StudySpecGenerator, UncertaintyEstimator
from .contracts import AIStudySpec, RankingPrediction
from .rag import RAGRuntimeContract


@dataclass
class AIV2Pipeline:
    retriever: EvidenceRetriever
    generator: StudySpecGenerator
    encoder: GraphEncoder
    fusion: FeatureFusion
    uncertainty: UncertaintyEstimator
    ranking: RankingHead
    rag_contract: RAGRuntimeContract
    approved_development_ids: frozenset[str]

    def run_case(self, case_id: str, query: str, *, lif_effect: tuple[float, ...], uncertainty_features: tuple[float, ...], qc_provenance: tuple[float, ...]) -> tuple[AIStudySpec, RankingPrediction]:
        if case_id not in self.approved_development_ids:
            raise ValueError("case is outside the approved development partition")
        evidence = tuple(self.retriever.retrieve(query))
        if not evidence:
            raise ValueError("evidence is required")
        for item in evidence:
            self.rag_contract.validate_result(item)
        study = self.generator.draft(query, evidence)
        artifact, vector = self.encoder.encode(study)
        if len(vector) != artifact.embedding_dimension:
            raise ValueError("graph embedding dimension mismatch")
        features = self.fusion.fuse(case_id, lif_effect=lif_effect, graph_embedding=vector, uncertainty=uncertainty_features, qc_provenance=qc_provenance)
        estimate = self.uncertainty.estimate(features)
        prediction = self.ranking.predict(features)
        if prediction.case_id != case_id or prediction.uncertainty != estimate:
            raise ValueError("prediction case/uncertainty mismatch")
        return study, prediction
