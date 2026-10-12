from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError

import pytest

from drosophila_pd.ai_v2.collection import (
    CollectionError, WorkbenchAPIClient, collect_outputs, load_collection_inputs,
)


def _pack(tmp_path: Path, *, approved=False, policy=False, count=2):
    tmp_path = tmp_path / "inputs"
    tmp_path.mkdir(exist_ok=True)
    corpus = tmp_path / "corpus.jsonl"
    chunk = {"source_id": "SYNTHETIC", "chunk_id": "synthetic:1", "citation": "Synthetic test guide",
             "text": "Synthetic protocol fixture only.", "provenance": "test fixture, not a biological source",
             "access_class": "DEVELOPMENT_INPUT"}
    corpus.write_text(json.dumps(chunk) + "\n", encoding="utf-8")
    sha = hashlib.sha256(corpus.read_bytes()).hexdigest()
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "schema_version": "approved-evidence-corpus-1", "corpus_id": "SYNTHETIC_TEST_ONLY",
        "corpus_file": "corpus.jsonl", "corpus_sha256": sha,
        "approved_source_ids": ["SYNTHETIC"], "denied_source_ids": [], "partition": "DEVELOPMENT",
        "owner_approved": True, "outcome_free": True, "reviewed_by": ["synthetic-test-stub"],
        "reviewed_at": "2026-10-07T12:00:00+07:00", "provider_sharing_approved": approved,
        "protocol_text_sharing_approved": approved,
        "approved_provider_id": "stub-provider" if approved else "",
        "approved_provider_endpoint": "http://localhost:9000/v1/chat/completions" if approved else "",
    }), encoding="utf-8")
    rubric = tmp_path / "rubric.json"
    rubric.write_text(json.dumps({
        "schema_version": "ai-v2-assistant-reference-reviewed-1" if approved else "ai-v2-assistant-reference-draft-1",
        "partition": "DEVELOPMENT", "status": "APPROVED" if approved else "DRAFT_NOT_APPROVED",
        "task_type": "SOFTWARE_POLICY_QA" if policy else "PROTOCOL_DRAFT_EXTRACTION",
        "synthetic_fixture": True, "corpus_sha256": sha,
        "reviewer_ids": ["synthetic-test-stub"] if approved else [],
        "privacy_decision": {"status": "APPROVED" if approved else "NOT_DECIDED",
                             "corpus_text_sharing_approved": approved, "protocol_text_sharing_approved": approved,
                             "provider_id": "stub-provider" if approved else "",
                             "provider_endpoint": "http://localhost:9000/v1/chat/completions" if approved else ""},
        "evaluation_protocol_draft": {"retrieval_k": 5},
        "cases": [{"case_id": f"CASE_{i:03}", "question" if policy else "protocol_text": f"Synthetic protocol {i}",
                   "gold_fields": {"not_sent_to_api": "reference"}} for i in range(count)],
    }), encoding="utf-8")
    return corpus, rubric, manifest, chunk


def _inputs(paths, *, draft=False):
    return load_collection_inputs(paths[0], paths[1], mode="rag-draft" if draft else "retrieval-only",
                                  allow_provider_calls=draft, manifest_path=paths[2])


class FakeAPI:
    def __init__(self, inputs, chunk):
        self.inputs = inputs
        self.chunk = chunk
        self.calls = []
        self.modify = lambda _method, _path, _payload, response: response

    def request(self, method, path, payload=None):
        self.calls.append((method, path, payload))
        identity = {"corpus_sha256": self.inputs["corpus_sha256"],
                    "manifest_sha256": self.inputs["expected_manifest_sha256"]}
        if path.endswith("/status"):
            response = {**identity, "status": "RETRIEVAL_READY", "retriever_configured": True, "provider_ready": True}
        elif path.endswith("/retrieve"):
            response = {**identity, "status": "MATCHES_FOUND", "provider_called": False,
                        "retrieved_evidence": [self.chunk]}
        else:
            response = {"schema_version": "protocol-rag-intake-draft-1", "status": "DRAFT_REQUIRES_RESEARCHER_REVIEW",
                        "source_sha256": hashlib.sha256(payload["protocol_text"].encode()).hexdigest(),
                        "proposed_fields": {"hypothesis": "fixture h", "falsifiable_prediction": "fixture p",
                                            "assay": "synthetic_assay", "primary_metric": "fixture_metric",
                                            "citations": [{"source_id": "SYNTHETIC", "chunk_id": "synthetic:1"}]},
                        "missing_fields": [], "approved": False, "study_created": False, "mapping_created": False,
                        "rag": {**identity, "retrieved_evidence": [self.chunk]},
                        "provenance": {"provider_id": "stub-provider", "model_id": "stub-model", "prompt_version": "stub-prompt-1"}}
        return self.modify(method, path, payload, copy.deepcopy(response))


def _records(root):
    return json.loads((root / "case_outputs.json").read_text(encoding="utf-8"))["cases"]


def test_retrieval_only_collects_every_case_and_never_calls_draft(tmp_path):
    paths = _pack(tmp_path, policy=True)
    inputs = _inputs(paths)
    api = FakeAPI(inputs, paths[3])
    output = tmp_path / "run"
    summary = collect_outputs(inputs, api, output, mode="retrieval-only", test_only=True)
    assert summary["collection_status"] == "COMPLETE"
    assert summary["status_counts"] == {"RETRIEVED": 2}
    assert summary["scoring_status"] == "NOT_RUN"
    assert summary["test_only"] is True
    assert all(not call[1].endswith("/draft") for call in api.calls)
    assert all(record["draft"] is None and record["evaluator_projection"] is None for record in _records(output))
    for name, sha in summary["artifact_sha256"].items():
        assert hashlib.sha256((output / name).read_bytes()).hexdigest() == sha


def test_draft_collection_retains_provenance_projection_and_never_sends_gold(tmp_path):
    paths = _pack(tmp_path, approved=True)
    inputs = _inputs(paths, draft=True)
    api = FakeAPI(inputs, paths[3])
    output = tmp_path / "run"
    summary = collect_outputs(inputs, api, output, mode="rag-draft", test_only=True)
    assert summary["provider_call_confirmed_count"] == 2
    assert summary["observed_generation_identity"]["model_id"] == "stub-model"
    for record in _records(output):
        assert record["status"] == "DRAFT_COLLECTED"
        assert record["draft"]["approved"] is False
        assert record["evaluator_projection"]["status"] == "COMPLETED"
        assert "claim_reviews" not in record["evaluator_projection"]
        assert set(record["timing_seconds"]) == {"retrieval", "draft", "total"}
    for _method, _path, payload in api.calls:
        if payload:
            assert set(payload).issubset({"query", "protocol_text", "k"})
            assert "reference" not in json.dumps(payload)


def test_no_evidence_abstention_is_distinct_from_transport_error(tmp_path):
    paths = _pack(tmp_path, approved=True, count=3)
    inputs = _inputs(paths, draft=True)
    api = FakeAPI(inputs, paths[3])

    def modify(_method, path, payload, response):
        if path.endswith("/draft") and payload["protocol_text"].endswith("1"):
            raise CollectionError("TIMEOUT", "Request timed out")
        if payload and (payload.get("query", payload.get("protocol_text", ""))).endswith("0"):
            if path.endswith("/retrieve"):
                response.update(status="NO_APPROVED_EVIDENCE_MATCH", retrieved_evidence=[])
            else:
                response.update(status="ABSTAINED_NO_EVIDENCE", proposed_fields={},
                                missing_fields=["hypothesis", "falsifiable_prediction", "assay", "primary_metric"])
                response["rag"]["retrieved_evidence"] = []
        return response

    api.modify = modify
    output = tmp_path / "run"
    summary = collect_outputs(inputs, api, output, mode="rag-draft", test_only=True)
    records = _records(output)
    assert summary["collection_status"] == "PARTIAL_FAILURE"
    assert summary["provider_call_unknown_count"] == 1
    assert [row["status"] for row in records] == ["ABSTAINED_NO_EVIDENCE", "ERROR", "DRAFT_COLLECTED"]
    assert records[0]["provider_called"] is False
    assert records[1]["provider_called"] is None
    assert records[1]["retrieved_evidence"]
    assert records[1]["evaluator_projection"] is None
    assert records[1]["timing_seconds"]["draft"] >= 0


@pytest.mark.parametrize("mutation,error", [
    ("partition", "DEVELOPMENT"), ("case_id", "safe filename"),
    ("reserved_name", "safe filename"), ("case_collision", "unique"),
    ("duplicate", "unique"), ("corpus", "hash"), ("k", "retrieval_k"),
])
def test_inputs_fail_before_transport_on_bad_partition_identity_or_shape(tmp_path, mutation, error):
    paths = _pack(tmp_path)
    rubric = json.loads(paths[1].read_text(encoding="utf-8"))
    if mutation == "partition":
        rubric["partition"] = "HELDOUT"  # synthetic invalid metadata, no validation data
    elif mutation == "case_id":
        rubric["cases"][0]["case_id"] = "../../overwrite"
    elif mutation == "duplicate":
        rubric["cases"][1]["case_id"] = rubric["cases"][0]["case_id"]
    elif mutation == "reserved_name":
        rubric["cases"][0]["case_id"] = "CON"
    elif mutation == "case_collision":
        rubric["cases"][1]["case_id"] = rubric["cases"][0]["case_id"].lower()
    elif mutation == "corpus":
        rubric["corpus_sha256"] = "0" * 64
    elif mutation == "k":
        rubric["evaluation_protocol_draft"]["retrieval_k"] = True
    paths[1].write_text(json.dumps(rubric), encoding="utf-8")
    with pytest.raises(ValueError, match=error):
        _inputs(paths)


def test_policy_questions_and_unapproved_references_cannot_call_provider(tmp_path):
    paths = _pack(tmp_path, policy=True)
    with pytest.raises(ValueError, match="policy questions"):
        _inputs(paths, draft=True)
    paths = _pack(tmp_path, policy=False)
    with pytest.raises(ValueError, match="approved reference"):
        _inputs(paths, draft=True)
    with pytest.raises(ValueError, match="allow-provider-calls"):
        load_collection_inputs(paths[0], paths[1], mode="rag-draft")


def test_provider_endpoint_policy_must_match_exact_manifest(tmp_path):
    paths = _pack(tmp_path, approved=True)
    rubric = json.loads(paths[1].read_text(encoding="utf-8"))
    rubric["privacy_decision"]["provider_endpoint"] = "http://localhost:9999/v1/chat/completions"
    paths[1].write_text(json.dumps(rubric), encoding="utf-8")
    with pytest.raises(ValueError, match="does not match"):
        _inputs(paths, draft=True)


def test_existing_output_directory_is_refused_without_any_request(tmp_path):
    paths = _pack(tmp_path)
    inputs = _inputs(paths)
    api = FakeAPI(inputs, paths[3])
    output = tmp_path / "run"
    output.mkdir()
    with pytest.raises(FileExistsError):
        collect_outputs(inputs, api, output, mode="retrieval-only")
    assert api.calls == []


def test_collector_cannot_create_artifacts_inside_input_package(tmp_path):
    paths = _pack(tmp_path)
    inputs = _inputs(paths)
    api = FakeAPI(inputs, paths[3])
    output = paths[0].parent / "run"
    with pytest.raises(ValueError, match="outside input"):
        collect_outputs(inputs, api, output, mode="retrieval-only")
    assert api.calls == []
    assert not output.exists()


def test_runtime_drift_stops_later_requests_but_retains_case_records(tmp_path):
    paths = _pack(tmp_path, count=3)
    inputs = _inputs(paths)
    api = FakeAPI(inputs, paths[3])

    def modify(_method, path, payload, response):
        if path.endswith("/retrieve") and payload["query"].endswith("1"):
            response["corpus_sha256"] = "0" * 64
        return response

    api.modify = modify
    output = tmp_path / "run"
    summary = collect_outputs(inputs, api, output, mode="retrieval-only")
    assert summary["collection_status"] == "PARTIAL_FAILURE"
    assert [record["status"] for record in _records(output)] == ["RETRIEVED", "ERROR", "NOT_RUN"]
    assert len(api.calls) == 3


@pytest.mark.parametrize("bad", ["approved", "citations", "missing_fields", "rag", "source_sha256", "context"])
def test_invalid_draft_is_archived_as_error_not_a_success(tmp_path, bad):
    paths = _pack(tmp_path, approved=True, count=1)
    inputs = _inputs(paths, draft=True)
    api = FakeAPI(inputs, paths[3])

    def modify(_method, path, _payload, response):
        if path.endswith("/draft"):
            if bad == "approved":
                response["approved"] = True
            elif bad == "citations":
                response["proposed_fields"]["citations"][0]["chunk_id"] = "never-retrieved"
            elif bad == "missing_fields":
                response["missing_fields"] = ["assay"]
            elif bad == "source_sha256":
                response["source_sha256"] = "0" * 64
            elif bad == "context":
                response["proposed_fields"]["context"] = {"unknown_field": "value"}
            else:
                response["rag"] = None
        return response

    api.modify = modify
    output = tmp_path / "run"
    collect_outputs(inputs, api, output, mode="rag-draft")
    record = _records(output)[0]
    assert record["status"] == "ERROR"
    assert record["draft"] is not None
    assert record["evaluator_projection"] is None


def test_model_prompt_drift_is_reported_and_stops_the_run(tmp_path):
    paths = _pack(tmp_path, approved=True, count=3)
    inputs = _inputs(paths, draft=True)
    api = FakeAPI(inputs, paths[3])

    def modify(_method, path, payload, response):
        if path.endswith("/draft") and payload["protocol_text"].endswith("1"):
            response["provenance"]["prompt_version"] = "changed-prompt"
        return response

    api.modify = modify
    output = tmp_path / "run"
    collect_outputs(inputs, api, output, mode="rag-draft")
    assert [row["status"] for row in _records(output)] == ["DRAFT_COLLECTED", "ERROR", "NOT_RUN"]


def test_echoed_credentials_are_removed_from_all_artifacts(tmp_path):
    paths = _pack(tmp_path)
    inputs = _inputs(paths)
    api = FakeAPI(inputs, paths[3])
    secret = "temporary-test-bearer-that-must-not-be-stored"

    def modify(_method, _path, _payload, response):
        response["token"] = "unknown-secret"
        response["message"] = secret
        return response

    api.modify = modify
    output = tmp_path / "run"
    collect_outputs(inputs, api, output, mode="retrieval-only", secrets=(secret,))
    for path in output.rglob("*.json"):
        text = path.read_text(encoding="utf-8")
        assert secret not in text and "unknown-secret" not in text


@pytest.mark.parametrize("base", ["http://remote.example", "https://remote.example", "http://user:pass@localhost", "http://localhost/?token=abc"])
def test_transport_rejects_remote_or_credential_bearing_origins_by_default(base):
    with pytest.raises(ValueError):
        WorkbenchAPIClient(base)


def test_transport_bounds_routes_and_timeout():
    with pytest.raises(ValueError, match="timeout"):
        WorkbenchAPIClient("http://localhost", timeout=61)
    with pytest.raises(ValueError, match="only status"):
        WorkbenchAPIClient("http://localhost").request("POST", "/v1/ai/jobs/example/run", {})


@pytest.mark.parametrize("body,code", [(b"not-json", "INVALID_JSON"), (b"[]", "INVALID_RESPONSE"), (b'{"value":NaN}', "INVALID_JSON")])
def test_transport_malformed_json_is_a_typed_error(body, code):
    class Response:
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def read(self, _limit): return body

    class Opener:
        def open(self, _request, *, timeout): return Response()

    client = WorkbenchAPIClient("http://localhost")
    client.opener = Opener()
    with pytest.raises(CollectionError) as caught:
        client.request("GET", "/v1/ai/rag/status")
    assert caught.value.code == code


def test_transport_http_errors_do_not_expose_server_body():
    class Opener:
        def open(self, request, *, timeout):
            raise HTTPError(request.full_url, 401, "secret-token-reflected", {}, None)

    client = WorkbenchAPIClient("http://localhost")
    client.opener = Opener()
    with pytest.raises(CollectionError) as caught:
        client.request("GET", "/v1/ai/rag/status")
    assert caught.value.http_status == 401
    assert "secret" not in str(caught.value)


def test_cli_dry_run_validates_without_creating_run_artifacts(tmp_path):
    paths = _pack(tmp_path, policy=True)
    script = Path(__file__).resolve().parents[1] / "scripts" / "collect_ai_v2_outputs.py"
    output = tmp_path / "run"
    result = subprocess.run([sys.executable, str(script), "--corpus", str(paths[0]), "--rubric", str(paths[1]),
                             "--output-dir", str(output), "--base-url", "http://localhost:1", "--dry-run"],
                            capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["status"] == "INPUTS_READY_NO_REQUESTS"
    assert not output.exists()


def test_collector_integrates_with_real_workbench_api_and_stub_provider(tmp_path):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient
    from drosophila_pd.workbench.api import create_app
    from drosophila_pd.workbench.rag import load_frozen_evidence_corpus
    from drosophila_pd.workbench.service import WorkbenchService
    from drosophila_pd.workbench.store import WorkbenchStore

    paths = _pack(tmp_path, approved=True, count=12)
    inputs = _inputs(paths, draft=True)
    token = "synthetic-staging-token-" + "x" * 32

    class Provider:
        provider_id = "stub-provider"
        model = "stub-model"
        endpoint = "http://localhost:9000/v1/chat/completions"

        def extract_with_evidence(self, text, *, evidence):
            assert "gold_fields" not in text
            return {"hypothesis": "fixture h", "falsifiable_prediction": "fixture p",
                    "assay": "synthetic_assay", "primary_metric": "fixture_metric",
                    "citations": [{"source_id": evidence[0]["source_id"], "chunk_id": evidence[0]["chunk_id"]}]}

    service = WorkbenchService(store=WorkbenchStore(tmp_path / "test.sqlite3"),
                               artifact_root=tmp_path / "server-artifacts", adapters={}, intake_provider=Provider())
    corpus = load_frozen_evidence_corpus(paths[2], retrieval_log_path=tmp_path / "retrieval.jsonl")
    app = create_app(service, api_token=token, deployment_env="staging", rag_corpus=corpus)
    with TestClient(app) as test_client:
        class Adapter:
            def request(self, method, path, payload=None):
                response = test_client.request(method, path, json=payload,
                                               headers={"Authorization": "Bearer " + token})
                if response.status_code != 200:
                    raise CollectionError("HTTP_ERROR", "Workbench error", http_status=response.status_code)
                return response.json()

        output = tmp_path / "run"
        summary = collect_outputs(inputs, Adapter(), output, mode="rag-draft", secrets=(token,), test_only=True)
    assert summary["collection_status"] == "COMPLETE"
    assert summary["status_counts"] == {"DRAFT_COLLECTED": 12}
    assert summary["observed_generation_identity"]["prompt_version"] == "protocol-intake-output-v2"
    assert len(list((tmp_path / "server-artifacts" / "intake_drafts").glob("*.json"))) == 12
    assert service.store.list_studies() == []


def test_preflight_auth_failure_keeps_all_cases_not_run(tmp_path):
    paths = _pack(tmp_path)
    inputs = _inputs(paths)

    class Unauthenticated:
        def request(self, method, path, payload=None):
            assert (method, path) == ("GET", "/v1/ai/rag/status")
            raise CollectionError("HTTP_ERROR", "Auth failed", http_status=401)

    output = tmp_path / "run"
    summary = collect_outputs(inputs, Unauthenticated(), output, mode="retrieval-only")
    assert summary["collection_status"] == "BLOCKED"
    assert summary["status_counts"] == {"NOT_RUN": 2}
    assert all(record["error"]["http_status"] == 401 for record in _records(output))


def test_preflight_provider_gate_stops_all_draft_attempts(tmp_path):
    paths = _pack(tmp_path, approved=True)
    inputs = _inputs(paths, draft=True)
    api = FakeAPI(inputs, paths[3])
    api.modify = lambda _method, _path, _payload, response: {**response, "provider_ready": False}
    output = tmp_path / "run"
    summary = collect_outputs(inputs, api, output, mode="rag-draft")
    assert summary["collection_status"] == "BLOCKED"
    assert len(api.calls) == 1
    assert summary["provider_call_confirmed_count"] == 0


def test_transport_redirects_are_disabled():
    from drosophila_pd.ai_v2.collection import _NoRedirect
    from urllib.request import Request
    with pytest.raises(HTTPError):
        _NoRedirect().redirect_request(Request("http://localhost"), None, 302, "redirect", {}, "https://other.example")


def test_response_size_is_bounded_before_json_parsing():
    class Response:
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def read(self, limit): return b" " * limit

    class Opener:
        def open(self, request, *, timeout): return Response()

    client = WorkbenchAPIClient("http://localhost")
    client.opener = Opener()
    with pytest.raises(CollectionError, match="8 MiB"):
        client.request("GET", "/v1/ai/rag/status")
