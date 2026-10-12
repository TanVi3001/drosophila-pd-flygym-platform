"""Auditable, human-reference evaluation for AI V2 assistant outputs.

The evaluator has no model-as-judge path. Human-approved development bundles
are required for scientific-quality reporting; synthetic bundles exercise only
the evaluator plumbing and are labeled as such in every result.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REQUIRED_SYSTEMS = {"manual_template", "llm_no_retrieval", "llm_rag"}


def evaluate_assistant_bundle(bundle: Mapping[str, Any], *, k: int = 5) -> dict[str, Any]:
    """Score a frozen Q&A bundle on a DEVELOPMENT partition only.

    Expected human gold fields are question-specific. Claim support annotations
    must come from human reviewers, never from another LLM.
    """

    if not isinstance(bundle, Mapping):
        raise TypeError("evaluation bundle must be an object")
    if k < 1:
        raise ValueError("k must be positive")
    if bundle.get("schema_version") != "ai-v2-assistant-evaluation-input-1":
        raise ValueError("unsupported evaluation bundle schema")
    if bundle.get("partition") != "DEVELOPMENT":
        raise ValueError("assistant evaluation accepts DEVELOPMENT only; validation partitions are locked")
    mode = bundle.get("evaluation_mode")
    if mode == "APPROVED_DEVELOPMENT":
        _validate_approved_bundle(bundle, k=k)
        result_status = "MEASURED_APPROVED_DEVELOPMENT"
    elif mode == "OWNER_REVIEWED_DEMO":
        _validate_owner_demo_bundle(bundle, k=k)
        result_status = "MEASURED_OWNER_REVIEWED_DEMO_NOT_INDEPENDENT"
    elif mode == "SYNTHETIC_TEST_ONLY" and bundle.get("synthetic_fixture") is True:
        result_status = "SYNTHETIC_TEST_ONLY"
    else:
        raise ValueError(
            "evaluation mode must be approved development, owner-reviewed demo, "
            "or explicitly synthetic test only"
        )

    cases_raw = bundle.get("cases")
    systems_raw = bundle.get("systems")
    if not isinstance(cases_raw, Sequence) or isinstance(cases_raw, (str, bytes)) or not cases_raw:
        raise ValueError("cases must be a non-empty list")
    if not isinstance(systems_raw, Sequence) or isinstance(systems_raw, (str, bytes)) or not systems_raw:
        raise ValueError("systems must be a non-empty list")
    cases: dict[str, Mapping[str, Any]] = {}
    for row in cases_raw:
        if not isinstance(row, Mapping):
            raise ValueError("each case must be an object")
        case_id = _required_text(row.get("case_id"), "case_id")
        if case_id in cases:
            raise ValueError(f"duplicate case_id: {case_id}")
        required = row.get("required_fields")
        gold_fields = row.get("gold_fields")
        if not isinstance(required, Sequence) or isinstance(required, (str, bytes)) or not required:
            raise ValueError(f"case {case_id} must list required_fields")
        if not isinstance(gold_fields, Mapping) or any(field not in gold_fields for field in required):
            raise ValueError(f"case {case_id} lacks gold values for required_fields")
        cases[case_id] = row

    systems: dict[str, Mapping[str, Any]] = {}
    for system in systems_raw:
        if not isinstance(system, Mapping):
            raise ValueError("each system must be an object")
        system_id = _required_text(system.get("system_id"), "system_id")
        if system_id in systems:
            raise ValueError(f"duplicate system_id: {system_id}")
        systems[system_id] = system
    reviewed_modes = {"APPROVED_DEVELOPMENT", "OWNER_REVIEWED_DEMO"}
    if mode in reviewed_modes and not _REQUIRED_SYSTEMS.issubset(systems):
        raise ValueError("reviewed comparison must include manual_template, llm_no_retrieval, and llm_rag")
    if mode in reviewed_modes:
        for system_id in ("llm_no_retrieval", "llm_rag"):
            for field in ("provider_id", "model_id", "prompt_version"):
                value = _required_text(systems[system_id].get(field), f"{system_id}.{field}")
                _reject_secret_like_value(value, f"{system_id}.{field}")

    owner_demo_reviewer = (
        str(bundle["reviewer_ids"][0]).strip()
        if mode == "OWNER_REVIEWED_DEMO"
        else None
    )
    per_system = []
    for system_id in sorted(systems):
        per_system.append(_score_system(
            system_id,
            systems[system_id],
            cases,
            k=k,
            expected_claim_reviewer=owner_demo_reviewer,
        ))
    bundle_digest = hashlib.sha256(
        json.dumps(bundle, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    return {
        "schema_version": "ai-v2-assistant-evaluation-result-2",
        "evaluation_status": result_status,
        "partition": "DEVELOPMENT",
        "case_count": len(cases),
        "system_count": len(systems),
        "retrieval_k": k,
        "reviewer_count": len(bundle.get("reviewer_ids", [])),
        "review_claim": (
            "single owner reviewer; not independent"
            if mode == "OWNER_REVIEWED_DEMO"
            else "two distinct human reviewers required"
            if mode == "APPROVED_DEVELOPMENT"
            else "synthetic fixture; no human-quality claim"
        ),
        "input_bundle_sha256": bundle_digest,
        "systems": per_system,
        "scoring_policy": {
            "reference": "human-annotated gold fields/evidence and claim support",
            "llm_as_judge": False,
            "unsupported_claim_rate": "unsupported determinate claims / determinate human-reviewed claims",
            "field_accuracy": "exact match over every declared required field and case",
            "retrieval_metrics": "RAG-only gold-set relevance; macro-average over non-empty-gold cases; non-gold chunks are unjudged; other arms are N/A",
            "schema_validity": "raw response and processed draft are separate; denominators/status counts preserve errors, no-response, not-called, and not-run",
            "claim_boundary": "assistant quality metrics do not establish biological validity or wet-lab utility",
        },
    }


def _validate_approved_bundle(bundle: Mapping[str, Any], *, k: int) -> None:
    _validate_frozen_bundle_inputs(bundle, k=k)
    reviewers = _reviewer_ids(bundle)
    if len(reviewers) < 2:
        raise ValueError("at least two distinct human reviewers are required for the gold bundle")


def _validate_owner_demo_bundle(bundle: Mapping[str, Any], *, k: int) -> None:
    _validate_frozen_bundle_inputs(bundle, k=k)
    if bundle.get("owner_demo") is not True:
        raise ValueError("owner-reviewed demo requires owner_demo=true")
    if bundle.get("independent_review_claim") is not False:
        raise ValueError("single-reviewer demo must explicitly set independent_review_claim=false")
    reviewers = _reviewer_ids(bundle)
    reviewer_rows = bundle.get("reviewer_ids")
    if len(reviewers) != 1 or len(reviewer_rows) != 1:
        raise ValueError("owner-reviewed demo requires exactly one named reviewer")


def _validate_frozen_bundle_inputs(bundle: Mapping[str, Any], *, k: int) -> None:
    for field in ("corpus_sha256", "rubric_sha256", "evaluation_protocol_sha256"):
        if not isinstance(bundle.get(field), str) or not _SHA256.fullmatch(str(bundle[field])):
            raise ValueError(f"{field} must be a frozen lowercase SHA-256")
    if bundle.get("corpus_status") != "APPROVED" or bundle.get("rubric_status") != "APPROVED":
        raise ValueError("approved corpus and human reference rubric are required")
    if bundle.get("provider_policy_approved") is not True:
        raise ValueError("provider/privacy policy approval is required before real-provider evaluation")
    if bundle.get("synthetic_fixture") is True:
        raise ValueError("synthetic fixtures cannot be labeled as an approved real evaluation")
    if bundle.get("retrieval_k") != k:
        raise ValueError("retrieval k differs from the frozen evaluation protocol")


def _reviewer_ids(bundle: Mapping[str, Any]) -> set[str]:
    reviewers = bundle.get("reviewer_ids")
    if not isinstance(reviewers, Sequence) or isinstance(reviewers, (str, bytes)):
        raise ValueError("reviewer_ids must identify human reviewers")
    normalized = [str(item).strip() for item in reviewers]
    if any(not item for item in normalized):
        raise ValueError("reviewer_ids must be non-empty")
    return set(normalized)


def _score_system(
    system_id: str,
    system: Mapping[str, Any],
    cases: Mapping[str, Mapping[str, Any]],
    *,
    k: int,
    expected_claim_reviewer: str | None = None,
) -> dict[str, Any]:
    outputs_raw = system.get("outputs")
    if not isinstance(outputs_raw, Sequence) or isinstance(outputs_raw, (str, bytes)):
        raise ValueError(f"system {system_id} outputs must be a list")
    outputs: dict[str, Mapping[str, Any]] = {}
    for output in outputs_raw:
        if not isinstance(output, Mapping):
            raise ValueError(f"system {system_id} contains a non-object output")
        case_id = _required_text(output.get("case_id"), "output.case_id")
        if case_id not in cases:
            raise ValueError(f"system {system_id} produced an out-of-bundle case: {case_id}")
        if case_id in outputs:
            raise ValueError(f"system {system_id} duplicated case: {case_id}")
        if _contains_forbidden_prediction_key(output):
            raise ValueError(f"system {system_id} output contains an outcome/label field")
        outputs[case_id] = output
    missing_outputs = set(cases) - set(outputs)
    if missing_outputs:
        raise ValueError(f"system {system_id} must emit an output or explicit abstention for every case")

    retrieval_precisions: list[float] = []
    retrieval_recalls: list[float] = []
    retrieval_relevant_hit_sum = retrieval_returned_hit_sum = retrieval_empty_gold_count = 0
    citation_correct = citation_total = 0
    field_correct = field_total = 0
    missing_tp = missing_fp = missing_fn = 0
    completed = 0
    status_counts: Counter[str] = Counter()
    raw_schema_statuses: Counter[str] = Counter()
    processed_schema_statuses: Counter[str] = Counter()
    raw_schema_valid_count = processed_schema_valid_count = 0
    raw_schema_responses = processed_schema_produced = 0
    unsupported = supported = uncertain = 0
    for case_id, case in cases.items():
        output = outputs[case_id]
        status = output.get("status")
        if status not in {"COMPLETED", "ABSTAINED", "ERROR", "NOT_RUN"}:
            raise ValueError(f"output {case_id} must state COMPLETED, ABSTAINED, ERROR, or NOT_RUN")
        status_counts[status] += 1
        completed += status == "COMPLETED"
        raw_schema_status = output.get("raw_schema_status")
        if raw_schema_status is None:
            raw_flag = output.get("raw_schema_valid")
            if raw_flag is True:
                raw_schema_status = "VALID"
            elif raw_flag is False:
                raw_schema_status = "INVALID"
            elif output.get("provider_attempted") is True:
                raw_schema_status = "NO_RESPONSE"
            elif output.get("provider_attempted") is False:
                raw_schema_status = "NOT_CALLED"
            else:
                raw_schema_status = "NOT_RECORDED"
        if raw_schema_status not in {"VALID", "INVALID", "NO_RESPONSE", "NOT_CALLED", "NOT_RUN",
                                     "NOT_APPLICABLE_MANUAL_TEMPLATE", "NOT_RECORDED"}:
            raise ValueError(f"output {case_id} has an unsupported raw_schema_status")
        raw_schema_statuses[raw_schema_status] += 1
        if raw_schema_status in {"VALID", "INVALID"}:
            raw_schema_responses += 1
            raw_schema_valid_count += raw_schema_status == "VALID"
        processed_schema_status = output.get("processed_schema_status")
        if processed_schema_status is None:
            processed_flag = output.get("schema_valid")
            if processed_flag is True:
                processed_schema_status = "VALID"
            elif processed_flag is False:
                processed_schema_status = "INVALID"
            elif status in {"ERROR", "NOT_RUN"}:
                processed_schema_status = "NOT_PRODUCED"
            else:
                processed_schema_status = "NOT_RECORDED"
        if processed_schema_status not in {"VALID", "INVALID", "NOT_PRODUCED", "NOT_APPLICABLE_MANUAL_TEMPLATE", "NOT_RECORDED"}:
            raise ValueError(f"output {case_id} has an unsupported processed_schema_status")
        processed_schema_statuses[processed_schema_status] += 1
        if processed_schema_status in {"VALID", "INVALID"}:
            processed_schema_produced += 1
            processed_schema_valid_count += processed_schema_status == "VALID"
        gold_chunks = set(_string_list(case.get("gold_evidence_chunk_ids", ()), f"{case_id}.gold_evidence_chunk_ids"))
        retrieved = _string_list(output.get("retrieved_chunk_ids", ()), f"{case_id}.retrieved_chunk_ids")[:k]
        if len(retrieved) != len(set(retrieved)):
            raise ValueError(f"output {case_id} contains duplicate retrieved chunk IDs")
        if system_id == "llm_rag" and gold_chunks:
            retrieved_set = set(retrieved)
            matches = len(retrieved_set & gold_chunks)
            retrieval_recalls.append(matches / len(gold_chunks))
            retrieval_precisions.append(matches / len(retrieved) if retrieved else 0.0)
            retrieval_relevant_hit_sum += matches
            retrieval_returned_hit_sum += len(retrieved)
        elif system_id == "llm_rag":
            retrieval_empty_gold_count += 1

        gold_citations = {
            (str(item.get("source_id", "")), str(item.get("chunk_id", "")))
            for item in case.get("gold_citations", ()) if isinstance(item, Mapping)
        }
        citations = output.get("citations", ())
        if not isinstance(citations, Sequence) or isinstance(citations, (str, bytes)):
            raise ValueError(f"output {case_id}.citations must be a list")
        for citation in citations:
            if not isinstance(citation, Mapping):
                citation_total += 1
                continue
            citation_total += 1
            pair = (str(citation.get("source_id", "")), str(citation.get("chunk_id", "")))
            citation_correct += pair in gold_citations

        predicted_fields = output.get("fields", {})
        if not isinstance(predicted_fields, Mapping):
            raise ValueError(f"output {case_id}.fields must be an object")
        gold_fields = case["gold_fields"]
        for field_name in case["required_fields"]:
            field_total += 1
            field_correct += status == "COMPLETED" and predicted_fields.get(field_name) == gold_fields[field_name]

        expected_missing = set(_string_list(case.get("gold_missing_fields", ()), f"{case_id}.gold_missing_fields"))
        predicted_missing = set(_string_list(output.get("missing_fields", ()), f"{case_id}.missing_fields"))
        missing_tp += len(expected_missing & predicted_missing)
        missing_fp += len(predicted_missing - expected_missing)
        missing_fn += len(expected_missing - predicted_missing)
        claims = output.get("claim_reviews", ())
        if not isinstance(claims, Sequence) or isinstance(claims, (str, bytes)):
            raise ValueError(f"output {case_id}.claim_reviews must be a list")
        for claim in claims:
            if not isinstance(claim, Mapping) or not claim.get("reviewer_ids"):
                raise ValueError(f"claim reviews require human reviewer_ids for {case_id}")
            if expected_claim_reviewer is not None:
                claim_reviewers = claim.get("reviewer_ids")
                if (
                    not isinstance(claim_reviewers, Sequence)
                    or isinstance(claim_reviewers, (str, bytes))
                    or list(claim_reviewers) != [expected_claim_reviewer]
                ):
                    raise ValueError(
                        f"owner-reviewed demo claim annotations must name only "
                        f"{expected_claim_reviewer!r} for {case_id}"
                    )
            decision = claim.get("support_status")
            if decision == "SUPPORTED":
                supported += 1
            elif decision == "UNSUPPORTED":
                unsupported += 1
            elif decision == "UNCERTAIN":
                uncertain += 1
            else:
                raise ValueError("claim support_status must be SUPPORTED, UNSUPPORTED, or UNCERTAIN")

    field_accuracy = field_correct / field_total if field_total else None
    missing_precision = missing_tp / (missing_tp + missing_fp) if missing_tp + missing_fp else 0.0
    missing_recall = missing_tp / (missing_tp + missing_fn) if missing_tp + missing_fn else 0.0
    missing_f1 = (2 * missing_precision * missing_recall / (missing_precision + missing_recall)
                  if missing_precision + missing_recall else 0.0)
    determinate_claims = supported + unsupported
    return {
        "system_id": system_id,
        "provider_id": system.get("provider_id"),
        "model_id": system.get("model_id"),
        "prompt_version": system.get("prompt_version"),
        "case_count": len(cases),
        "completed_count": completed,
        "abstained_count": status_counts["ABSTAINED"],
        "error_count": status_counts["ERROR"],
        "not_run_count": status_counts["NOT_RUN"],
        "status_counts": dict(status_counts),
        "coverage": completed / len(cases),
        "schema_valid_count": processed_schema_valid_count,
        "schema_valid_rate": processed_schema_valid_count / len(cases),
        "schema_validity": {
            "raw_output": {
                "status_counts": dict(raw_schema_statuses),
                "response_denominator": raw_schema_responses,
                "valid_count": raw_schema_valid_count,
                "valid_rate_among_responses": raw_schema_valid_count / raw_schema_responses if raw_schema_responses else None,
                "case_denominator": len(cases),
                "valid_rate_per_case": raw_schema_valid_count / len(cases),
            },
            "processed_draft": {
                "status_counts": dict(processed_schema_statuses),
                "produced_denominator": processed_schema_produced,
                "valid_count": processed_schema_valid_count,
                "valid_rate_among_produced": processed_schema_valid_count / processed_schema_produced if processed_schema_produced else None,
                "case_denominator": len(cases),
                "valid_rate_per_case": processed_schema_valid_count / len(cases),
            },
        },
        "retrieval_assessable_case_count": len(retrieval_recalls),
        "recall_at_k": _mean_or_none(retrieval_recalls),
        "precision_at_k": _mean_or_none(retrieval_precisions),
        "precision_at_k_case_denominator": len(retrieval_precisions),
        "precision_relevant_hit_numerator_sum": retrieval_relevant_hit_sum,
        "precision_returned_hit_denominator_sum": retrieval_returned_hit_sum,
        "precision_relevance_basis": "gold-set chunk IDs only; non-gold chunks are unjudged",
        "precision_formula": "macro mean of |returned_top_k ∩ gold_ids| / |actual returned hits| over non-empty-gold cases; zero returned hits scores 0",
        "empty_gold_retrieval_cases_excluded": retrieval_empty_gold_count if system_id == "llm_rag" else None,
        "citation_count": citation_total,
        "citation_precision": citation_correct / citation_total if citation_total else None,
        "field_correct_count": field_correct,
        "field_denominator": field_total,
        "required_field_exact_accuracy": field_accuracy,
        "missing_field_detection": {
            "true_positive": missing_tp,
            "false_positive": missing_fp,
            "false_negative": missing_fn,
            "precision": missing_precision,
            "recall": missing_recall,
            "f1": missing_f1,
        },
        "claim_review": {
            "supported": supported,
            "unsupported": unsupported,
            "uncertain": uncertain,
            "determinate_denominator": determinate_claims,
            "unsupported_claim_rate": unsupported / determinate_claims if determinate_claims else None,
            "human_annotated": True,
        },
    }


def _mean_or_none(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _required_text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")
    return value.strip()


def _reject_secret_like_value(value: str, name: str) -> None:
    lowered = value.casefold()
    markers = ("bearer ", "api_key", "api-key", "secret=", "token=", "sk-", "ghp_", "github_pat_")
    if any(marker in lowered for marker in markers):
        raise ValueError(f"{name} looks like it contains a secret; store only provider/model identifiers")


def _string_list(value: Any, name: str) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{name} must be a list")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"{name} must contain non-empty strings")
    return [item.strip() for item in value]


def _contains_forbidden_prediction_key(value: Any) -> bool:
    forbidden = {"label", "outcome", "phenotype", "response_class", "responder_status", "gold_fields"}
    if isinstance(value, Mapping):
        return any(str(key).strip().casefold() in forbidden or _contains_forbidden_prediction_key(item)
                   for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return any(_contains_forbidden_prediction_key(item) for item in value)
    return False


__all__ = ["evaluate_assistant_bundle"]
