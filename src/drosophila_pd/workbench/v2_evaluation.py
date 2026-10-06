"""Leakage-aware offline evaluation for Workbench V2 retrieval and draft artifacts.

This module scores already-produced artifacts. It never calls a model, reads a
corpus, runs a simulation, or accesses benchmark labels.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping
from typing import Any


EVALUATION_SCHEMA = "workbench-v2-ai-evaluation-1"
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_OUTCOME_ID_MARKERS = re.compile(
    r"(^|[._:-])(positive|negative|responder|nonresponder|phenotype|outcome|"
    r"heldout|held-out|label|result|effect)(?=$|[._:-])",
    re.IGNORECASE,
)
_ALLOWED_SPLITS = {"development", "synthetic_fixture"}
_FIELDS = {
    "title", "hypothesis", "falsifiable_prediction", "assay",
    "primary_metric", "primary_metric_unit", "context",
}
_OUTPUT_KEYS = {
    "case_id", "expected_relevant_evidence_ids", "expected_fields",
    "field_support", "expected_abstention", "forbidden_evidence_ids",
    "retrieval", "draft",
}
_DRAFT_KEYS = {
    "status", "proposed_fields", "field_citations", "approved",
    "study_created", "mapping_created", "job_created", "graph_used",
    "simulation_started",
}
_FORBIDDEN_DRAFT_STATES = (
    "approved", "study_created", "mapping_created", "job_created",
    "graph_used", "simulation_started",
)


class EvaluationContractError(ValueError):
    """Raised when an evaluation bundle is malformed or outside the allowed split."""


def _safe_ids(value: Any, field: str) -> list[str]:
    if not isinstance(value, list):
        raise EvaluationContractError(f"{field} must be a list")
    if any(
        not isinstance(item, str)
        or not _SAFE_ID.fullmatch(item)
        or _OUTCOME_ID_MARKERS.search(item)
        for item in value
    ):
        raise EvaluationContractError(f"{field} contains an invalid opaque ID")
    if len(set(value)) != len(value):
        raise EvaluationContractError(f"{field} must not contain duplicate IDs")
    return list(value)


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _ndcg_at_k(ranked_ids: list[str], relevant_ids: set[str], k: int) -> float:
    dcg = sum(
        1.0 / math.log2(rank + 1)
        for rank, evidence_id in enumerate(ranked_ids[:k], start=1)
        if evidence_id in relevant_ids
    )
    ideal_hits = min(len(relevant_ids), k)
    ideal = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
    return dcg / ideal if ideal else 0.0


def evaluate_ai_v2_bundle(bundle: Mapping[str, Any], *, k: int = 5) -> dict[str, Any]:
    """Score retrieval/draft outputs against an explicitly permitted reference set.

    ``field_support`` is a project-authored reference annotation. Citation
    alignment is not a machine judgement that the cited prose entails a claim.
    """
    if not isinstance(bundle, Mapping):
        raise EvaluationContractError("bundle must be an object")
    expected_root = {"schema_version", "evaluation_id", "evaluation_split", "cases"}
    if set(bundle) != expected_root:
        raise EvaluationContractError("bundle keys do not match the evaluation schema")
    if bundle["schema_version"] != EVALUATION_SCHEMA:
        raise EvaluationContractError("unsupported evaluation schema_version")
    evaluation_id = bundle["evaluation_id"]
    if not isinstance(evaluation_id, str) or not _SAFE_ID.fullmatch(evaluation_id):
        raise EvaluationContractError("evaluation_id must be a safe opaque ID")
    if _OUTCOME_ID_MARKERS.search(evaluation_id):
        raise EvaluationContractError("evaluation_id must not encode outcome or split labels")
    split = bundle["evaluation_split"]
    if not isinstance(split, str) or split not in _ALLOWED_SPLITS:
        raise EvaluationContractError(
            "only development or synthetic_fixture evaluation is permitted; held-out is locked"
        )
    if isinstance(k, bool) or not isinstance(k, int) or k < 1:
        raise EvaluationContractError("k must be a positive integer")
    cases = bundle["cases"]
    if not isinstance(cases, list) or not cases:
        raise EvaluationContractError("cases must be a non-empty list")

    seen_case_ids: set[str] = set()
    retrieval_recalls: list[float] = []
    reciprocal_ranks: list[float] = []
    ndcgs: list[float] = []
    abstention_results: list[float] = []
    field_coverage: list[float] = []
    field_precision: list[float] = []
    citation_alignment: list[float] = []
    citation_membership: list[float] = []
    safe_draft_results: list[float] = []
    total_forbidden_hits = 0
    forbidden_cases = 0
    citation_pair_count = 0
    citation_alignment_field_count = 0
    per_case: list[dict[str, Any]] = []

    for case in cases:
        if not isinstance(case, Mapping) or set(case) != _OUTPUT_KEYS:
            raise EvaluationContractError("each case must match the exact case schema")
        case_id = case["case_id"]
        if (not isinstance(case_id, str) or not _SAFE_ID.fullmatch(case_id)
                or _OUTCOME_ID_MARKERS.search(case_id) or case_id in seen_case_ids):
            raise EvaluationContractError("case_id must be unique and a safe opaque ID")
        seen_case_ids.add(case_id)

        relevant = _safe_ids(case["expected_relevant_evidence_ids"], "expected_relevant_evidence_ids")
        forbidden = _safe_ids(case["forbidden_evidence_ids"], "forbidden_evidence_ids")
        if set(relevant) & set(forbidden):
            raise EvaluationContractError("an evidence ID cannot be both relevant and forbidden")
        expected_fields = case["expected_fields"]
        if (not isinstance(expected_fields, list)
                or any(not isinstance(name, str) or name not in _FIELDS for name in expected_fields)
                or len(set(expected_fields)) != len(expected_fields)):
            raise EvaluationContractError("expected_fields contains an invalid or duplicate field")
        field_support = case["field_support"]
        if not isinstance(field_support, Mapping) or set(field_support) - set(expected_fields):
            raise EvaluationContractError("field_support must annotate only expected fields")
        normalized_support: dict[str, set[str]] = {}
        for field, ids in field_support.items():
            values = _safe_ids(ids, f"field_support.{field}")
            if not values or not set(values) <= set(relevant):
                raise EvaluationContractError("field_support IDs must be non-empty relevant evidence IDs")
            normalized_support[field] = set(values)

        expect_abstention = case["expected_abstention"]
        if not isinstance(expect_abstention, bool):
            raise EvaluationContractError("expected_abstention must be boolean")
        if expect_abstention != (len(relevant) == 0):
            raise EvaluationContractError("expected_abstention must agree with the relevant evidence set")

        retrieval = case["retrieval"]
        if not isinstance(retrieval, Mapping) or set(retrieval) != {"status", "evidence_ids"}:
            raise EvaluationContractError("retrieval output has an invalid schema")
        status = retrieval["status"]
        ranked = _safe_ids(retrieval["evidence_ids"], "retrieval.evidence_ids")
        if not isinstance(status, str) or status not in {"RETRIEVED", "NO_APPROVED_EVIDENCE"}:
            raise EvaluationContractError("retrieval status is not recognized")
        if (status == "NO_APPROVED_EVIDENCE") != (len(ranked) == 0):
            raise EvaluationContractError("retrieval status and returned evidence IDs disagree")

        draft = case["draft"]
        if not isinstance(draft, Mapping) or set(draft) != _DRAFT_KEYS:
            raise EvaluationContractError("draft output has an invalid schema")
        if not isinstance(draft["status"], str) or not draft["status"]:
            raise EvaluationContractError("draft status must be non-empty")
        proposed = draft["proposed_fields"]
        citations = draft["field_citations"]
        if not isinstance(proposed, Mapping) or set(proposed) - _FIELDS:
            raise EvaluationContractError("draft contains unknown proposed fields")
        if not isinstance(citations, Mapping) or set(citations) - _FIELDS:
            raise EvaluationContractError("draft contains unknown citation fields")
        normalized_citations: dict[str, list[str]] = {}
        for field, ids in citations.items():
            normalized_citations[field] = _safe_ids(ids, f"field_citations.{field}")
        for flag in _FORBIDDEN_DRAFT_STATES:
            if not isinstance(draft[flag], bool):
                raise EvaluationContractError(f"draft.{flag} must be boolean")
        safe_draft = not any(draft[flag] for flag in _FORBIDDEN_DRAFT_STATES)
        safe_draft_results.append(float(safe_draft))

        ranked_top_k = ranked[:k]
        relevant_set = set(relevant)
        if relevant:
            hits = [index for index, evidence_id in enumerate(ranked_top_k, start=1)
                    if evidence_id in relevant_set]
            retrieval_recalls.append(len(set(ranked_top_k) & relevant_set) / len(relevant_set))
            reciprocal_ranks.append(1.0 / hits[0] if hits else 0.0)
            ndcgs.append(_ndcg_at_k(ranked, relevant_set, k))
        abstention_correct = (not ranked) if expect_abstention else bool(ranked)
        abstention_results.append(float(abstention_correct))

        forbidden_hits = set(ranked) & set(forbidden)
        total_forbidden_hits += len(forbidden_hits)
        forbidden_cases += int(bool(forbidden_hits))

        expected_field_set = set(expected_fields)
        proposed_field_set = set(proposed)
        field_coverage.append(
            len(proposed_field_set & expected_field_set) / len(expected_field_set)
            if expected_field_set else 1.0
        )
        field_precision.append(
            len(proposed_field_set & expected_field_set) / len(proposed_field_set)
            if proposed_field_set else (1.0 if not expected_field_set else 0.0)
        )
        annotated_fields = set(normalized_support)
        aligned = [
            bool(set(normalized_citations.get(field, ())) & normalized_support[field])
            for field in proposed_field_set & annotated_fields
        ]
        if aligned:
            citation_alignment.append(sum(aligned) / len(aligned))
            citation_alignment_field_count += len(aligned)

        citation_ids = [evidence_id for ids in normalized_citations.values() for evidence_id in ids]
        if citation_ids:
            citation_pair_count += len(citation_ids)
            citation_membership.append(
                sum(evidence_id in set(ranked) for evidence_id in citation_ids) / len(citation_ids)
            )
        per_case.append({
            "case_id": case_id,
            "relevant_evidence_count": len(relevant),
            "retrieved_evidence_count": len(ranked),
            "recall_at_k": (len(set(ranked_top_k) & relevant_set) / len(relevant_set)) if relevant else None,
            "reciprocal_rank": reciprocal_ranks[-1] if relevant else None,
            "ndcg_at_k": ndcgs[-1] if relevant else None,
            "abstention_correct": abstention_correct,
            "forbidden_evidence_ids_returned": sorted(forbidden_hits),
            "expected_field_coverage": field_coverage[-1],
            "expected_field_precision": field_precision[-1],
            "reference_citation_alignment": sum(aligned) / len(aligned) if aligned else None,
            "citation_retrieval_membership": (
                sum(evidence_id in set(ranked) for evidence_id in citation_ids) / len(citation_ids)
                if citation_ids else None
            ),
            "draft_non_executable_invariant_pass": safe_draft,
        })

    canonical_bundle = json.dumps(
        bundle, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    report = {
        "schema_version": "workbench-v2-ai-evaluation-report-1",
        "evaluation_id": evaluation_id,
        "evaluation_split": split,
        "evaluation_case_count": len(cases),
        "input_bundle_sha256": hashlib.sha256(canonical_bundle).hexdigest(),
        "k": k,
        "metric_denominators": {
            "retrieval_ranking_cases": len(retrieval_recalls),
            "abstention_cases": len(abstention_results),
            "field_cases": len(field_coverage),
            "citation_alignment_fields": citation_alignment_field_count,
            "citation_pairs": citation_pair_count,
            "non_executable_invariant_cases": len(safe_draft_results),
        },
        "metrics": {
            "retrieval_recall_at_k_macro": _mean(retrieval_recalls),
            "retrieval_mrr": _mean(reciprocal_ranks),
            "retrieval_ndcg_at_k_macro": _mean(ndcgs),
            "abstention_accuracy": _mean(abstention_results),
            "forbidden_evidence_case_count": forbidden_cases,
            "forbidden_evidence_hit_count": total_forbidden_hits,
            "expected_field_coverage": _mean(field_coverage),
            "expected_field_precision": _mean(field_precision),
            "reference_citation_alignment": _mean(citation_alignment),
            "citation_retrieval_membership": _mean(citation_membership),
            "draft_non_executable_invariant_pass_rate": _mean(safe_draft_results),
        },
        "interpretation_limits": {
            "citation_alignment": "Matches project-authored field/evidence reference IDs; does not measure semantic entailment.",
            "expected_field_metrics": "Measure structured field coverage against the supplied reference; not biological correctness.",
            "synthetic_fixture": split == "synthetic_fixture",
            "biological_validity": "NOT_ASSESSED",
            "heldout_status": "LOCKED_NOT_RUN",
        },
        "cases": per_case,
    }
    canonical_report = json.dumps(
        report, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    report["report_sha256"] = hashlib.sha256(canonical_report).hexdigest()
    return report


__all__ = ["EVALUATION_SCHEMA", "EvaluationContractError", "evaluate_ai_v2_bundle"]
