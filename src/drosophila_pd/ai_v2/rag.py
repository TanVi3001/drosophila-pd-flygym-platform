"""Offline, frozen-corpus retrieval contract; no web retrieval is implemented."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
from datetime import UTC, datetime

from .contracts import EvidenceItem, _hash


RAG_METRIC_HOOKS = ("recall_at_k", "precision_at_k", "citation_precision", "studyspec_field_accuracy", "unsupported_claim_rate")


@dataclass(frozen=True)
class RAGRuntimeContract:
    corpus_sha256: str
    approved_source_ids: frozenset[str]
    denied_source_ids: frozenset[str]
    no_internet: bool = True
    retrieval_log_path: Path | None = None

    def __post_init__(self) -> None:
        _hash(self.corpus_sha256, "corpus_sha256")
        if not self.no_internet or not self.approved_source_ids or self.approved_source_ids & self.denied_source_ids:
            raise ValueError("RAG requires an offline frozen corpus and disjoint allow/deny lists")

    def validate_result(self, item: EvidenceItem) -> dict[str, object]:
        if item.source_id not in self.approved_source_ids or item.source_id in self.denied_source_ids:
            raise ValueError("retrieval source is not approved")
        if item.access_class not in {"PUBLIC_UNLABELED", "DEVELOPMENT_INPUT"}:
            raise ValueError("retrieval source access class is forbidden")
        event = {"timestamp_utc": datetime.now(UTC).isoformat(), "source_id": item.source_id, "chunk_id": item.chunk_id, "citation": item.citation, "corpus_sha256": self.corpus_sha256}
        if self.retrieval_log_path is not None:
            path = Path(self.retrieval_log_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(event, sort_keys=True) + "\n")
        return event
