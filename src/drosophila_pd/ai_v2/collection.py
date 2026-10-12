"""Development-only API output collection; never a scorer or model judge."""

from __future__ import annotations

import hashlib
import json
import math
import re
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


_SHA = re.compile(r"^[0-9a-f]{64}$")
_CASE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
_RESERVED_CASE_ID = re.compile(r"^(?:con|prn|aux|nul|com[1-9]|lpt[1-9])$", re.IGNORECASE)
_SECRET_KEYS = {"authorization", "proxy-authorization", "cookie", "set-cookie", "password",
                "api_key", "apikey", "access_token", "bearer_token", "secret", "token"}
_SECRET_TOKEN = re.compile(r"\b(?:sk-|ghp_|github_pat_)[A-Za-z0-9_-]{8,}")
_PATHS = {"/v1/ai/rag/status", "/v1/ai/rag/retrieve", "/v1/ai/rag/draft"}
_MAX_RESPONSE = 8 * 1024 * 1024


class CollectionError(RuntimeError):
    def __init__(self, code: str, message: str, *, http_status: int | None = None):
        super().__init__(message)
        self.code = code
        self.http_status = http_status


class APIClient(Protocol):
    def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]: ...


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise HTTPError(req.full_url, code, "redirects are disabled", headers, fp)


def redact(value: Any, secrets: tuple[str, ...] = ()) -> Any:
    """Do not retain credentials even if an API echoes them back."""
    if isinstance(value, dict):
        return {key: "[REDACTED]" if str(key).casefold() in _SECRET_KEYS
                else redact(item, secrets) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item, secrets) for item in value]
    if isinstance(value, str):
        for secret in secrets:
            if secret:
                value = value.replace(secret, "[REDACTED]")
        return _SECRET_TOKEN.sub("[REDACTED]", value)
    return value


class WorkbenchAPIClient:
    """Small bounded transport. No redirects, retries, job APIs or CLI secrets."""

    def __init__(self, base_url: str, *, token: str = "", timeout: float = 30,
                 allow_remote: bool = False):
        parsed = urlsplit(base_url)
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path not in {"", "/"}):
            raise ValueError("Workbench URL must be an HTTP(S) origin without credentials, path or query")
        if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            if not allow_remote or parsed.scheme != "https":
                raise ValueError("remote Workbench needs explicit permission and HTTPS")
        if not math.isfinite(timeout) or not 0 < timeout <= 60:
            raise ValueError("timeout must be between 0 and 60 seconds")
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self.opener = build_opener(_NoRedirect())

    def request(self, method: str, path: str, payload=None) -> dict[str, Any]:
        if path not in _PATHS or (method, path) not in {
            ("GET", "/v1/ai/rag/status"), ("POST", "/v1/ai/rag/retrieve"),
            ("POST", "/v1/ai/rag/draft"),
        }:
            raise ValueError("collector can call only status, retrieval and draft endpoints")
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        data = _json_bytes(payload) if payload is not None else None
        req = Request(self.base_url + path, data=data, headers=headers, method=method)
        try:
            with self.opener.open(req, timeout=self.timeout) as response:
                raw = response.read(_MAX_RESPONSE + 1)
        except HTTPError as error:
            # Untrusted HTTP bodies may contain credentials or server internals.
            # Retain the status, not the body or request headers.
            error.close()
            raise CollectionError("HTTP_ERROR", "Workbench request failed", http_status=error.code) from None
        except (TimeoutError, URLError, OSError) as error:
            code = "TIMEOUT" if isinstance(error, TimeoutError) or isinstance(getattr(error, "reason", None), TimeoutError) else "TRANSPORT_ERROR"
            raise CollectionError(code, "Workbench transport failed") from None
        if len(raw) > _MAX_RESPONSE:
            raise CollectionError("RESPONSE_TOO_LARGE", "Workbench response exceeds 8 MiB")
        try:
            result = json.loads(raw.decode("utf-8"), parse_constant=_invalid_constant)
        except (UnicodeDecodeError, ValueError):
            raise CollectionError("INVALID_JSON", "Workbench did not return JSON") from None
        if not isinstance(result, dict):
            raise CollectionError("INVALID_RESPONSE", "Workbench response must be an object")
        return result


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _invalid_constant(value: str) -> None:
    raise ValueError("non-finite JSON number")


def load_collection_inputs(corpus_path: Path, rubric_path: Path, *, mode: str,
                           allow_provider_calls: bool = False,
                           manifest_path: Path | None = None) -> dict[str, Any]:
    """Validate inputs before allocating artifacts or making any API request."""
    if mode not in {"retrieval-only", "rag-draft"}:
        raise ValueError("unknown collection mode")
    for path in (corpus_path, rubric_path, *((manifest_path,) if manifest_path else ())):
        name = str(path.resolve()).casefold()
        if any(marker in name for marker in ("heldout", "held-out", "held_out", "sealed")):
            raise ValueError("collector refuses validation/sealed input paths")
    rubric_bytes = rubric_path.read_bytes()
    rubric = json.loads(rubric_bytes.decode("utf-8"), parse_constant=_invalid_constant)
    if not isinstance(rubric, dict) or rubric.get("partition") != "DEVELOPMENT":
        raise ValueError("collector accepts DEVELOPMENT references only")
    if rubric.get("schema_version") not in {
        "ai-v2-assistant-reference-draft-1", "ai-v2-assistant-reference-reviewed-1",
    }:
        raise ValueError("unsupported collection reference schema")
    task_type = rubric.get("task_type", "SOFTWARE_POLICY_QA")
    if task_type not in {"SOFTWARE_POLICY_QA", "PROTOCOL_DRAFT_EXTRACTION"}:
        raise ValueError("unknown reference task_type")
    cases = rubric.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("reference needs a non-empty case list")
    input_field = "question" if task_type == "SOFTWARE_POLICY_QA" else "protocol_text"
    seen: set[str] = set()
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("reference cases must be objects")
        case_id = case.get("case_id")
        if (not isinstance(case_id, str) or not _CASE_ID.fullmatch(case_id)
                or _RESERVED_CASE_ID.fullmatch(case_id) or case_id.casefold() in seen):
            raise ValueError("case IDs must be unique, safe filename identifiers")
        seen.add(case_id.casefold())
        text = case.get(input_field)
        if not isinstance(text, str) or not 0 < len(text.strip()) <= 20_000:
            raise ValueError(f"{case_id} needs runtime-sized {input_field}")
    corpus_bytes = corpus_path.read_bytes()
    corpus_sha = _hash(corpus_bytes)
    if rubric.get("corpus_sha256") != corpus_sha:
        raise ValueError("reference corpus hash does not match exact bytes")
    protocol = rubric.get("evaluation_protocol_draft", {})
    k = protocol.get("retrieval_k") if isinstance(protocol, dict) else None
    if isinstance(k, bool) or not isinstance(k, int) or not 1 <= k <= 20:
        raise ValueError("reference must declare runtime-valid retrieval_k")
    if mode == "rag-draft":
        if task_type != "PROTOCOL_DRAFT_EXTRACTION":
            raise ValueError("policy questions cannot be collected through the protocol-draft endpoint")
        if not allow_provider_calls:
            raise ValueError("draft collection requires explicit --allow-provider-calls")
        reviewers = rubric.get("reviewer_ids")
        if (rubric.get("status") != "APPROVED" or not isinstance(reviewers, list) or not reviewers
                or any(not isinstance(item, str) or not item.strip() for item in reviewers)):
            raise ValueError("draft collection needs a new approved reference snapshot with named reviewers")
        privacy = rubric.get("privacy_decision", {})
        if (not isinstance(privacy, dict) or privacy.get("status") != "APPROVED"
                or privacy.get("corpus_text_sharing_approved") is not True
                or privacy.get("protocol_text_sharing_approved") is not True
                or not isinstance(privacy.get("provider_id"), str) or not privacy["provider_id"].strip()
                or not isinstance(privacy.get("provider_endpoint"), str) or not privacy["provider_endpoint"].strip()):
            raise ValueError("draft collection needs an explicitly approved provider/data policy")
        if manifest_path is None:
            raise ValueError("draft collection needs the exact reviewed runtime manifest")
    manifest_sha = None
    if manifest_path is not None:
        from drosophila_pd.workbench.rag import load_frozen_evidence_corpus

        # Loader verifies existing bytes/attestations and writes nothing until retrieval.
        snapshot = load_frozen_evidence_corpus(manifest_path, retrieval_log_path=manifest_path.parent / "unused-collector-log.jsonl")
        if snapshot.corpus_sha256 != corpus_sha:
            raise ValueError("runtime manifest corpus differs from reference corpus")
        manifest_sha = snapshot.manifest_sha256
        if mode == "rag-draft" and (
            not snapshot.provider_sharing_approved or not snapshot.protocol_text_sharing_approved
            or snapshot.approved_provider_id != privacy["provider_id"]
            or snapshot.approved_provider_endpoint != privacy["provider_endpoint"]
        ):
            raise ValueError("runtime manifest does not match reviewed provider/data policy")
    return {"rubric": rubric, "input_field": input_field, "task_type": task_type, "mode": mode,
            "expected_manifest_sha256": manifest_sha,
            "protected_input_roots": list({str(path.resolve().parent) for path in
                                           (corpus_path, rubric_path, *((manifest_path,) if manifest_path else ()))}),
            "corpus_sha256": corpus_sha, "rubric_sha256": _hash(rubric_bytes), "retrieval_k": k}


def _identity(payload: dict[str, Any], inputs: dict[str, Any], manifest_sha: str) -> None:
    if not isinstance(payload, dict):
        raise CollectionError("INVALID_RESPONSE", "runtime identity must be an object")
    if payload.get("corpus_sha256") != inputs["corpus_sha256"] or payload.get("manifest_sha256") != manifest_sha:
        raise CollectionError("CORPUS_DRIFT", "runtime corpus/manifest identity changed or mismatched")


def _evidence(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise CollectionError("INVALID_RESPONSE", "retrieved_evidence must be a list of objects")
    seen = set()
    for item in value:
        if any(not isinstance(item.get(key), str) or not item[key].strip()
               for key in ("source_id", "chunk_id", "text", "citation")):
            raise CollectionError("INVALID_RESPONSE", "evidence lacks source identity or text")
        pair = (item["source_id"], item["chunk_id"])
        if pair in seen:
            raise CollectionError("INVALID_RESPONSE", "duplicate evidence identities")
        seen.add(pair)
    return value


def _project_draft(draft: dict[str, Any], record: dict[str, Any], inputs: dict[str, Any]) -> None:
    from drosophila_pd.workbench import intake

    def valid(condition: bool, message: str) -> None:
        if not condition:
            raise CollectionError("DRAFT_CONTRACT_VIOLATION", message)

    valid(draft.get("schema_version") == "protocol-rag-intake-draft-1", "unexpected draft schema")
    valid(draft.get("source_sha256") == record["input_sha256"], "draft input hash differs from submitted case")
    for flag in ("approved", "study_created", "mapping_created"):
        valid(draft.get(flag) is False, "draft creation/approval flags must remain false")
    status = draft.get("status")
    valid(status in {"DRAFT_REQUIRES_RESEARCHER_REVIEW", "ABSTAINED_NO_EVIDENCE"}, "unexpected draft status")
    fields = draft.get("proposed_fields")
    valid(isinstance(fields, dict) and set(fields).issubset(intake._ALLOWED_FIELDS - {"missing_fields"}), "unexpected proposed fields")
    valid(not intake._contains_forbidden_key(fields), "draft contains executable/mapping fields")
    for field in ("name", *intake._REQUIRED_FIELDS):
        if field in fields:
            valid(isinstance(fields[field], str) and bool(fields[field].strip()), "draft scalar fields must be non-empty strings")
    if "context" in fields:
        context = fields["context"]
        valid(isinstance(context, dict) and bool(context)
              and set(context).issubset(intake._ALLOWED_CONTEXT_FIELDS)
              and all(isinstance(value, str) and value.strip() for value in context.values()), "invalid context fields")
    for field, allowed in (("candidate_suggestions", intake._ALLOWED_SUGGESTION_FIELDS),
                           ("control_suggestions", intake._ALLOWED_CONTROL_FIELDS)):
        if field in fields:
            suggestions = fields[field]
            valid(isinstance(suggestions, list)
                  and all(isinstance(item, dict) and set(item).issubset(allowed - {"sources"})
                          and all(isinstance(value, str) and value.strip() for value in item.values())
                          and ("expected_direction" not in item or item["expected_direction"] in intake._ALLOWED_DIRECTIONS)
                          for item in suggestions), "invalid suggestion fields")
    missing = draft.get("missing_fields")
    valid(isinstance(missing, list) and all(isinstance(item, str) for item in missing), "invalid missing fields")
    expected_missing = {key for key in intake._REQUIRED_FIELDS if not isinstance(fields.get(key), str) or not fields[key].strip()}
    valid(set(missing) == expected_missing and len(missing) == len(set(missing)), "missing fields disagree with runtime core fields")
    evidence = _evidence(draft.get("rag", {}).get("retrieved_evidence"))
    citations = fields.get("citations", [])
    valid(isinstance(citations, list) and all(isinstance(item, dict) for item in citations), "invalid citations")
    pairs = {(item["source_id"], item["chunk_id"]) for item in evidence}
    valid(all(isinstance(item.get("source_id"), str) and isinstance(item.get("chunk_id"), str)
              and (item["source_id"], item["chunk_id"]) in pairs for item in citations), "citations were not retrieved")
    record.update(retrieved_evidence=evidence, citations=citations, missing_fields=missing)
    if status == "ABSTAINED_NO_EVIDENCE":
        valid(not evidence and not fields, "no-evidence abstention must be empty")
        record.update(status="ABSTAINED_NO_EVIDENCE", provider_called=False)
    else:
        valid(bool(evidence), "draft must have evidence")
        provenance = draft.get("provenance")
        valid(isinstance(provenance, dict), "draft has no provider provenance")
        valid(all(isinstance(provenance.get(key), str) and provenance[key].strip()
                  for key in ("provider_id", "model_id", "prompt_version")), "draft has incomplete provider provenance")
        valid(provenance["provider_id"] == inputs["rubric"]["privacy_decision"]["provider_id"], "provider differs from reviewed identity")
        record.update(status="DRAFT_COLLECTED", provider_called=True,
                      provider_id=provenance["provider_id"], model_id=provenance["model_id"],
                      prompt_version=provenance["prompt_version"])
    record["evaluator_projection"] = {
        "case_id": record["case_id"], "status": "COMPLETED" if status == "DRAFT_REQUIRES_RESEARCHER_REVIEW" else "ABSTAINED",
        "fields": {key: value for key, value in fields.items() if key != "citations"},
        "missing_fields": missing, "citations": citations, "schema_valid": True,
        "retrieved_chunk_ids": [item["chunk_id"] for item in evidence],
    }


def collect_outputs(inputs: dict[str, Any], client: APIClient, output_dir: Path, *, mode: str,
                    expected_manifest_sha256: str | None = None, secrets: tuple[str, ...] = (),
                    test_only: bool = False) -> dict[str, Any]:
    """Persist each case immediately; never fabricate failed outputs as abstentions."""
    if mode not in {"retrieval-only", "rag-draft"} or mode != inputs.get("mode"):
        raise ValueError("unknown collection mode")
    if isinstance(client, WorkbenchAPIClient) and client.token:
        secrets = (*secrets, client.token)
    if (expected_manifest_sha256 is not None and inputs.get("expected_manifest_sha256") is not None
            and expected_manifest_sha256 != inputs["expected_manifest_sha256"]):
        raise ValueError("manifest override differs from reviewed snapshot")
    expected_manifest_sha256 = expected_manifest_sha256 or inputs.get("expected_manifest_sha256")
    if expected_manifest_sha256 is not None and not _SHA.fullmatch(expected_manifest_sha256):
        raise ValueError("expected manifest hash must be a lowercase SHA-256")
    if any(output_dir.resolve().is_relative_to(Path(root)) for root in inputs["protected_input_roots"]):
        raise ValueError("output directory must be outside input/manifest package directories")
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "cases").mkdir()
    records = []
    files: dict[str, str] = {}

    def write(name: str, value: Any) -> None:
        data = _json_bytes(redact(value, secrets))
        with (output_dir / name).open("xb") as stream:
            stream.write(data)
        files[name] = _hash(data)

    summary = {"schema_version": "ai-v2-output-collection-1", "partition": "DEVELOPMENT",
               "mode": mode, "task_type": inputs["task_type"], "retrieval_k": inputs["retrieval_k"],
               "corpus_sha256": inputs["corpus_sha256"], "rubric_sha256": inputs["rubric_sha256"],
               "started_at": datetime.now(UTC).isoformat(), "test_only": test_only,
               "collection_status": "IN_PROGRESS", "independent_review_claim": False,
               "api_origin": client.base_url if isinstance(client, WorkbenchAPIClient) else None,
               "synthetic_fixture": inputs["rubric"].get("synthetic_fixture", False),
               "reference_status": inputs["rubric"].get("status"),
               "reviewer_ids": inputs["rubric"].get("reviewer_ids", []),
               "scoring_status": "NOT_RUN", "human_claim_annotations": "NOT_COLLECTED",
               "heldout_status": "LOCKED_NOT_RUN"}
    write("run_config.json", summary)
    blocked: CollectionError | None = None
    manifest_sha = ""
    version_identity = None
    try:
        readiness = client.request("GET", "/v1/ai/rag/status")
        if not isinstance(readiness, dict):
            raise CollectionError("INVALID_RESPONSE", "readiness must be an object")
        write("runtime_status.json", readiness)
        manifest_sha = readiness.get("manifest_sha256", "")
        if not isinstance(manifest_sha, str) or not _SHA.fullmatch(manifest_sha):
            raise CollectionError("NOT_READY", "runtime has no valid manifest identity")
        _identity(readiness, inputs, expected_manifest_sha256 or manifest_sha)
        if readiness.get("retriever_configured") is not True or readiness.get("status") != "RETRIEVAL_READY":
            raise CollectionError("NOT_READY", "retrieval runtime is not ready")
        if mode == "rag-draft" and readiness.get("provider_ready") is not True:
            raise CollectionError("PROVIDER_NOT_READY", "runtime provider/sharing gates are not ready")
    except CollectionError as error:
        blocked = error
    summary["manifest_sha256"] = manifest_sha or None
    summary["collector_code_sha256"] = _hash(Path(__file__).read_bytes())

    for index, case in enumerate(inputs["rubric"]["cases"], start=1):
        started = time.perf_counter()
        text = case[inputs["input_field"]]
        record = {"schema_version": "ai-v2-collected-case-1", "case_id": case["case_id"],
                  "started_at": datetime.now(UTC).isoformat(),
                  "ordinal": index, "mode": mode, "status": "NOT_RUN", "input_sha256": _hash(text.encode("utf-8")),
                  "corpus_sha256": inputs["corpus_sha256"], "manifest_sha256": manifest_sha or None,
                  "rubric_sha256": inputs["rubric_sha256"], "retrieved_evidence": [], "draft": None,
                  "citations": [], "missing_fields": None, "provider_called": False,
                  "draft_request_attempted": False, "provider_id": None, "model_id": None,
                  "prompt_version": None, "error": None, "evaluator_projection": None,
                  "timing_seconds": {}, "test_only": test_only}
        stage = "preflight"
        try:
            if blocked is not None:
                raise blocked
            stage = "retrieval"
            step = time.perf_counter()
            try:
                retrieval = client.request("POST", "/v1/ai/rag/retrieve", {"query": text, "k": inputs["retrieval_k"]})
            finally:
                record["timing_seconds"]["retrieval"] = time.perf_counter() - step
            record["retrieval_response"] = retrieval
            _identity(retrieval, inputs, manifest_sha)
            record["retrieved_evidence"] = _evidence(retrieval.get("retrieved_evidence"))
            if retrieval.get("provider_called") is not False or retrieval.get("status") not in {"MATCHES_FOUND", "NO_APPROVED_EVIDENCE_MATCH"}:
                raise CollectionError("INVALID_RESPONSE", "retrieval status/provider behavior is invalid")
            if (retrieval["status"] == "MATCHES_FOUND") != bool(record["retrieved_evidence"]) or len(record["retrieved_evidence"]) > inputs["retrieval_k"]:
                raise CollectionError("INVALID_RESPONSE", "retrieval status/count differs from evidence")
            record["status"] = "RETRIEVED" if record["retrieved_evidence"] else "NO_MATCH"
            if mode == "rag-draft":
                stage = "draft"
                record.update(draft_request_attempted=True, provider_called=None)
                step = time.perf_counter()
                try:
                    draft = client.request("POST", "/v1/ai/rag/draft", {"protocol_text": text, "k": inputs["retrieval_k"]})
                finally:
                    record["timing_seconds"]["draft"] = time.perf_counter() - step
                record["draft"] = draft
                if not isinstance(draft, dict):
                    raise CollectionError("INVALID_RESPONSE", "draft must be an object")
                _identity(draft.get("rag", {}), inputs, manifest_sha)
                _project_draft(draft, record, inputs)
                if record["provider_called"] is True:
                    identity = tuple(record[key] for key in ("provider_id", "model_id", "prompt_version"))
                    if version_identity is not None and identity != version_identity:
                        record["evaluator_projection"] = None
                        raise CollectionError("VERSION_DRIFT", "provider/model/prompt changed during collection")
                    version_identity = identity
        except CollectionError as error:
            record["status"] = "NOT_RUN" if stage == "preflight" else "ERROR"
            record["error"] = {"stage": stage, "code": error.code, "message": str(error), "http_status": error.http_status}
            if error.code in {"CORPUS_DRIFT", "VERSION_DRIFT"} or error.http_status in {401, 403}:
                blocked = error
        record["timing_seconds"]["total"] = time.perf_counter() - started
        record["finished_at"] = datetime.now(UTC).isoformat()
        record = redact(record, secrets)
        write("cases/" + case["case_id"] + ".json", record)
        records.append(record)
    write("case_outputs.json", {"schema_version": "ai-v2-collected-outputs-1", "cases": records})
    counts = dict(Counter(record["status"] for record in records))
    summary.update(finished_at=datetime.now(UTC).isoformat(), case_count=len(records), status_counts=counts,
                   observed_generation_identity=dict(zip(("provider_id", "model_id", "prompt_version"), version_identity)) if version_identity else None,
                   collection_status="BLOCKED" if counts.get("NOT_RUN") == len(records) else
                   "PARTIAL_FAILURE" if counts.get("ERROR", 0) or counts.get("NOT_RUN", 0) else "COMPLETE",
                   provider_call_confirmed_count=sum(record["provider_called"] is True for record in records),
                   provider_call_unknown_count=sum(record["provider_called"] is None for record in records),
                   artifact_sha256=files.copy(),
                   note="Raw output collection only. Errors are not abstentions. No gold values or human support decisions were generated.")
    write("run_manifest.json", summary)
    return redact(summary, secrets)


__all__ = ["CollectionError", "WorkbenchAPIClient", "collect_outputs", "load_collection_inputs"]
