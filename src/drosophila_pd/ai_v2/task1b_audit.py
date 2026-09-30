"""Post-Task-1 development-only sanitization and CV diagnostics; no model fitting."""

from __future__ import annotations

import collections
import hashlib
import json
import random
from pathlib import Path

from .access import AccessClass, DevelopmentDataAccess
from .cv import canonical_hash, load_cv


TASK1_CONFIG_SHA256 = "55909e29f6f876407965e50f1be9b2cb61cf6e4da86624c3c9041f4c909ca137"
TASK1_FOLD_SHA256 = "6b054c6ff0a6669cb6038b0cd365a6787f5fa5f2d0e5018094badd6cce256dab"
GRAPH_SHA256 = "94db8c650533bc36ffa3223f2e62325d5648b8d6bd31c3a4e1c804628c7557b3"
MAPPING_SHA256 = "67291ca3b68b79b2ec1d6f32c3ba7fcc938cbcffe1c25e867b39afc9e7e89165"
DEV_ABLATION_SHA256 = "7be3413b85be977a0eede4a57e6d0f682a9e1837f8431f8a04a9245311865fef"
STRATIFIED_SEED = 20260930


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def compact_json(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True) + "\n").encode("utf-8")


def _assert_no_label_fields(value: object) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = str(key).casefold().replace("_", "")
            if any(token in normalized for token in ("label", "outcome", "phenotype", "responseclass", "groundtruth")):
                raise ValueError("sanitized development input contains a prohibited field")
            _assert_no_label_fields(nested)
    elif isinstance(value, list):
        for nested in value:
            _assert_no_label_fields(nested)


def load_sanitized_development_inputs(
    access: DevelopmentDataAccess,
    *,
    approved_ids: tuple[str, ...],
    manifest_path: Path,
    effect_path: Path,
    mapping_path: Path,
) -> tuple[dict[str, object], dict[str, object]]:
    """Read only exact allowlisted DEV artifacts; suitable for future runners."""
    if len(approved_ids) != 74 or len(set(approved_ids)) != 74:
        raise ValueError("approved development IDs must contain exactly 74 cases")
    manifest = json.loads(access.read_bytes(AccessClass.DEVELOPMENT_INPUT, manifest_path))
    root = manifest_path.resolve(strict=True).parents[2]
    relative_paths = []
    artifacts = manifest.get("artifacts", {})
    payloads = []
    for path in (effect_path, mapping_path):
        relative = path.resolve(strict=True).relative_to(root).as_posix()
        relative_paths.append(relative)
        expected = artifacts.get(relative)
        content = access.read_bytes(AccessClass.DEVELOPMENT_INPUT, path)
        if not expected or hash_bytes(content) != expected:
            raise ValueError("sanitized artifact checksum mismatch")
        payloads.append(json.loads(content))
    effects, mapping = payloads
    allowed = set(approved_ids)
    if manifest.get("partition") != "DEVELOPMENT" or manifest.get("case_count") != 74:
        raise ValueError("sanitized manifest is not the approved development partition")
    if effects.get("partition") != "DEVELOPMENT" or mapping.get("partition") != "DEVELOPMENT":
        raise ValueError("sanitized artifacts must declare DEVELOPMENT partition")
    _assert_no_label_fields(effects)
    _assert_no_label_fields(mapping)
    effect_rows = effects.get("features", [])
    mapping_rows = mapping.get("mappings", [])
    if len(effect_rows) != 74 or len(mapping_rows) != 74:
        raise ValueError("sanitized artifacts must contain exactly 74 rows")
    effect_ids = [row.get("case_id") for row in effect_rows]
    mapping_ids = [row.get("case_id") for row in mapping_rows]
    if len(set(effect_ids)) != 74 or len(set(mapping_ids)) != 74 or set(effect_ids) != allowed or set(mapping_ids) != allowed:
        raise ValueError("sanitized artifact IDs do not equal the approved DEV set")
    if any(set(row) != {"case_id", "effect_hz"} for row in effect_rows):
        raise ValueError("effect feature artifact contains an unexpected field")
    if manifest_path.name != "sanitized_manifest_v1.json" or relative_paths[0] == relative_paths[1]:
        raise ValueError("unexpected sanitized manifest/artifact identity")
    return effects, mapping


def create_stratified_cv(ids: tuple[str, ...], labels: dict[str, int], *, seed: int = STRATIFIED_SEED) -> dict[str, object]:
    if len(ids) != 74 or len(set(ids)) != 74 or set(labels) != set(ids) or set(labels.values()) != {0, 1}:
        raise ValueError("stratified CV requires exactly the 74 labeled DEV IDs")
    positive = sorted(case for case in ids if labels[case] == 1)
    negative = sorted(case for case in ids if labels[case] == 0)
    rng = random.Random(seed)
    rng.shuffle(positive)
    rng.shuffle(negative)
    folds: list[list[str]] = [[] for _ in range(5)]
    for group in (positive, negative):
        for position, case in enumerate(group):
            folds[position % 5].append(case)
    folds = [sorted(fold) for fold in folds]
    flattened = [case for fold in folds for case in fold]
    if len(flattened) != 74 or len(set(flattened)) != 74 or set(flattened) != set(ids):
        raise ValueError("stratified CV lost or duplicated a development case")
    counts = [{"fold": index, "case_count": len(fold), "positive_count": sum(labels[case] for case in fold), "negative_count": len(fold) - sum(labels[case] for case in fold), "positive_prevalence": sum(labels[case] for case in fold) / len(fold)} for index, fold in enumerate(folds)]
    return {"schema_version": "ai-v2-dev-stratified-cv-v2", "partition": "DEVELOPMENT", "seed": seed, "case_count": 74, "positive_count": len(positive), "negative_count": len(negative), "case_ids": sorted(ids), "folds": folds, "fold_class_counts": counts, "development_split_sha256": canonical_hash(sorted(ids)), "fold_membership_sha256": canonical_hash(folds), "created_after_task1_results": True, "purpose": "ROBUSTNESS_DIAGNOSTIC_NOT_REPLACEMENT", "creation_reason": "Original fixed folds had uneven positive prevalence; this label-stratified manifest is a post-Task-1 diagnostic, not a replacement or retrospective correction.", "task1_original_fold_membership_sha256": TASK1_FOLD_SHA256, "execution_status": "NOT_EXECUTED"}


def sanitize_development_inputs(
    access: DevelopmentDataAccess,
    *,
    approved_ids: tuple[str, ...],
    dev_ablation_path: Path,
    mapping_path: Path,
    original_cv_path: Path,
) -> tuple[dict[str, object], dict[str, object], dict[str, object], list[dict[str, float | int]]]:
    if len(approved_ids) != 74 or len(set(approved_ids)) != 74:
        raise ValueError("approved development set must be exactly 74 unique IDs")
    if hash_bytes(access.read_bytes(AccessClass.DEVELOPMENT_LABEL, dev_ablation_path)) != DEV_ABLATION_SHA256:
        raise ValueError("development ablation artifact hash mismatch")
    # The source file also contains unlabeled scores for non-DEV rows. Only this
    # 74-row evaluator-owned development collection is projected below.
    dev = json.loads(access.read_bytes(AccessClass.DEVELOPMENT_LABEL, dev_ablation_path))
    evaluated = dev["comparison"]["systems"]["rewire_effect_only"]["evaluated_cases"]
    rows = {item["case_id"]: item for item in evaluated}
    if len(evaluated) != 74 or len(rows) != 74 or set(rows) != set(approved_ids) or dev["evaluation_split"] != "development":
        raise ValueError("development evaluator rows do not equal the approved partition")
    labels = {case: {"positive": 1, "negative": 0}[rows[case]["reference_label"]] for case in approved_ids}
    effects = {"schema_version": "ai-v2-dev-effect-features-v1", "partition": "DEVELOPMENT", "source_sha256": DEV_ABLATION_SHA256, "case_count": 74, "features": [{"case_id": case, "effect_hz": float(rows[case]["ranking_score"])} for case in sorted(approved_ids)]}
    if hash_bytes(access.read_bytes(AccessClass.DEVELOPMENT_INPUT, mapping_path)) != MAPPING_SHA256:
        raise ValueError("mapping registry hash mismatch")
    registry = json.loads(access.read_bytes(AccessClass.DEVELOPMENT_INPUT, mapping_path))
    approved_set = set(approved_ids)
    selected = {item["case_id"]: item for item in registry["mapping_records"] if item["case_id"] in approved_set}
    if len(selected) != 74:
        raise ValueError("mapping registry lacks approved development cases")
    target_counter = collections.Counter(node for case in approved_ids for node in set(selected[case]["target_ids"]))
    mapping_rows = []
    for case in sorted(approved_ids):
        source = selected[case]
        targets = source["target_ids"]
        technical_exact = source["mapping_status"] == "EXACT" and not source["invalid_source_ids"] and bool(targets) and len(targets) == len(set(targets))
        review_state = "REQUIRES_SCIENTIFIC_REVIEW" if technical_exact else "AMBIGUOUS"
        citations = [item.get("citation", "") for item in source.get("sources", []) if item.get("citation")]
        mapping_rows.append({"case_id": case, "source_biological_identifier": source["biological_target"], "normalized_identifier": source["source_mapping_key"].strip().casefold(), "target_ids": list(targets), "target_count": len(targets), "mapping_method": "inherited_exact_name_to_upstream_neuron_set" if technical_exact else "unresolved", "mapping_provenance_citations": citations, "mapping_provenance_sha256": source["source_sha256"], "mapping_registry_sha256": MAPPING_SHA256, "technical_state": "TECHNICAL_EXACT_MATCH" if technical_exact else "AMBIGUOUS", "ambiguity_state": "NONE_TECHNICAL" if technical_exact else "REQUIRES_REVIEW", "duplicate_target_within_case_count": len(targets) - len(set(targets)), "shared_target_with_other_case_count": sum(target_counter[target] > 1 for target in set(targets)), "review_state": review_state, "source_review_status": source["review_status"]})
    mapping = {"schema_version": "ai-v2-dev-mapping-v1", "partition": "DEVELOPMENT", "source_sha256": MAPPING_SHA256, "case_count": 74, "valid_review_states": ["TECHNICAL_EXACT_MATCH", "REQUIRES_SCIENTIFIC_REVIEW", "AMBIGUOUS", "REJECTED", "SCIENTIFICALLY_APPROVED"], "mappings": mapping_rows}
    original = load_cv(original_cv_path, frozenset(approved_ids))
    if original.membership_sha256 != TASK1_FOLD_SHA256:
        raise ValueError("historical fold hash mismatch")
    diagnostic = [{"fold": index, "case_count": len(fold), "positive_count": sum(labels[case] for case in fold), "negative_count": len(fold) - sum(labels[case] for case in fold), "positive_prevalence": sum(labels[case] for case in fold) / len(fold)} for index, fold in enumerate(original.folds)]
    stratified = create_stratified_cv(approved_ids, labels)
    return effects, mapping, stratified, diagnostic
