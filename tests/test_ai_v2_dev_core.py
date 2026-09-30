"""Synthetic-only infrastructure tests for the isolated AI V2 core."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from drosophila_pd.ai_v2.access import AccessClass, DataAccessDenied, DevelopmentDataAccess, DevelopmentLabels
from drosophila_pd.ai_v2.contracts import AIStudySpec, EvidenceItem, GraphEmbeddingArtifact, RankingPrediction, UnifiedFeatures
from drosophila_pd.ai_v2.cv import canonical_hash, load_cv, make_development_cv
from drosophila_pd.ai_v2.experiment import DevelopmentExperiment
from drosophila_pd.ai_v2.graph import GraphPretrainingContract
from drosophila_pd.ai_v2.metrics import average_precision, coverage, precision_at_k, recall_at_k
from drosophila_pd.ai_v2.pipeline import AIV2Pipeline
from drosophila_pd.ai_v2.rag import RAGRuntimeContract
from drosophila_pd.workbench.models import CandidateSpec, StudySpec


def test_firewall_denies_all_validation_classes_and_sensitive_paths(tmp_path: Path) -> None:
    dev = tmp_path / "dev"
    dev.mkdir()
    (dev / "input.json").write_text("{}", encoding="utf-8")
    (dev / "labels.json").write_text('{"DEV_01": 1}', encoding="utf-8")
    access = DevelopmentDataAccess({AccessClass.DEVELOPMENT_INPUT: dev, AccessClass.DEVELOPMENT_LABEL: dev}, {AccessClass.DEVELOPMENT_INPUT: frozenset({dev / "input.json"}), AccessClass.DEVELOPMENT_LABEL: frozenset({dev / "labels.json"})}, tmp_path / "audit.jsonl")
    assert access.read_bytes(AccessClass.DEVELOPMENT_INPUT, dev / "input.json") == b"{}"
    assert access.load_development_labels(dev / "labels.json", approved_ids=frozenset({"DEV_01"})).values["DEV_01"] == 1
    for forbidden in (AccessClass.INTERNAL_HELDOUT_INPUT, AccessClass.INTERNAL_HELDOUT_LABEL, AccessClass.EXTERNAL_VALIDATION_INPUT, AccessClass.EXTERNAL_VALIDATION_LABEL):
        with pytest.raises(DataAccessDenied):
            access.read_bytes(forbidden, dev / "input.json")
    hidden = dev / "validation_labels_sealed"
    hidden.mkdir()
    (hidden / "data.json").write_text("{}", encoding="utf-8")
    with pytest.raises(DataAccessDenied):
        access.read_bytes(AccessClass.DEVELOPMENT_INPUT, hidden / "data.json")
    (dev / "unapproved.json").write_text("{}", encoding="utf-8")
    with pytest.raises(DataAccessDenied):
        access.read_bytes(AccessClass.DEVELOPMENT_INPUT, dev / "unapproved.json")
    (dev / "shiu_public_benchmark_v2.json").write_text("{}", encoding="utf-8")
    with pytest.raises(DataAccessDenied):
        access.read_bytes(AccessClass.DEVELOPMENT_INPUT, dev / "shiu_public_benchmark_v2.json")
    with pytest.raises(DataAccessDenied):
        access.read_bytes(AccessClass.DEVELOPMENT_INPUT, tmp_path / "outside.json")
    with pytest.raises(DataAccessDenied):
        access.read_bytes("UNKNOWN", dev / "input.json")
    events = [json.loads(line) for line in (tmp_path / "audit.jsonl").read_text(encoding="utf-8").splitlines()]
    assert sum(event["decision"] == "DENY" for event in events) == 9


def test_cv_is_deterministic_and_rejects_partition_switch(tmp_path: Path) -> None:
    ids = tuple(f"DEV_{index:02d}" for index in range(20))
    approved = frozenset(ids)
    cv = make_development_cv(ids, approved_ids=approved)
    assert cv == make_development_cv(tuple(reversed(ids)), approved_ids=approved)
    assert sorted(len(fold) for fold in cv.folds) == [4] * 5
    for index in range(5):
        train, validation = cv.train_validation(index)
        assert set(train).isdisjoint(validation)
        assert set(train) | set(validation) == approved
    path = tmp_path / "cv.json"
    path.write_text(json.dumps(cv.as_dict()), encoding="utf-8")
    assert load_cv(path, approved).membership_sha256 == cv.membership_sha256
    with pytest.raises(ValueError):
        make_development_cv(ids + ("EXTVAL_0001",), approved_ids=approved)
    with pytest.raises(ValueError):
        load_cv(path, approved | {"OTHER"})
    corrupt = cv.as_dict()
    corrupt["folds"][0][0] = "HELDOUT_FAKE"
    path.write_text(json.dumps(corrupt), encoding="utf-8")
    with pytest.raises(ValueError):
        load_cv(path, approved)


def test_metric_definitions() -> None:
    labels = {"A": 1, "B": 0, "C": 1, "D": 0}
    scores = {"A": 0.9, "B": 0.8, "C": 0.7, "D": 0.6}
    assert average_precision(labels, scores) == pytest.approx((1 + 2 / 3) / 2)
    assert precision_at_k(labels, scores, 2) == 0.5
    assert recall_at_k(labels, scores, 2) == 0.5
    assert coverage(set(labels), {"A", "B"}) == 0.5
    with pytest.raises(ValueError):
        average_precision(labels, {"A": 1.0})


def test_synthetic_pipeline_and_development_experiment(tmp_path: Path) -> None:
    digest = "a" * 64
    config = {"synthetic": True}
    config_hash = canonical_hash(config)
    evidence = EvidenceItem("SOURCE_1", "Synthetic source", "CHUNK_1", 0.9, "synthetic", "PUBLIC_UNLABELED")
    graph = {"nodes": ["X", "Y"], "edges": [["X", "Y"]]}
    artifact = GraphEmbeddingArtifact(canonical_hash(graph), "fake-encoder", digest, 2, "self_supervised_unlabeled", "inductive", "synthetic-commit")

    class Retrieve:
        def retrieve(self, query):
            return [evidence]

    class Generate:
        def draft(self, query, items):
            study = StudySpec(name="Synthetic", hypothesis="Test", falsifiable_prediction="Synthetic readout", assay="synthetic neural", primary_metric="synthetic value", candidates=(CandidateSpec(candidate_id="C", label="C"),))
            return AIStudySpec(study, (items[0].source_id,))

    class Encode:
        def encode(self, study):
            return artifact, (0.2, 0.3)

    class Fuse:
        def fuse(self, case_id, **families):
            return UnifiedFeatures(case_id, families["lif_effect"], families["graph_embedding"], families["uncertainty"], families["qc_provenance"])

    class Uncertainty:
        def estimate(self, features):
            return 0.1

    class Rank:
        def predict(self, features):
            return RankingPrediction(features.case_id, sum(features.lif_effect) + sum(features.graph_embedding), 0.1, "synthetic-model", config_hash)

    ids = tuple(f"DEV_{index:02d}" for index in range(20))
    cv = make_development_cv(ids, approved_ids=frozenset(ids))
    pipeline = AIV2Pipeline(Retrieve(), Generate(), Encode(), Fuse(), Uncertainty(), Rank(), RAGRuntimeContract(digest, frozenset({"SOURCE_1"}), frozenset(), retrieval_log_path=tmp_path / "retrieval.jsonl"), frozenset(ids))
    def predict(case_id):
        study, prediction = pipeline.run_case(case_id, "synthetic question", lif_effect=(0.1,), uncertainty_features=(0.2,), qc_provenance=(1.0,))
        assert study.approval_status == "DRAFT"
        return prediction
    labels = {case: 0 for case in ids}
    for fold in cv.folds:
        labels[fold[0]] = 1
    experiment = DevelopmentExperiment(cv, "synthetic-commit", "clean", "synthetic-model", config, {"fake_graph": canonical_hash(graph)}, ("lif_effect", "graph_embedding", "uncertainty", "qc_provenance"), 11, tmp_path)
    manifest = experiment.run_fold(fold=0, labels=DevelopmentLabels(labels, AccessClass.DEVELOPMENT_LABEL), predict=predict, output_dir=tmp_path / "run", k=2)
    assert manifest["partition"] == "DEVELOPMENT"
    assert manifest["metrics"]["coverage"] == 1.0
    predictions = json.loads((tmp_path / "run" / "predictions.json").read_text(encoding="utf-8"))
    assert all("label" not in row for row in predictions)
    assert json.loads((tmp_path / "retrieval.jsonl").read_text(encoding="utf-8").splitlines()[0])["source_id"] == "SOURCE_1"
    with pytest.raises(ValueError):
        pipeline.run_case("EXTVAL_0001", "synthetic question", lif_effect=(0.1,), uncertainty_features=(0.2,), qc_provenance=(1.0,))
    with pytest.raises(ValueError):
        experiment.run_fold(fold=1, labels=DevelopmentLabels({"EXTVAL_0001": 1}, AccessClass.DEVELOPMENT_LABEL), predict=predict, output_dir=tmp_path / "invalid")


def test_contracts_reject_labels_and_transductive_graph() -> None:
    with pytest.raises(TypeError):
        RankingPrediction("DEV_1", 0.2, 0.1, "model", "a" * 64, label=1)
    with pytest.raises(ValueError):
        GraphEmbeddingArtifact("a" * 64, "encoder", "b" * 64, 2, "self_supervised_unlabeled", "transductive", "commit")
    with pytest.raises(ValueError):
        GraphPretrainingContract("external_validation_labels", "a" * 64, "mask", "encoder", 1, "reconstruct", 2)
    with pytest.raises(ValueError):
        RAGRuntimeContract("a" * 64, frozenset({"SOURCE_1"}), frozenset(), no_internet=False)


def test_real_development_manifest_contains_only_approved_74() -> None:
    root = Path(__file__).resolve().parents[1]
    approved = json.loads((root / "configs/ai_v2/approved_development_ids_v1.json").read_text(encoding="utf-8"))
    assert approved["case_count"] == 74
    assert len(set(approved["case_ids"])) == 74
    cv = load_cv(root / "configs/ai_v2/development_cv_5fold_v1.json", frozenset(approved["case_ids"]))
    assert len(cv.folds) == 5
    assert sorted(len(fold) for fold in cv.folds) == [14, 15, 15, 15, 15]
