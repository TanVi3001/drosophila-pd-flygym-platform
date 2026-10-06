from __future__ import annotations

import hashlib
import json

from drosophila_pd.workbench.evidence import (
    CORPUS_SCHEMA,
    ApprovedEvidenceCorpus,
    OfflineEvidenceRetriever,
)
from drosophila_pd.workbench.study_spec_draft import create_study_spec_draft
from drosophila_pd.workbench.v2_evaluation import EVALUATION_SCHEMA, evaluate_ai_v2_bundle


_CHUNK_ID = "fixture-methods-001"
_CHUNK_TEXT = "The sensory assay measures MN9 firing rate in hertz."


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class _FixtureGenerator:
    """Deterministic stand-in; never contacts an external model provider."""

    provider_id = "synthetic-integration-fixture"

    def __init__(self) -> None:
        self.calls = 0

    def generate_json(self, *, system_prompt, user_payload):
        self.calls += 1
        assert "untrusted data" in system_prompt
        assert user_payload["retrieved_evidence_untrusted_data"][0]["text"] == _CHUNK_TEXT
        return {
            "title": "Synthetic sensory assay draft",
            "hypothesis": "The declared sensory input changes MN9 firing.",
            "falsifiable_prediction": "MN9 firing differs from a matched control.",
            "assay": "sensory_mn9",
            "primary_metric": "mn9_rate",
            "primary_metric_unit": "Hz",
            "field_citations": {field: [_CHUNK_ID] for field in (
                "hypothesis", "falsifiable_prediction", "assay",
                "primary_metric", "primary_metric_unit",
            )},
            "uncertainties": ["Synthetic fixture; scientific review remains required."],
        }


def _retriever(tmp_path) -> OfflineEvidenceRetriever:
    corpus_root = tmp_path / "external" / "ai_v2" / "corpus"
    corpus_root.mkdir(parents=True)
    document = {
        "schema_version": CORPUS_SCHEMA,
        "corpus_id": "synthetic-integration-corpus",
        "corpus_version": "1",
        "sources": [{
            "source_id": "fixture-paper-001",
            "citation": "Synthetic integration fixture, not a scientific source",
            "source_uri": "https://example.org/synthetic-fixture",
            "dataset_version": "fixture-only",
            "evidence_tier": "METHODS",
            "source_sha256": _sha("synthetic source placeholder"),
            "review_status": "APPROVED",
            "reviewer": "synthetic-test-only",
            "reviewed_at": "2026-10-06T00:00:00Z",
            "approval_record_id": "fixture-approval-001",
            "blind_use": "ELIGIBLE",
            "chunks": [{
                "chunk_id": _CHUNK_ID,
                "locator": "Synthetic fixture paragraph 1",
                "evidence_scope": "methods",
                "text": _CHUNK_TEXT,
                "text_sha256": _sha(_CHUNK_TEXT),
                "access_class": "PUBLIC_UNLABELED",
                "blind_review_status": "PASS",
                "blind_reviewer": "synthetic-test-only",
                "blind_reviewed_at": "2026-10-06T00:00:00Z",
            }],
        }],
    }
    payload = json.dumps(document, ensure_ascii=False, sort_keys=True).encode("utf-8")
    corpus_path = corpus_root / "corpus.json"
    corpus_path.write_bytes(payload)
    corpus = ApprovedEvidenceCorpus.load(
        corpus_path,
        expected_sha256=hashlib.sha256(payload).hexdigest(),
        corpus_root=corpus_root,
    )
    output_root = tmp_path / "external" / "ai_v2" / "outputs"
    return OfflineEvidenceRetriever(
        corpus,
        audit_path=output_root / "retrieval_audit.jsonl",
        output_root=output_root,
    )


def _evaluation_case(*, case_id, retrieval, draft, expected_ids, expected_fields,
                     expected_categorical_values, field_support, expected_abstention):
    return {
        "case_id": case_id,
        "expected_relevant_evidence_ids": expected_ids,
        "expected_fields": expected_fields,
        "expected_categorical_values": expected_categorical_values,
        "field_support": field_support,
        "expected_abstention": expected_abstention,
        "forbidden_evidence_ids": [],
        "retrieval": {
            "status": retrieval["status"],
            "evidence_ids": [item["evidence_id"] for item in retrieval["evidence"]],
        },
        "draft": {
            "status": draft["status"],
            "proposed_fields": draft["proposed_fields"],
            "field_citations": {
                field: [item["evidence_id"] for item in citations]
                for field, citations in draft["field_citations"].items()
            },
            "approved": draft["approved"],
            "study_created": draft["study_created"],
            "mapping_created": draft["mapping_created"],
            "job_created": draft["job_created"],
            "graph_used": draft["graph_used"],
            "simulation_started": draft["simulation_started"],
        },
    }


def test_ai_v2_offline_chain_retrieves_drafts_abstains_and_scores_synthetic_fixtures(tmp_path):
    retriever = _retriever(tmp_path)
    generator = _FixtureGenerator()
    answerable_question = "How does the sensory assay measure MN9 firing rate?"
    retrieved = retriever.retrieve(answerable_question, top_k=5).as_dict()
    draft = create_study_spec_draft(
        answerable_question,
        retriever=retriever,
        generator=generator,
        supported_assays={"sensory_mn9"},
    )

    assert retrieved["status"] == "RETRIEVED"
    assert draft["status"] == "DRAFT_REQUIRES_RESEARCHER_REVIEW"
    assert draft["schema_version"] == "workbench-v2-study-spec-draft-2"
    assert draft["provider_id"] == generator.provider_id
    assert draft["uncertainties"] == ["Synthetic fixture; scientific review remains required."]
    assert "uncertainties" not in draft["proposed_fields"]
    assert draft["approved"] is False
    assert draft["study_created"] is False
    assert draft["mapping_created"] is False
    assert draft["job_created"] is False
    assert draft["graph_used"] is False
    assert draft["simulation_started"] is False

    abstention_question = "How does the mushroom body encode odor?"
    no_evidence = retriever.retrieve(abstention_question, top_k=5).as_dict()
    abstaining_draft = create_study_spec_draft(
        abstention_question,
        retriever=retriever,
        generator=generator,
        supported_assays={"sensory_mn9"},
    )
    assert no_evidence["status"] == "NO_APPROVED_EVIDENCE"
    assert abstaining_draft["status"] == "NO_APPROVED_EVIDENCE"
    assert abstaining_draft["proposed_fields"] == {}
    assert generator.calls == 1  # No generation request on the no-evidence path.

    supported_fields = [
        "hypothesis", "falsifiable_prediction", "assay", "primary_metric",
        "primary_metric_unit",
    ]
    relevant_ids = [_CHUNK_ID]
    bundle = {
        "schema_version": EVALUATION_SCHEMA,
        "evaluation_id": "offline-chain-fixture-v1",
        "evaluation_split": "synthetic_fixture",
        "cases": [
            _evaluation_case(
                case_id="fixture-answerable-001",
                retrieval=retrieved,
                draft=draft,
                expected_ids=relevant_ids,
                expected_fields=supported_fields,
                expected_categorical_values={
                    "assay": "sensory_mn9",
                    "primary_metric": "mn9_rate",
                    "primary_metric_unit": "Hz",
                },
                field_support={field: relevant_ids for field in supported_fields},
                expected_abstention=False,
            ),
            _evaluation_case(
                case_id="fixture-abstention-001",
                retrieval=no_evidence,
                draft=abstaining_draft,
                expected_ids=[],
                expected_fields=[],
                expected_categorical_values={},
                field_support={},
                expected_abstention=True,
            ),
        ],
    }
    report = evaluate_ai_v2_bundle(bundle, k=5)

    assert report["evaluation_split"] == "synthetic_fixture"
    assert report["evaluation_case_count"] == 2
    assert report["metrics"]["retrieval_recall_at_k_macro"] == 1.0
    assert report["metrics"]["retrieval_mrr"] == 1.0
    assert report["metrics"]["abstention_accuracy"] == 1.0
    assert report["metrics"]["false_acceptance_rate"] == 0.0
    assert report["metrics"]["draft_non_executable_invariant_pass_rate"] == 1.0
    assert report["input_bundle_sha256"]
    assert "semantic entailment" in report["interpretation_limits"][
        "citation_precision_reference_proxy"
    ].lower()
