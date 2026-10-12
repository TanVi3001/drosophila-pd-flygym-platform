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
    provenance: dict[str, str] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.study, StudySpec):
            raise TypeError("study must be a Workbench StudySpec")
        if self.approval_status != "DRAFT":
            raise ValueError("AI StudySpec cannot self-approve")
        if not self.evidence_ids or any(not item for item in self.evidence_ids):
            raise ValueError("evidence IDs are required")
        provenance = dict(self.provenance or {})
        allowed = {
            "provider_id", "model_id", "prompt_version", "corpus_sha256",
            "retrieval_log_sha256", "generator_output_sha256",
        }
        if set(provenance) - allowed:
            raise ValueError("AIStudySpec provenance contains an unsupported field")
        for key, value in provenance.items():
            _required(value, f"provenance.{key}")
            if key.endswith("_sha256"):
                _hash(value, f"provenance.{key}")
        object.__setattr__(self, "evidence_ids", tuple(self.evidence_ids))
        object.__setattr__(self, "provenance", provenance)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "ai-v2-study-draft-1",
            "study": self.study.as_dict(),
            "evidence_ids": list(self.evidence_ids),
            "approval_status": self.approval_status,
            "provenance": dict(self.provenance or {}),
            "scientific_scope": "AI-generated draft; not approved and not biological validation.",
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AIStudySpec":
        """Parse the public draft contract without accepting unknown controls."""

        if not isinstance(data, dict):
            raise TypeError("AIStudySpec payload must be an object")
        allowed = {
            "schema_version", "study", "evidence_ids", "approval_status",
            "provenance", "scientific_scope",
        }
        if set(data) - allowed:
            raise ValueError("AIStudySpec payload contains unsupported fields")
        version = data.get("schema_version", "ai-v2-study-draft-1")
        if version != "ai-v2-study-draft-1":
            raise ValueError("unsupported AIStudySpec schema_version")
        study_data = data.get("study")
        if not isinstance(study_data, dict):
            raise TypeError("AIStudySpec study must be an object")
        evidence_ids = data.get("evidence_ids")
        if not isinstance(evidence_ids, list) or any(not isinstance(item, str) for item in evidence_ids):
            raise TypeError("AIStudySpec evidence_ids must be a list of strings")
        provenance = data.get("provenance", {})
        if not isinstance(provenance, dict) or any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in provenance.items()
        ):
            raise TypeError("AIStudySpec provenance must be a string-to-string object")
        return cls(
            study=StudySpec.from_dict(study_data),
            evidence_ids=tuple(evidence_ids),
            approval_status=str(data.get("approval_status", "DRAFT")),
            provenance=dict(provenance),
        )


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
