"""Guarded inputs and preregistered decision rule for AI V2 Task 1C."""

from __future__ import annotations

import hashlib
import json
import statistics
from pathlib import Path
from typing import Any

from .access import AccessClass, DataAccessDenied, DevelopmentDataAccess, DevelopmentLabels
from .cv import DevelopmentCV, canonical_hash


TASK1_CONFIG_SHA256 = "55909e29f6f876407965e50f1be9b2cb61cf6e4da86624c3c9041f4c909ca137"
TASK1_FOLD_SHA256 = "6b054c6ff0a6669cb6038b0cd365a6787f5fa5f2d0e5018094badd6cce256dab"
TASK1C_FOLD_SHA256 = "bddbe5a7a51a0610c4d6b82aaf27ac7e6fd10cf892eb0c824ec2dcd3f95fccfd"
TASK1C_SEED = 20260930


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def load_task1c_cv(path: Path, *, approved_ids: frozenset[str]) -> DevelopmentCV:
    """Load only the frozen, development-only stratified fold manifest."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if (
        raw.get("schema_version") != "ai-v2-dev-stratified-cv-v2"
        or raw.get("partition") != "DEVELOPMENT"
        or raw.get("purpose") != "ROBUSTNESS_DIAGNOSTIC_NOT_REPLACEMENT"
        or raw.get("seed") != TASK1C_SEED
        or raw.get("case_count") != 74
        or raw.get("task1_original_fold_membership_sha256") != TASK1_FOLD_SHA256
        or raw.get("fold_membership_sha256") != TASK1C_FOLD_SHA256
    ):
        raise ValueError("Task 1C fold manifest differs from preregistration")
    ids = tuple(raw.get("case_ids", ()))
    folds = tuple(tuple(fold) for fold in raw.get("folds", ()))
    if len(ids) != 74 or len(set(ids)) != 74 or set(ids) != set(approved_ids):
        raise ValueError("Task 1C manifest does not contain exactly the approved DEV IDs")
    cv = DevelopmentCV(
        ids,
        folds,
        int(raw["seed"]),
        str(raw["development_split_sha256"]),
        str(raw["fold_membership_sha256"]),
    )
    if cv.membership_sha256 != TASK1C_FOLD_SHA256 or len(cv.folds) != 5:
        raise ValueError("Task 1C fold membership integrity check failed")
    return cv


def load_task1c_development_labels(
    access: DevelopmentDataAccess,
    *,
    path: Path,
    expected_sha256: str,
    approved_ids: frozenset[str],
) -> DevelopmentLabels:
    """Project labels from the development evaluator's exact 74-case section.

    The function intentionally accesses only `evaluated_cases`; it never reads,
    copies, emits, or returns the artifact's separate all-case score table.
    """
    payload = access.read_bytes(AccessClass.DEVELOPMENT_LABEL, path)
    if sha256_bytes(payload) != expected_sha256:
        raise ValueError("development evaluator artifact hash mismatch")
    raw = json.loads(payload)
    if raw.get("evaluation_split") != "development":
        raise DataAccessDenied("label source is not marked as development")
    rows = raw["comparison"]["systems"]["rewire_effect_only"]["evaluated_cases"]
    if len(rows) != 74:
        raise DataAccessDenied("development evaluator section must contain exactly 74 cases")
    indexed = {row.get("case_id"): row for row in rows}
    if len(indexed) != 74 or set(indexed) != set(approved_ids):
        raise DataAccessDenied("development labels do not equal the approved 74-case partition")
    label_values = {"positive": 1, "negative": 0}
    labels: dict[str, int] = {}
    for case_id, row in indexed.items():
        label = row.get("reference_label")
        if label not in label_values:
            raise DataAccessDenied("development label is missing or not binary")
        labels[case_id] = label_values[label]
    return DevelopmentLabels(labels, AccessClass.DEVELOPMENT_LABEL)


def validate_fold_label_counts(cv: DevelopmentCV, labels: DevelopmentLabels) -> list[dict[str, int]]:
    """Ensure the frozen stratified folds still have their registered balance."""
    if set(labels.values) != set(cv.case_ids):
        raise ValueError("development labels and Task 1C fold IDs differ")
    observed: list[dict[str, int]] = []
    for index, fold in enumerate(cv.folds):
        positive = sum(labels.values[case_id] for case_id in fold)
        counts = {"fold": index, "case_count": len(fold), "positive_count": positive, "negative_count": len(fold) - positive}
        observed.append(counts)
        if counts["positive_count"] != 2:
            raise ValueError("Task 1C fold class counts differ from preregistered manifest")
    return observed


def decide_task1c(fold_metrics: list[dict[str, Any]]) -> dict[str, Any]:
    """Apply the Task 1C decision rule without tuning after results."""
    systems = {name: [row for row in fold_metrics if row["system"] == name] for name in (
        "B0_effect", "B1_structural", "B2_effect_structural", "B3_graphsage", "B4_effect_graphsage"
    )}
    if any(len(rows) != 5 for rows in systems.values()):
        raise ValueError("Task 1C requires exactly five fold rows per system")
    mean = lambda name, metric: statistics.mean(float(row[metric]) for row in systems[name])
    delta_ap_b4 = mean("B4_effect_graphsage", "average_precision") - mean("B0_effect", "average_precision")
    delta_p5_b4 = mean("B4_effect_graphsage", "precision_at_5") - mean("B0_effect", "precision_at_5")
    b4_ap_by_fold = {int(row["fold"]): float(row["average_precision"]) for row in systems["B4_effect_graphsage"]}
    b0_ap_by_fold = {int(row["fold"]): float(row["average_precision"]) for row in systems["B0_effect"]}
    fold_wins = sum(b4_ap_by_fold[fold] > b0_ap_by_fold[fold] for fold in range(5))
    leave_one_fold_out_deltas = {
        str(omitted): statistics.mean(
            b4_ap_by_fold[fold] - b0_ap_by_fold[fold] for fold in range(5) if fold != omitted
        )
        for omitted in range(5)
    }
    robust = (
        delta_ap_b4 >= 0.05
        and delta_p5_b4 >= 0.04
        and mean("B4_effect_graphsage", "average_precision") > mean("B2_effect_structural", "average_precision")
        and fold_wins >= 4
        and all(delta > 0 for delta in leave_one_fold_out_deltas.values())
    )
    graph_systems = ("B3_graphsage", "B4_effect_graphsage")
    weak = any(
        mean(system, metric) > mean("B0_effect", metric)
        for system in graph_systems
        for metric in ("average_precision", "precision_at_5")
    )
    decision = "GRAPH_SIGNAL_ROBUST" if robust else "GRAPH_SIGNAL_STILL_WEAK" if weak else "GRAPH_SIGNAL_UNSUPPORTED"
    return {
        "decision": decision,
        "preregistered_rule_passed": robust,
        "delta_ap_b4_vs_b0": delta_ap_b4,
        "delta_p_at_5_b4_vs_b0": delta_p5_b4,
        "b4_ap_fold_wins_vs_b0": fold_wins,
        "b4_mean_ap_exceeds_b2": mean("B4_effect_graphsage", "average_precision") > mean("B2_effect_structural", "average_precision"),
        "leave_one_fold_out_b4_minus_b0_ap": leave_one_fold_out_deltas,
        "interpretation_boundary": "Development-only computational robustness; not biological or wet-lab validation.",
    }
