"""Exact-name lookup over human-reviewed mapping records; never creates mappings."""

from __future__ import annotations

import hashlib
import unicodedata
from collections.abc import Mapping
from typing import Any

from .support import MappingRecord


_USABLE_REVIEW_STATES = {"COMPUTATIONALLY_REVIEWED", "BIOLOGY_REVIEWED"}


def _normalize_target(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def resolve_reviewed_mappings(
    target_query: str | None,
    mapping_records: Mapping[str, Mapping[str, Any]] | None,
) -> dict[str, Any]:
    """Return only exact normalized matches in already-reviewed records.

    No aliases, partial matches, semantic model calls, new IDs, or mutation are
    performed. Target-query text is represented only by its digest.
    """
    if target_query is None or not target_query.strip():
        return {
            "status": "NOT_REQUESTED",
            "match_rule": "EXACT_NORMALIZED_BIOLOGICAL_TARGET_ONLY",
            "query_sha256": None,
            "matches": [],
            "human_selection_required": True,
            "inserted_into_study": False,
        }
    normalized = _normalize_target(target_query)
    query_hash = hashlib.sha256(target_query.encode("utf-8")).hexdigest()
    matches: list[MappingRecord] = []
    for declared_id, raw in (mapping_records or {}).items():
        if not isinstance(raw, Mapping):
            raise ValueError(f"stored mapping record {declared_id!r} is not an object")
        record = MappingRecord.from_dict(raw)
        if record.mapping_id != str(declared_id):
            raise ValueError("stored mapping key does not match mapping_id")
        if record.review_status not in _USABLE_REVIEW_STATES:
            continue
        if _normalize_target(record.biological_target) == normalized:
            matches.append(record)
    matches.sort(key=lambda record: (record.mapping_id, record.version, record.record_hash))
    return {
        "status": "EXACT_REVIEWED_MATCHES" if matches else "NO_EXACT_REVIEWED_MATCH",
        "match_rule": "EXACT_NORMALIZED_BIOLOGICAL_TARGET_ONLY",
        "query_sha256": query_hash,
        "matches": [
            {
                "mapping_id": record.mapping_id,
                "version": record.version,
                "biological_target": record.biological_target,
                "backend": record.backend,
                "id_namespace": record.id_namespace,
                "dataset_id": record.dataset_id,
                "intervention_type": record.intervention_type,
                "target_ids": list(record.target_ids),
                "review_status": record.review_status,
                "reviewer": record.reviewer,
                "reviewed_at": record.reviewed_at,
                "sources": [
                    {key: item[key] for key in ("citation", "locator", "url", "doi") if key in item}
                    for item in record.sources
                ],
                "context": dict(record.context),
                "limitations": list(record.limitations),
                "record_hash": record.record_hash,
            }
            for record in matches
        ],
        "human_selection_required": True,
        "inserted_into_study": False,
    }


__all__ = ["resolve_reviewed_mappings"]
