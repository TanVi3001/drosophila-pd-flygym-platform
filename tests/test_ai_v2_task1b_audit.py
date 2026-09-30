"""Synthetic tests for post-Task-1 sanitization and CV registration."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from drosophila_pd.ai_v2.access import AccessClass, DataAccessDenied, DevelopmentDataAccess
from drosophila_pd.ai_v2.cv import make_development_cv
from drosophila_pd.ai_v2.graph_data import GraphProjection
from drosophila_pd.ai_v2.representation_audit import audit_representation
from drosophila_pd.ai_v2 import task1b_audit as audit


def _synthetic_sources(tmp_path: Path, monkeypatch):
    ids = tuple(f"DEV_{index:03d}" for index in range(74))
    labels = {case: int(index < 10) for index, case in enumerate(ids)}
    development = tmp_path / "development.json"
    development.write_text(json.dumps({"evaluation_split": "development", "comparison": {"systems": {"rewire_effect_only": {"evaluated_cases": [{"case_id": case, "reference_label": "positive" if labels[case] else "negative", "ranking_score": float(index)} for index, case in enumerate(ids)]}}}, "score_table": [{"case_id": "NON_DEV_SENTINEL", "private_value": "MUST_NOT_COPY"}]}), encoding="utf-8")
    mapping = tmp_path / "mapping.json"
    records = [{"case_id": case, "biological_target": f"cell_{index}", "source_mapping_key": f"CELL_{index}", "target_ids": [str(index + 1)], "mapping_status": "EXACT", "invalid_source_ids": [], "source_sha256": "a" * 64, "review_status": "PENDING_SCIENTIFIC_REVIEW"} for index, case in enumerate(ids)]
    records.append({"case_id": "NON_DEV_SENTINEL", "private_value": "MUST_NOT_COPY"})
    mapping.write_text(json.dumps({"mapping_records": records}), encoding="utf-8")
    original = make_development_cv(ids, approved_ids=frozenset(ids))
    cv_path = tmp_path / "cv.json"
    cv_path.write_text(json.dumps(original.as_dict()), encoding="utf-8")
    monkeypatch.setattr(audit, "DEV_ABLATION_SHA256", audit.hash_bytes(development.read_bytes()))
    monkeypatch.setattr(audit, "MAPPING_SHA256", audit.hash_bytes(mapping.read_bytes()))
    monkeypatch.setattr(audit, "TASK1_FOLD_SHA256", original.membership_sha256)
    access = DevelopmentDataAccess({AccessClass.DEVELOPMENT_LABEL: tmp_path, AccessClass.DEVELOPMENT_INPUT: tmp_path}, {AccessClass.DEVELOPMENT_LABEL: frozenset({development}), AccessClass.DEVELOPMENT_INPUT: frozenset({mapping})}, tmp_path / "audit.jsonl")
    return ids, development, mapping, cv_path, access


def test_sanitized_artifacts_are_exactly_dev_and_label_free(tmp_path: Path, monkeypatch) -> None:
    ids, dev, mapping, cv_path, access = _synthetic_sources(tmp_path, monkeypatch)
    features, mappings, stratified, diagnostic = audit.sanitize_development_inputs(access, approved_ids=ids, dev_ablation_path=dev, mapping_path=mapping, original_cv_path=cv_path)
    assert set(row["case_id"] for row in features["features"]) == set(ids)
    assert set(row["case_id"] for row in mappings["mappings"]) == set(ids)
    assert len(features["features"]) == len(mappings["mappings"]) == 74
    assert "MUST_NOT_COPY" not in json.dumps(features) + json.dumps(mappings)
    assert all("label" not in key.lower() and "outcome" not in key.lower() for row in features["features"] + mappings["mappings"] for key in row)
    assert {row["review_state"] for row in mappings["mappings"]} == {"REQUIRES_SCIENTIFIC_REVIEW"}
    assert len(diagnostic) == 5 and sum(row["positive_count"] for row in diagnostic) == 10
    assert stratified["created_after_task1_results"] is True
    assert stratified["purpose"] == "ROBUSTNESS_DIAGNOSTIC_NOT_REPLACEMENT"
    assert len(stratified["folds"]) == 5
    assert all(row["positive_count"] == 2 for row in stratified["fold_class_counts"])
    flattened = [case for fold in stratified["folds"] for case in fold]
    assert len(flattened) == len(set(flattened)) == 74 and set(flattened) == set(ids)
    assert stratified == audit.create_stratified_cv(ids, {case: int(index < 10) for index, case in enumerate(ids)})
    reordered = audit.create_stratified_cv(tuple(reversed(ids)), {case: int(index < 10) for index, case in enumerate(ids)})
    assert reordered["fold_membership_sha256"] == stratified["fold_membership_sha256"]
    assert audit.hash_bytes(audit.compact_json(reordered)) == audit.hash_bytes(audit.compact_json(stratified))
    with pytest.raises(DataAccessDenied):
        access.read_bytes(AccessClass.INTERNAL_HELDOUT_LABEL, dev)
    with pytest.raises(DataAccessDenied):
        access.read_bytes(AccessClass.EXTERNAL_VALIDATION_LABEL, dev)


def test_real_sanitized_artifact_hashes_and_ids(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    approved = set(json.loads((root / "configs/ai_v2/approved_development_ids_v1.json").read_text())["case_ids"])
    manifest = json.loads((root / "data/ai_v2_dev/sanitized_manifest_v1.json").read_text())
    assert manifest["case_count"] == 74
    for name, digest in manifest["artifacts"].items():
        assert audit.hash_bytes((root / name).read_bytes()) == digest
    for name, section in (("development_effect_features_v1.json", "features"), ("development_mapping_v1.json", "mappings")):
        raw = json.loads((root / "data/ai_v2_dev" / name).read_text())
        assert raw["case_count"] == 74
        assert {row["case_id"] for row in raw[section]} == approved
        assert all("label" not in key.lower() and "outcome" not in key.lower() for row in raw[section] for key in row)
    cv = json.loads((root / "configs/ai_v2/development_cv_stratified_5fold_v2.json").read_text())
    assert cv["case_count"] == 74 and set(cv["case_ids"]) == approved
    assert all(row["positive_count"] == 2 for row in cv["fold_class_counts"])
    diagnostic_path = root / "data/ai_v2_dev/graph_representation_diagnostic_v1.json"
    diagnostic = json.loads(diagnostic_path.read_text())
    candidates = json.loads((root / "configs/ai_v2/graph_representation_candidates_v2.json").read_text())
    assert audit.hash_bytes(diagnostic_path.read_bytes()) == candidates["source_audit_sha256"]
    assert diagnostic["case_count"] == 74 and diagnostic["labels_used"] is False
    manifest_path = root / "data/ai_v2_dev/sanitized_manifest_v1.json"
    effect_path = root / "data/ai_v2_dev/development_effect_features_v1.json"
    mapping_path = root / "data/ai_v2_dev/development_mapping_v1.json"
    access = DevelopmentDataAccess(
        {AccessClass.DEVELOPMENT_INPUT: root / "data/ai_v2_dev"},
        {AccessClass.DEVELOPMENT_INPUT: frozenset({manifest_path, effect_path, mapping_path})},
        tmp_path / "audit.jsonl",
    )
    safe_effects, safe_mapping = audit.load_sanitized_development_inputs(access, approved_ids=tuple(sorted(approved)), manifest_path=manifest_path, effect_path=effect_path, mapping_path=mapping_path)
    assert len(safe_effects["features"]) == len(safe_mapping["mappings"]) == 74


def test_label_blind_representation_audit_handles_shared_targets(tmp_path: Path) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    graph_path = tmp_path / "tiny.parquet"
    pq.write_table(pa.table({"Postsynaptic_ID": [1, 2, 2, 3], "Connectivity": [2, 3, 1, 4]}), graph_path)
    self_features = np.array([[[1, 2, 3, 4], [2, 3, 4, 5]], [[2, 3, 4, 5], [3, 4, 5, 6]], [[4, 5, 6, 7], [0, 0, 0, 0]]], dtype=np.float32)
    neighbor = self_features / 2
    mask = np.array([[1, 1], [1, 1], [1, 0]], dtype=np.float32)
    pooled = (self_features * mask[:, :, None]).sum(axis=1) / mask.sum(axis=1)[:, None]
    projection = GraphProjection(("DEV_A", "DEV_B", "DEV_C"), ((1, 2), (2, 3), (4,)), self_features, neighbor, mask, pooled, "a" * 64, "b" * 64, 4, 4, 4)
    report = audit_representation(projection, [["DEV_A"], ["DEV_B", "DEV_C"]], [["DEV_A", "DEV_B"], ["DEV_C"]], graph_path=graph_path)
    assert report["labels_used"] is False
    assert report["target_neurons_shared_across_cases"] == 1
    assert report["cases_sharing_any_target"] == 2
    assert report["original_cv_cross_fold_target_overlap"][0]["validation_cases_sharing_train_targets"] == 1
    assert report["stratified_cv_cross_fold_target_overlap"][0]["validation_cases_sharing_train_targets"] == 0
