"""Frozen, allow-listed evidence corpus for the Workbench RAG intake.

Retrieval is local and deterministic. This module never fetches URLs. A remote
LLM call is a separate operation and is gated by explicit manifest approvals.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from drosophila_pd.ai_v2.contracts import EvidenceItem
from drosophila_pd.ai_v2.rag import RAGRuntimeContract


_TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)
_MANIFEST_FIELDS = {
    "schema_version", "corpus_id", "corpus_file", "corpus_sha256",
    "approved_source_ids", "denied_source_ids", "partition",
    "owner_approved", "outcome_free", "provider_sharing_approved",
    "protocol_text_sharing_approved", "reviewed_by", "reviewed_at",
    "approved_provider_id", "approved_provider_endpoint",
}
_CHUNK_FIELDS = {"source_id", "citation", "chunk_id", "text", "provenance", "access_class"}
_ALLOWED_ACCESS = {"PUBLIC_UNLABELED", "DEVELOPMENT_INPUT"}
_MAX_MANIFEST_BYTES = 256 * 1024
_MAX_CORPUS_BYTES = 128 * 1024 * 1024
_MAX_CHUNK_BYTES = 1024 * 1024
_MAX_CHUNKS = 100_000
_MAX_K = 20
_MAX_QUERY_CHARS = 20_000


@dataclass(frozen=True)
class CorpusHit:
    """A validated citation record and its source text."""

    evidence: EvidenceItem
    text: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.evidence.source_id,
            "citation": self.evidence.citation,
            "chunk_id": self.evidence.chunk_id,
            "retrieval_score": self.evidence.retrieval_score,
            "provenance": self.evidence.provenance,
            "access_class": self.evidence.access_class,
            "text": self.text,
        }


class FrozenEvidenceCorpus:
    """In-memory snapshot of a hash-verified, reviewer-approved JSONL corpus."""

    def __init__(
        self,
        *,
        corpus_id: str,
        corpus_sha256: str,
        manifest_sha256: str,
        chunks: tuple[dict[str, str], ...],
        approved_source_ids: frozenset[str],
        denied_source_ids: frozenset[str],
        provider_sharing_approved: bool,
        protocol_text_sharing_approved: bool,
        approved_provider_id: str,
        approved_provider_endpoint: str,
        retrieval_log_path: Path,
    ) -> None:
        self.corpus_id = corpus_id
        self.corpus_sha256 = corpus_sha256
        self.manifest_sha256 = manifest_sha256
        self._chunks = chunks
        self.provider_sharing_approved = provider_sharing_approved
        self.protocol_text_sharing_approved = protocol_text_sharing_approved
        self.approved_provider_id = approved_provider_id
        self.approved_provider_endpoint = approved_provider_endpoint
        self.retrieval_log_path = retrieval_log_path
        self.contract = RAGRuntimeContract(
            corpus_sha256=corpus_sha256,
            approved_source_ids=approved_source_ids,
            denied_source_ids=denied_source_ids,
            no_internet=True,
            # The richer per-query audit event below is the single runtime log.
            retrieval_log_path=None,
        )
        self._tokenized = tuple(_tokens(item["text"]) for item in chunks)
        self._document_frequency: Counter[str] = Counter()
        for terms in self._tokenized:
            self._document_frequency.update(set(terms))
        self._average_length = (
            sum(map(len, self._tokenized)) / len(self._tokenized) if self._tokenized else 0.0
        )

    @property
    def chunk_count(self) -> int:
        return len(self._chunks)

    def retrieve(self, query: str, *, k: int = 5) -> tuple[CorpusHit, ...]:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")
        if len(query) > _MAX_QUERY_CHARS:
            raise ValueError(f"query exceeds {_MAX_QUERY_CHARS} characters")
        if isinstance(k, bool) or not isinstance(k, int) or not 1 <= k <= _MAX_K:
            raise ValueError(f"k must be an integer between 1 and {_MAX_K}")

        query_terms = Counter(_tokens(query))
        if not query_terms:
            return ()
        count = len(self._chunks)
        ranked: list[tuple[float, str, str, int]] = []
        for index, (chunk, terms) in enumerate(zip(self._chunks, self._tokenized, strict=True)):
            frequencies = Counter(terms)
            length_norm = 1.2 * (1.0 - 0.75 + 0.75 * len(terms) / max(self._average_length, 1.0))
            score = 0.0
            for token, query_frequency in sorted(query_terms.items()):
                term_frequency = frequencies.get(token, 0)
                if not term_frequency:
                    continue
                df = self._document_frequency[token]
                inverse_frequency = math.log(1.0 + (count - df + 0.5) / (df + 0.5))
                score += query_frequency * inverse_frequency * (term_frequency * 2.2) / (term_frequency + length_norm)
            if score > 0:
                ranked.append((round(score, 12), chunk["source_id"], chunk["chunk_id"], index))
        ranked.sort(key=lambda row: (-row[0], row[1], row[2]))

        query_sha256 = hashlib.sha256(query.encode("utf-8")).hexdigest()
        hits: list[CorpusHit] = []
        for rank, (score, _source_id, _chunk_id, index) in enumerate(ranked[:k], start=1):
            chunk = self._chunks[index]
            item = EvidenceItem(
                source_id=chunk["source_id"], citation=chunk["citation"],
                chunk_id=chunk["chunk_id"], retrieval_score=score,
                provenance=chunk["provenance"], access_class=chunk["access_class"],
            )
            self.contract.validate_result(item)
            self._append_log({
                "timestamp_utc": datetime.now(UTC).isoformat(),
                "query_sha256": query_sha256,
                "rank": rank,
                "source_id": item.source_id,
                "chunk_id": item.chunk_id,
                "citation": item.citation,
                "retrieval_score": score,
                "corpus_id": self.corpus_id,
                "corpus_sha256": self.corpus_sha256,
                "manifest_sha256": self.manifest_sha256,
            })
            hits.append(CorpusHit(item, chunk["text"]))
        return tuple(hits)

    def _append_log(self, event: dict[str, Any]) -> None:
        self.retrieval_log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.retrieval_log_path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")


def load_frozen_evidence_corpus(
    manifest_path: str | Path,
    *,
    retrieval_log_path: str | Path,
) -> FrozenEvidenceCorpus:
    """Load a strict manifest and verify the exact JSONL bytes before service."""

    manifest_path = Path(manifest_path).resolve(strict=True)
    if not manifest_path.is_file() or manifest_path.stat().st_size > _MAX_MANIFEST_BYTES:
        raise ValueError("RAG manifest must be a regular file no larger than 256 KiB")
    manifest_bytes = manifest_path.read_bytes()
    manifest = _read_json_object(manifest_bytes, "manifest")
    if set(manifest) != _MANIFEST_FIELDS:
        raise ValueError("RAG manifest has missing or unsupported fields")
    if manifest["schema_version"] != "approved-evidence-corpus-1":
        raise ValueError("unsupported RAG manifest schema_version")
    _nonempty(manifest["corpus_id"], "corpus_id")
    if manifest["partition"] != "DEVELOPMENT":
        raise ValueError("RAG runtime accepts DEVELOPMENT corpora only")
    for attestation in ("owner_approved", "outcome_free", "provider_sharing_approved", "protocol_text_sharing_approved"):
        if not isinstance(manifest[attestation], bool):
            raise ValueError(f"manifest {attestation} must be boolean")
    if not manifest["owner_approved"] or not manifest["outcome_free"]:
        raise ValueError("corpus must be owner-approved and explicitly attested outcome-free")
    reviewers = manifest["reviewed_by"]
    if (
        not isinstance(reviewers, list)
        or not reviewers
        or any(not isinstance(reviewer, str) or not reviewer.strip() for reviewer in reviewers)
        or len({reviewer.strip() for reviewer in reviewers}) != len(reviewers)
    ):
        raise ValueError("reviewed_by must identify at least one unique reviewer")
    reviewed_at = manifest["reviewed_at"]
    if not isinstance(reviewed_at, str) or not reviewed_at.strip():
        raise ValueError("reviewed_at must be a timezone-aware ISO-8601 timestamp")
    try:
        reviewed_timestamp = datetime.fromisoformat(reviewed_at.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("reviewed_at must be a timezone-aware ISO-8601 timestamp") from error
    if reviewed_timestamp.tzinfo is None or reviewed_timestamp.utcoffset() is None:
        raise ValueError("reviewed_at must be a timezone-aware ISO-8601 timestamp")
    approved_provider_id = manifest["approved_provider_id"]
    approved_provider_endpoint = manifest["approved_provider_endpoint"]
    if not isinstance(approved_provider_id, str) or not isinstance(approved_provider_endpoint, str):
        raise ValueError("approved provider identity and endpoint must be strings")
    if manifest["provider_sharing_approved"] and manifest["protocol_text_sharing_approved"]:
        if not approved_provider_id.strip() or not approved_provider_endpoint.strip():
            raise ValueError("provider-sharing approval must be bound to an exact provider ID and endpoint")
    elif approved_provider_id.strip() or approved_provider_endpoint.strip():
        raise ValueError("provider identity must be blank unless both sharing approvals are granted")
    corpus_hash = manifest["corpus_sha256"]
    if not isinstance(corpus_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", corpus_hash):
        raise ValueError("corpus_sha256 must be a lowercase SHA-256")
    approved = _source_ids(manifest["approved_source_ids"], "approved_source_ids")
    denied = _source_ids(manifest["denied_source_ids"], "denied_source_ids", allow_empty=True)
    if not approved or approved & denied:
        raise ValueError("approved and denied source IDs must be non-empty and disjoint")

    corpus_name = manifest["corpus_file"]
    if not isinstance(corpus_name, str) or not corpus_name.strip():
        raise ValueError("corpus_file must be a relative path")
    candidate = (manifest_path.parent / corpus_name).resolve(strict=True)
    if not candidate.is_relative_to(manifest_path.parent) or not candidate.is_file():
        raise ValueError("corpus_file must resolve to a regular file beside/under the manifest")
    corpus_bytes = candidate.read_bytes()
    if len(corpus_bytes) > _MAX_CORPUS_BYTES:
        raise ValueError("RAG corpus exceeds 128 MiB")
    actual_hash = hashlib.sha256(corpus_bytes).hexdigest()
    if actual_hash != corpus_hash:
        raise ValueError("RAG corpus SHA-256 mismatch; refusing to load")

    chunks: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for line_number, raw_line in enumerate(corpus_bytes.splitlines(), start=1):
        if not raw_line.strip():
            continue
        if len(raw_line) > _MAX_CHUNK_BYTES:
            raise ValueError(f"RAG corpus line {line_number} exceeds 1 MiB")
        row = _read_json_object(raw_line, f"corpus line {line_number}")
        if set(row) != _CHUNK_FIELDS:
            raise ValueError(f"RAG corpus line {line_number} has missing or unsupported fields")
        for key in _CHUNK_FIELDS:
            _nonempty(row[key], f"corpus line {line_number} {key}")
        source_id, chunk_id = row["source_id"], row["chunk_id"]
        if source_id not in approved or source_id in denied:
            raise ValueError(f"RAG corpus line {line_number} source is not approved")
        if row["access_class"] not in _ALLOWED_ACCESS:
            raise ValueError(f"RAG corpus line {line_number} has forbidden access_class")
        identity = (source_id, chunk_id)
        if identity in seen:
            raise ValueError(f"duplicate RAG chunk identity at line {line_number}")
        seen.add(identity)
        chunks.append({key: row[key].strip() for key in sorted(_CHUNK_FIELDS)})
        if len(chunks) > _MAX_CHUNKS:
            raise ValueError("RAG corpus exceeds 100,000 chunks")
    if not chunks:
        raise ValueError("RAG corpus must contain at least one approved chunk")
    chunks.sort(key=lambda row: (row["source_id"], row["chunk_id"]))
    return FrozenEvidenceCorpus(
        corpus_id=manifest["corpus_id"], corpus_sha256=actual_hash,
        manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
        chunks=tuple(chunks), approved_source_ids=approved, denied_source_ids=denied,
        provider_sharing_approved=manifest["provider_sharing_approved"],
        protocol_text_sharing_approved=manifest["protocol_text_sharing_approved"],
        approved_provider_id=approved_provider_id.strip(),
        approved_provider_endpoint=approved_provider_endpoint.strip(),
        retrieval_log_path=Path(retrieval_log_path),
    )


def _read_json_object(raw: bytes, label: str) -> dict[str, Any]:
    def no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key in {label}: {key}")
            result[key] = value
        return result

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=no_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid UTF-8 JSON in {label}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _source_ids(value: Any, name: str, *, allow_empty: bool = False) -> frozenset[str]:
    if not isinstance(value, list) or (not allow_empty and not value):
        raise ValueError(f"{name} must be a list of source IDs")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"{name} must contain non-empty strings")
    normalized = [item.strip() for item in value]
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{name} cannot contain duplicates")
    return frozenset(normalized)


def _nonempty(value: Any, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")


def _tokens(text: str) -> list[str]:
    return [token.casefold() for token in _TOKEN_RE.findall(text)]


__all__ = ["CorpusHit", "FrozenEvidenceCorpus", "load_frozen_evidence_corpus"]
