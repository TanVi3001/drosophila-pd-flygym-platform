"""Offline, checksum-locked retrieval over explicitly approved evidence chunks.

The module deliberately uses a small lexical scorer and standard-library JSON.
It does not crawl the web, ingest Notion, or access benchmark outcomes.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit


CORPUS_SCHEMA = "fly-workbench-approved-evidence-1"
ACCESS_CLASS = "PUBLIC_UNLABELED"
EVIDENCE_SCOPES = {
    "assay_definition",
    "dataset_identity",
    "mapping_context",
    "methods",
    "model_capability",
}
_HASH_RE = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_ID_OUTCOME_MARKERS = re.compile(
    r"(^|[._:-])(positive|negative|responder|nonresponder|phenotype|outcome|"
    r"heldout|held-out|label|result|effect)(?=$|[._:-])",
    re.IGNORECASE,
)
_TOKEN_RE = re.compile(r"[^\W_]+(?:['’][^\W_]+)?", re.UNICODE)
_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in",
    "is", "it", "of", "on", "or", "the", "to", "was", "were", "with",
    "cua", "của", "cho", "đã", "được", "là", "một", "những", "và", "về",
    "trong", "các", "theo", "này", "để", "từ", "với",
}
_ROOT_KEYS = {"schema_version", "corpus_id", "corpus_version", "sources"}
_SOURCE_KEYS = {
    "source_id", "citation", "source_uri", "dataset_version", "evidence_tier",
    "source_sha256", "review_status", "reviewer", "reviewed_at",
    "approval_record_id", "blind_use", "chunks",
}
_CHUNK_KEYS = {
    "chunk_id", "locator", "evidence_scope", "text", "text_sha256",
    "access_class", "blind_review_status", "blind_reviewer", "blind_reviewed_at",
}
_AUDIT_LOCK = threading.Lock()


class EvidenceCorpusError(ValueError):
    """Raised when a corpus is not approved, intact, or safely scoped."""


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise EvidenceCorpusError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _require_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EvidenceCorpusError(f"{field} must be a non-empty string")
    return value.strip()


def _require_hash(value: Any, field: str) -> str:
    digest = _require_text(value, field)
    if not _HASH_RE.fullmatch(digest):
        raise EvidenceCorpusError(f"{field} must be a SHA-256 hex digest")
    return digest.lower()


def _require_id(value: Any, field: str) -> str:
    identifier = _require_text(value, field)
    if not _ID_RE.fullmatch(identifier) or _ID_OUTCOME_MARKERS.search(identifier):
        raise EvidenceCorpusError(f"{field} is not a safe opaque identifier")
    return identifier


def _require_timestamp(value: Any, field: str) -> str:
    timestamp = _require_text(value, field)
    try:
        datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as error:
        raise EvidenceCorpusError(f"{field} must be an ISO-8601 timestamp") from error
    return timestamp


def _exact_keys(value: Mapping[str, Any], expected: set[str], field: str) -> None:
    actual = set(value)
    if actual != expected:
        unknown = sorted(actual - expected)
        missing = sorted(expected - actual)
        raise EvidenceCorpusError(f"{field} keys mismatch (unknown={unknown}, missing={missing})")


@dataclass(frozen=True)
class EvidenceChunk:
    evidence_id: str
    source_id: str
    citation: str
    source_uri: str
    locator: str
    dataset_version: str
    evidence_tier: str
    evidence_scope: str
    text: str
    text_sha256: str
    source_sha256: str
    approval_record_id: str
    source_reviewer: str
    source_reviewed_at: str
    chunk_blind_reviewer: str
    chunk_blind_reviewed_at: str
    blind_use: str
    retrieval_score: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "source_id": self.source_id,
            "citation": self.citation,
            "source_uri": self.source_uri,
            "locator": self.locator,
            "dataset_version": self.dataset_version,
            "evidence_tier": self.evidence_tier,
            "evidence_scope": self.evidence_scope,
            "text": self.text,
            "text_sha256": self.text_sha256,
            "source_sha256": self.source_sha256,
            "review_status": "APPROVED",
            "approval_record_id": self.approval_record_id,
            "source_reviewer": self.source_reviewer,
            "source_reviewed_at": self.source_reviewed_at,
            "access_class": ACCESS_CLASS,
            "blind_use": self.blind_use,
            "blind_review_status": "PASS",
            "blind_reviewer": self.chunk_blind_reviewer,
            "blind_reviewed_at": self.chunk_blind_reviewed_at,
            "retrieval_score": self.retrieval_score,
        }


@dataclass(frozen=True)
class RetrievalResult:
    status: str
    corpus_sha256: str
    evidence: tuple[EvidenceChunk, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "corpus_sha256": self.corpus_sha256,
            "retrieval_algorithm": "lexical_overlap_v1",
            "evidence": [item.as_dict() for item in self.evidence],
        }


class ApprovedEvidenceCorpus:
    """Validated snapshot of an externally stored, human-approved corpus."""

    def __init__(self, *, corpus_sha256: str, corpus_id: str, corpus_version: str,
                 chunks: tuple[EvidenceChunk, ...]) -> None:
        self.corpus_sha256 = corpus_sha256
        self.corpus_id = corpus_id
        self.corpus_version = corpus_version
        self.chunks = chunks

    @classmethod
    def load(
        cls,
        path: str | Path,
        *,
        expected_sha256: str,
        corpus_root: str | Path,
    ) -> "ApprovedEvidenceCorpus":
        source_path = Path(path).expanduser()
        root = Path(corpus_root).expanduser().resolve()
        if not source_path.is_absolute():
            raise EvidenceCorpusError("corpus path must be absolute")
        try:
            resolved = source_path.resolve(strict=True)
            resolved.relative_to(root)
        except (OSError, ValueError) as error:
            raise EvidenceCorpusError("corpus file must exist inside the configured external corpus directory") from error
        if resolved.name != "corpus.json" or not resolved.is_file():
            raise EvidenceCorpusError("approved corpus file must be named corpus.json")
        expected = _require_hash(expected_sha256, "expected_sha256")
        payload = resolved.read_bytes()
        actual_hash = sha256_bytes(payload)
        if actual_hash != expected:
            raise EvidenceCorpusError("corpus SHA-256 does not match the configured digest")
        try:
            document = json.loads(payload.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise EvidenceCorpusError("corpus must be valid UTF-8 JSON") from error
        if not isinstance(document, Mapping):
            raise EvidenceCorpusError("corpus root must be an object")
        _exact_keys(document, _ROOT_KEYS, "corpus")
        if document["schema_version"] != CORPUS_SCHEMA:
            raise EvidenceCorpusError("unsupported evidence corpus schema_version")
        corpus_id = _require_id(document["corpus_id"], "corpus_id")
        corpus_version = _require_text(document["corpus_version"], "corpus_version")
        sources = document["sources"]
        if not isinstance(sources, list) or not sources:
            raise EvidenceCorpusError("corpus must contain at least one approved source")

        chunks: list[EvidenceChunk] = []
        seen_sources: set[str] = set()
        seen_chunks: set[str] = set()
        for source in sources:
            if not isinstance(source, Mapping):
                raise EvidenceCorpusError("each source must be an object")
            _exact_keys(source, _SOURCE_KEYS, "source")
            source_id = _require_id(source["source_id"], "source_id")
            if source_id in seen_sources:
                raise EvidenceCorpusError("source_id values must be unique")
            seen_sources.add(source_id)
            citation = _require_text(source["citation"], "citation")
            source_uri = _require_text(source["source_uri"], "source_uri")
            parsed_source_uri = urlsplit(source_uri)
            if parsed_source_uri.scheme not in {"http", "https", "doi"} or parsed_source_uri.username or parsed_source_uri.password:
                raise EvidenceCorpusError(f"source {source_id} source_uri must be a public HTTP(S) or DOI reference")
            dataset_version = _require_text(source["dataset_version"], "dataset_version")
            evidence_tier = _require_text(source["evidence_tier"], "evidence_tier").upper()
            if evidence_tier not in {"PRIMARY", "SECONDARY", "METHODS"}:
                raise EvidenceCorpusError("evidence_tier must be PRIMARY, SECONDARY, or METHODS")
            source_hash = _require_hash(source["source_sha256"], "source_sha256")
            if str(source["review_status"]).upper() != "APPROVED":
                raise EvidenceCorpusError(f"source {source_id} is not approved")
            source_reviewer = _require_text(source["reviewer"], "reviewer")
            source_reviewed_at = _require_timestamp(source["reviewed_at"], "reviewed_at")
            approval_record_id = _require_id(source["approval_record_id"], "approval_record_id")
            blind_use = str(source["blind_use"]).upper()
            if blind_use != "ELIGIBLE":
                raise EvidenceCorpusError("only blind_use=ELIGIBLE sources may enter this retrieval corpus")
            source_chunks = source["chunks"]
            if not isinstance(source_chunks, list) or not source_chunks:
                raise EvidenceCorpusError(f"approved source {source_id} has no chunks")
            for chunk in source_chunks:
                if not isinstance(chunk, Mapping):
                    raise EvidenceCorpusError("each chunk must be an object")
                _exact_keys(chunk, _CHUNK_KEYS, "chunk")
                chunk_id = _require_id(chunk["chunk_id"], "chunk_id")
                if chunk_id in seen_chunks:
                    raise EvidenceCorpusError("chunk_id values must be globally unique")
                seen_chunks.add(chunk_id)
                locator = _require_text(chunk["locator"], "locator")
                scope = _require_text(chunk["evidence_scope"], "evidence_scope").lower()
                if scope not in EVIDENCE_SCOPES:
                    raise EvidenceCorpusError(f"chunk {chunk_id} has a prohibited evidence_scope")
                if str(chunk["access_class"]).upper() != ACCESS_CLASS:
                    raise EvidenceCorpusError(f"chunk {chunk_id} is not PUBLIC_UNLABELED")
                if str(chunk["blind_review_status"]).upper() != "PASS":
                    raise EvidenceCorpusError(f"chunk {chunk_id} has not passed its leakage review")
                chunk_blind_reviewer = _require_text(chunk["blind_reviewer"], "blind_reviewer")
                chunk_blind_reviewed_at = _require_timestamp(chunk["blind_reviewed_at"], "blind_reviewed_at")
                text = _require_text(chunk["text"], "chunk text")
                text_hash = _require_hash(chunk["text_sha256"], "text_sha256")
                if sha256_bytes(text.encode("utf-8")) != text_hash:
                    raise EvidenceCorpusError(f"chunk {chunk_id} text hash mismatch")
                chunks.append(EvidenceChunk(
                    evidence_id=chunk_id,
                    source_id=source_id,
                    citation=citation,
                    source_uri=source_uri,
                    locator=locator,
                    dataset_version=dataset_version,
                    evidence_tier=evidence_tier,
                    evidence_scope=scope,
                    text=text,
                    text_sha256=text_hash,
                    source_sha256=source_hash,
                    approval_record_id=approval_record_id,
                    source_reviewer=source_reviewer,
                    source_reviewed_at=source_reviewed_at,
                    chunk_blind_reviewer=chunk_blind_reviewer,
                    chunk_blind_reviewed_at=chunk_blind_reviewed_at,
                    blind_use=blind_use,
                ))
        if not chunks:
            raise EvidenceCorpusError("approved corpus contains no retrievable chunks")
        return cls(
            corpus_sha256=actual_hash,
            corpus_id=corpus_id,
            corpus_version=corpus_version,
            chunks=tuple(sorted(chunks, key=lambda item: item.evidence_id)),
        )


def _terms(text: str) -> set[str]:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return {term for term in _TOKEN_RE.findall(normalized) if term not in _STOPWORDS and len(term) > 1}


class OfflineEvidenceRetriever:
    """Deterministic lexical retrieval with a mandatory privacy-minimized audit log."""

    def __init__(self, corpus: ApprovedEvidenceCorpus, *, audit_path: str | Path,
                 output_root: str | Path) -> None:
        self.corpus = corpus
        root = Path(output_root).expanduser().resolve()
        candidate = Path(audit_path).expanduser()
        if not candidate.is_absolute():
            raise ValueError("retrieval audit path must be absolute")
        resolved = candidate.resolve()
        try:
            resolved.relative_to(root)
        except ValueError as error:
            raise ValueError("retrieval audit path must be inside the V2 output root") from error
        self.audit_path = resolved
        self.output_root = root

    def retrieve(self, query: str, *, top_k: int = 5) -> RetrievalResult:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")
        if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= 50:
            raise ValueError("top_k must be an integer between 1 and 50")
        query_terms = _terms(query)
        scored: list[EvidenceChunk] = []
        if query_terms:
            for chunk in self.corpus.chunks:
                chunk_terms = _terms(" ".join((chunk.citation, chunk.locator, chunk.text)))
                overlap = len(query_terms & chunk_terms)
                if overlap:
                    scored.append(EvidenceChunk(**{
                        **chunk.__dict__,
                        "retrieval_score": round(overlap / len(query_terms), 12),
                    }))
        ranked = tuple(sorted(scored, key=lambda item: (-item.retrieval_score, item.evidence_id))[:top_k])
        result = RetrievalResult(
            status="RETRIEVED" if ranked else "NO_APPROVED_EVIDENCE",
            corpus_sha256=self.corpus.corpus_sha256,
            evidence=ranked,
        )
        self.record_event({
            "event": "evidence_retrieval",
            "timestamp": datetime.now(UTC).isoformat(),
            "query_sha256": sha256_bytes(query.encode("utf-8")),
            "corpus_sha256": self.corpus.corpus_sha256,
            "top_k": top_k,
            "result_status": result.status,
            "results": [
                {
                    "source_id": item.source_id,
                    "evidence_id": item.evidence_id,
                    "citation": item.citation,
                    "source_uri": item.source_uri,
                    "locator": item.locator,
                    "dataset_version": item.dataset_version,
                    "evidence_tier": item.evidence_tier,
                    "evidence_scope": item.evidence_scope,
                    "text_sha256": item.text_sha256,
                    "approval_record_id": item.approval_record_id,
                    "retrieval_score": item.retrieval_score,
                }
                for item in ranked
            ],
        })
        return result

    def record_event(self, event: Mapping[str, Any]) -> None:
        """Append one redacted event; raw question/protocol/evidence text is forbidden."""
        if any(key in event for key in {"query", "protocol_text", "text", "prompt", "response"}):
            raise ValueError("audit events must not contain raw query, protocol, prompt, or text")
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.audit_path.resolve().relative_to(self.output_root)
        except ValueError as error:
            raise ValueError("retrieval audit path escaped the V2 output root") from error
        payload = json.dumps(dict(event), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        with _AUDIT_LOCK:
            with self.audit_path.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(payload + "\n")


__all__ = [
    "ACCESS_CLASS", "CORPUS_SCHEMA", "EVIDENCE_SCOPES", "ApprovedEvidenceCorpus",
    "EvidenceChunk", "EvidenceCorpusError", "OfflineEvidenceRetriever", "RetrievalResult",
    "sha256_bytes",
]
