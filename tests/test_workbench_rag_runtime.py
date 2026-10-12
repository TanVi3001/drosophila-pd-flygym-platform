from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient

from drosophila_pd.workbench.api import create_app
from drosophila_pd.workbench.intake import create_rag_intake_draft
from drosophila_pd.workbench.rag import load_frozen_evidence_corpus
from drosophila_pd.workbench.service import WorkbenchService
from drosophila_pd.workbench.store import WorkbenchStore


def _corpus_files(
    root: Path,
    *,
    provider_sharing_approved: bool = True,
    protocol_text_sharing_approved: bool = True,
    partition: str = "DEVELOPMENT",
    chunks: list[dict[str, str]] | None = None,
) -> tuple[Path, bytes]:
    root.mkdir(parents=True, exist_ok=True)
    chunks = chunks or [
        {
            "source_id": "DEV_SYNTHETIC_GUIDE",
            "citation": "Synthetic fixture guide, section 1",
            "chunk_id": "fixture:1",
            "text": "Synthetic development fixture describes a neural response assay and firing-rate readout.",
            "provenance": "generated test fixture; not a research source",
            "access_class": "DEVELOPMENT_INPUT",
        },
        {
            "source_id": "DEV_SYNTHETIC_GUIDE",
            "citation": "Synthetic fixture guide, section 2",
            "chunk_id": "fixture:2",
            "text": "Synthetic fixture describes video tracking and locomotion measurements.",
            "provenance": "generated test fixture; not a research source",
            "access_class": "DEVELOPMENT_INPUT",
        },
    ]
    corpus_bytes = b"".join(
        json.dumps(item, sort_keys=True, separators=(",", ":")).encode() + b"\n"
        for item in chunks
    )
    (root / "approved-corpus.jsonl").write_bytes(corpus_bytes)
    manifest = {
        "schema_version": "approved-evidence-corpus-1",
        "corpus_id": "SYNTHETIC_TEST_CORPUS_ONLY",
        "corpus_file": "approved-corpus.jsonl",
        "corpus_sha256": hashlib.sha256(corpus_bytes).hexdigest(),
        "approved_source_ids": ["DEV_SYNTHETIC_GUIDE"],
        "denied_source_ids": ["SEALED_LABELS"],
        "partition": partition,
        "owner_approved": True,
        "outcome_free": True,
        "provider_sharing_approved": provider_sharing_approved,
        "protocol_text_sharing_approved": protocol_text_sharing_approved,
        "reviewed_by": ["synthetic-test-curator"],
        "reviewed_at": "2026-10-06T12:00:00Z",
        "approved_provider_id": (
            "fake-evidence-provider"
            if provider_sharing_approved and protocol_text_sharing_approved else ""
        ),
        "approved_provider_endpoint": (
            "https://llm.example/v1/chat/completions"
            if provider_sharing_approved and protocol_text_sharing_approved else ""
        ),
    }
    path = root / "manifest.json"
    path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    return path, corpus_bytes


def _load(path: Path, root: Path):
    return load_frozen_evidence_corpus(path, retrieval_log_path=root / "artifacts" / "retrieval.jsonl")


class EvidenceProvider:
    provider_id = "fake-evidence-provider"
    model = "fake-model"
    endpoint = "https://llm.example/v1/chat/completions"

    def __init__(self):
        self.called = False
        self.protocol = None
        self.evidence = None

    def extract_with_evidence(self, protocol_text, *, evidence):
        self.called = True
        self.protocol = protocol_text
        self.evidence = evidence
        return {
            "hypothesis": "Fixture hypothesis for review",
            "falsifiable_prediction": "Fixture prediction",
            "assay": "synthetic_demo",
            "primary_metric": "fixture_rate",
            "candidate_suggestions": [{"label": "fixture candidate", "sources": [{"citation": "invented citation"}]}],
            "citations": [
                {"source_id": evidence[0]["source_id"], "chunk_id": evidence[0]["chunk_id"]},
                {"source_id": "MADE_UP_SOURCE", "chunk_id": "invented:7"},
            ],
            "mapping": {"target_ids": ["must-not-survive"]},
        }


def test_corpus_checksum_allowlist_and_deterministic_offline_retrieval(tmp_path: Path) -> None:
    manifest_path, _ = _corpus_files(tmp_path / "corpus")
    corpus = _load(manifest_path, tmp_path)

    first = corpus.retrieve("neural response firing-rate assay", k=2)
    second = corpus.retrieve("neural response firing-rate assay", k=2)

    assert [hit.evidence.chunk_id for hit in first] == ["fixture:1"]
    assert [hit.as_dict() for hit in first] == [hit.as_dict() for hit in second]
    assert all(hit.evidence.source_id == "DEV_SYNTHETIC_GUIDE" for hit in first)
    events = [json.loads(line) for line in (tmp_path / "artifacts" / "retrieval.jsonl").read_text().splitlines()]
    assert len(events) == 2
    assert events[0]["query_sha256"] == hashlib.sha256(b"neural response firing-rate assay").hexdigest()
    assert "query" not in events[0]
    assert events[0]["corpus_sha256"] == corpus.corpus_sha256


def test_retrieval_has_bounded_k_and_query_and_abstains_without_matches(tmp_path: Path) -> None:
    manifest_path, _ = _corpus_files(tmp_path / "corpus")
    corpus = _load(manifest_path, tmp_path)

    assert corpus.retrieve("query terms absent from corpus") == ()
    for invalid_k in (0, 21, True, "5"):
        with pytest.raises(ValueError, match="k must"):
            corpus.retrieve("neural", k=invalid_k)
    with pytest.raises(ValueError, match="non-empty"):
        corpus.retrieve("  ")
    with pytest.raises(ValueError, match="characters"):
        corpus.retrieve("x" * 20_001)


@pytest.mark.parametrize(
    "change,match",
    [
        ("tamper", "SHA-256 mismatch"),
        ("partition", "DEVELOPMENT corpora only"),
        ("access", "forbidden access_class"),
        ("source", "source is not approved"),
        ("duplicate", "duplicate RAG chunk identity"),
        ("owner", "owner-approved"),
    ],
)
def test_loader_fails_closed_on_tampering_and_unapproved_sources(tmp_path: Path, change: str, match: str) -> None:
    root = tmp_path / change
    path, _ = _corpus_files(root)
    if change == "tamper":
        with (root / "approved-corpus.jsonl").open("ab") as stream:
            stream.write(b" ")
    elif change == "partition":
        manifest = json.loads(path.read_text())
        manifest["partition"] = "HELDOUT"
        path.write_text(json.dumps(manifest))
    elif change == "owner":
        manifest = json.loads(path.read_text())
        manifest["owner_approved"] = False
        path.write_text(json.dumps(manifest))
    else:
        chunks = [
            {
                "source_id": "DEV_SYNTHETIC_GUIDE",
                "citation": "Synthetic test cite",
                "chunk_id": "same:1",
                "text": "neural response fixture",
                "provenance": "generated test fixture",
                "access_class": "DEVELOPMENT_INPUT",
            },
            {
                "source_id": "DEV_SYNTHETIC_GUIDE",
                "citation": "Synthetic test cite 2",
                "chunk_id": "same:1",
                "text": "duplicate fixture identity",
                "provenance": "generated test fixture",
                "access_class": "DEVELOPMENT_INPUT",
            },
        ]
        if change == "access":
            chunks[0]["access_class"] = "SEALED_OUTCOME"
        if change == "source":
            chunks[0]["source_id"] = "SEALED_LABELS"
            chunks = chunks[:1]
        path, _ = _corpus_files(root, chunks=chunks)
    with pytest.raises(ValueError, match=match):
        _load(path, root)


def test_manifest_rejects_unknown_and_duplicate_json_keys(tmp_path: Path) -> None:
    path, _ = _corpus_files(tmp_path / "corpus")
    manifest = json.loads(path.read_text())
    manifest["heldout_labels"] = "not allowed"
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="missing or unsupported fields"):
        _load(path, tmp_path)
    path.write_text('{"schema_version":"x","schema_version":"y"}')
    with pytest.raises(ValueError, match="duplicate JSON key"):
        _load(path, tmp_path)


def test_manifest_corpus_path_cannot_escape_package_directory(tmp_path: Path) -> None:
    package = tmp_path / "package"
    path, _ = _corpus_files(package)
    outside = tmp_path / "outside.jsonl"
    outside.write_text("{}\n", encoding="utf-8")
    manifest = json.loads(path.read_text())
    manifest["corpus_file"] = "../outside.jsonl"
    manifest["corpus_sha256"] = hashlib.sha256(outside.read_bytes()).hexdigest()
    path.write_text(json.dumps(manifest))

    with pytest.raises(ValueError, match="beside/under the manifest"):
        _load(path, package)


def test_manifest_freeze_tool_verifies_and_never_overwrites(tmp_path: Path) -> None:
    import runpy
    from argparse import Namespace

    root = tmp_path / "package"
    source_manifest, _ = _corpus_files(root)
    corpus_path = root / "approved-corpus.jsonl"
    manifest_path = root / "frozen-manifest.json"
    build_manifest = runpy.run_path(str(Path(__file__).parents[1] / "scripts" / "create_rag_manifest.py"))["build_manifest"]
    args = Namespace(
        corpus=corpus_path,
        manifest=manifest_path,
        corpus_id="SYNTHETIC_FREEZE_TEST",
        approved_source_id=["DEV_SYNTHETIC_GUIDE"],
        denied_source_id=["SEALED_LABELS"],
        reviewed_by=["test-reviewer"],
        owner_approved=True,
        outcome_free=True,
        provider_sharing_approved=False,
        protocol_text_sharing_approved=False,
        approved_provider_id=None,
        approved_provider_endpoint=None,
    )

    _path, report = build_manifest(args)
    assert report["chunk_count"] == 2
    assert report["corpus_sha256"] == hashlib.sha256(corpus_path.read_bytes()).hexdigest()
    with pytest.raises(FileExistsError, match="overwriting a freeze"):
        build_manifest(args)
    assert source_manifest.exists()


def test_rag_provider_is_blocked_without_both_explicit_sharing_approvals(tmp_path: Path) -> None:
    manifest_path, _ = _corpus_files(
        tmp_path / "corpus", provider_sharing_approved=False, protocol_text_sharing_approved=True,
    )
    corpus = _load(manifest_path, tmp_path)
    provider = EvidenceProvider()

    with pytest.raises(PermissionError, match="sharing"):
        create_rag_intake_draft("neural response assay", corpus, provider)
    assert provider.called is False


def test_rag_provider_identity_and_endpoint_must_match_the_attestation(tmp_path: Path) -> None:
    manifest_path, _ = _corpus_files(tmp_path / "corpus")
    corpus = _load(manifest_path, tmp_path)
    provider = EvidenceProvider()
    provider.endpoint = "https://different.example/v1/chat/completions"

    with pytest.raises(PermissionError, match="identity/endpoint"):
        create_rag_intake_draft("neural response assay", corpus, provider)
    assert provider.called is False


def test_no_evidence_abstains_without_provider_or_share_approval(tmp_path: Path) -> None:
    manifest_path, _ = _corpus_files(
        tmp_path / "corpus", provider_sharing_approved=False, protocol_text_sharing_approved=False,
    )
    corpus = _load(manifest_path, tmp_path)

    result = create_rag_intake_draft("unrelated words", corpus, None)
    assert result["status"] == "ABSTAINED_NO_EVIDENCE"
    assert result["guardrail_events"] == ["no_approved_evidence_match", "provider_not_called"]
    assert result["approved"] is False
    assert result["study_created"] is False


def test_rag_draft_sanitizes_citations_and_never_creates_mapping(tmp_path: Path) -> None:
    manifest_path, _ = _corpus_files(tmp_path / "corpus")
    corpus = _load(manifest_path, tmp_path)
    provider = EvidenceProvider()

    result = create_rag_intake_draft("neural response firing-rate assay", corpus, provider)

    assert provider.called is True
    assert provider.protocol == "neural response firing-rate assay"
    assert provider.evidence[0]["chunk_id"] == "fixture:1"
    assert result["status"] == "DRAFT_REQUIRES_RESEARCHER_REVIEW"
    assert result["proposed_fields"]["citations"] == [{
        "source_id": "DEV_SYNTHETIC_GUIDE",
        "chunk_id": "fixture:1",
        "citation": "Synthetic fixture guide, section 1",
        "locator": "fixture:1",
    }]
    assert "mapping" not in result["proposed_fields"]
    assert "sources" not in result["proposed_fields"]["candidate_suggestions"][0]
    assert "nested_unverified_citations_removed" in result["guardrail_events"]
    assert "mapping_generation_prohibited" in result["guardrail_events"]
    assert "unsupported_citations_removed" in result["guardrail_events"]
    assert result["rag"]["citation_validation"] == "PASS_WITH_UNSUPPORTED_CITATIONS_REMOVED"
    assert result["provenance"]["corpus_sha256"] == corpus.corpus_sha256
    assert result["provenance"]["generator_output_sha256"]
    assert result["approved"] is False and result["study_created"] is False and result["mapping_created"] is False


def _service(tmp_path: Path, provider=None) -> WorkbenchService:
    return WorkbenchService(
        store=WorkbenchStore(tmp_path / "state.sqlite3"),
        artifact_root=tmp_path / "artifacts",
        intake_provider=provider,
    )


def test_rag_api_auth_retrieval_and_provider_gate(tmp_path: Path) -> None:
    manifest_path, _ = _corpus_files(
        tmp_path / "corpus", provider_sharing_approved=False, protocol_text_sharing_approved=True,
    )
    corpus = _load(manifest_path, tmp_path)
    app = create_app(_service(tmp_path, EvidenceProvider()), api_token="r" * 40, deployment_env="staging", rag_corpus=corpus)
    with TestClient(app) as client:
        assert client.get("/v1/ai/rag/status").status_code == 401
        headers = {"Authorization": "Bearer " + "r" * 40}
        status = client.get("/v1/ai/rag/status", headers=headers).json()
        assert status["status"] == "RETRIEVAL_READY"
        assert status["provider_ready"] is False
        retrieved = client.post(
            "/v1/ai/rag/retrieve", headers=headers,
            json={"query": "neural response firing-rate assay", "k": 3},
        )
        assert retrieved.status_code == 200
        assert retrieved.json()["provider_called"] is False
        assert retrieved.json()["retrieved_evidence"][0]["chunk_id"] == "fixture:1"
        blocked = client.post(
            "/v1/ai/rag/draft", headers=headers,
            json={"protocol_text": "neural response firing-rate assay"},
        )
        assert blocked.status_code == 403
        disabled_legacy = client.post(
            "/v1/protocol-intake/draft", headers=headers,
            json={"protocol_text": "do not send without RAG"},
        )
        assert disabled_legacy.status_code == 403


def test_rag_api_creates_persisted_evidence_conditioned_draft_only(tmp_path: Path) -> None:
    manifest_path, _ = _corpus_files(tmp_path / "corpus")
    corpus = _load(manifest_path, tmp_path)
    provider = EvidenceProvider()
    service = _service(tmp_path, provider)
    app = create_app(service, api_token="a" * 40, deployment_env="staging", rag_corpus=corpus)
    with TestClient(app) as client:
        response = client.post(
            "/v1/ai/rag/draft",
            headers={"Authorization": "Bearer " + "a" * 40},
            json={"protocol_text": "neural response firing-rate assay", "k": 1},
        )
        assert response.status_code == 200, response.text
        draft = response.json()
        assert draft["draft_id"].startswith("rag-intake-")
        assert draft["rag"]["retrieved_evidence"][0]["chunk_id"] == "fixture:1"
        assert draft["approved"] is False
        assert draft["study_created"] is False
        assert draft["mapping_created"] is False
        assert provider.called is True
        assert list((tmp_path / "artifacts" / "intake_drafts").glob("rag-intake-*.json"))
        assert client.get("/v1/studies", headers={"Authorization": "Bearer " + "a" * 40}).json()["studies"] == []


def test_provider_failure_returns_no_persisted_draft(tmp_path: Path) -> None:
    manifest_path, _ = _corpus_files(tmp_path / "corpus")
    corpus = _load(manifest_path, tmp_path)

    class BrokenProvider:
        provider_id = "fake-evidence-provider"
        endpoint = "https://llm.example/v1/chat/completions"

        def extract_with_evidence(self, *_args, **_kwargs):
            raise RuntimeError("provider request failed: TimeoutError")

    service = _service(tmp_path, BrokenProvider())
    app = create_app(service, api_token="f" * 40, deployment_env="staging", rag_corpus=corpus)
    with TestClient(app) as client:
        response = client.post(
            "/v1/ai/rag/draft",
            headers={"Authorization": "Bearer " + "f" * 40},
            json={"protocol_text": "neural response firing-rate assay"},
        )
        assert response.status_code == 502
        assert "TimeoutError" not in response.text
        assert not list((tmp_path / "artifacts" / "intake_drafts").glob("*.json"))


def test_rag_api_without_corpus_and_without_provider_fail_clearly(tmp_path: Path) -> None:
    app = create_app(_service(tmp_path), api_token="b" * 40, deployment_env="staging")
    with TestClient(app) as client:
        headers = {"Authorization": "Bearer " + "b" * 40}
        assert client.get("/v1/ai/rag/status", headers=headers).json()["status"] == "DISABLED"
        assert client.post("/v1/ai/rag/retrieve", headers=headers, json={"query": "x"}).status_code == 503

    manifest_path, _ = _corpus_files(tmp_path / "corpus")
    corpus = _load(manifest_path, tmp_path)
    app = create_app(_service(tmp_path / "no_provider"), api_token="c" * 40, deployment_env="staging", rag_corpus=corpus)
    with TestClient(app) as client:
        response = client.post(
            "/v1/ai/rag/draft",
            headers={"Authorization": "Bearer " + "c" * 40},
            json={"protocol_text": "neural response assay"},
        )
        assert response.status_code == 503
