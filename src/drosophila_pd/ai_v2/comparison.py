"""Paired development experiments; no jobs, model judge or automatic approval."""

from __future__ import annotations

import hashlib
import json
import math
import statistics
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from .collection import load_collection_inputs, redact
from drosophila_pd.workbench import intake
from drosophila_pd.workbench.rag import load_frozen_evidence_corpus

SYSTEMS = ("manual_template", "llm_no_retrieval", "llm_rag")
PROMPT_VERSION = "protocol-intake-output-v2"
POLICY_VERSION = "paired-protocol-comparison-2"
VALID = {"COMPLETED", "ABSTAINED"}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encoded(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def safe_path(path: Path) -> Path:
    resolved = path.resolve()
    if any(s in str(resolved).casefold() for s in ("heldout", "held-out", "held_out", "sealed")):
        raise ValueError("validation/sealed paths are not permitted")
    return resolved


def read_json(path: Path) -> Any:
    return json.loads(safe_path(path).read_text(encoding="utf-8"),
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))


def citation_pair(cite: Any) -> tuple[str, str] | None:
    if (isinstance(cite, dict) and isinstance(cite.get("source_id"), str)
            and isinstance(cite.get("chunk_id"), str)):
        return cite["source_id"], cite["chunk_id"]
    return None


def prepare_inputs(corpus: Path, rubric: Path, manifest: Path | None = None,
                   *, generation: bool = False) -> dict[str, Any]:
    inputs = load_collection_inputs(corpus, rubric, mode="rag-draft" if generation else "retrieval-only",
                                    allow_provider_calls=generation, manifest_path=manifest)
    if inputs["task_type"] != "PROTOCOL_DRAFT_EXTRACTION" or inputs["retrieval_k"] != 5:
        raise ValueError("comparison requires protocol-extraction references and fixed k=5")
    for case in inputs["rubric"]["cases"]:
        required = case.get("required_fields")
        gold = case.get("gold_fields")
        if (not isinstance(required, list) or not required or len(set(required)) != len(required)
                or any(not isinstance(key, str) or key not in intake._ALLOWED_FIELDS - {"citations", "missing_fields"}
                       for key in required)
                or not isinstance(gold, dict) or any(key not in gold for key in required)):
            raise ValueError("reference fields must align with the protocol draft schema")
        for key in ("gold_evidence_chunk_ids", "gold_missing_fields"):
            values = case.get(key)
            if (not isinstance(values, list) or any(not isinstance(x, str) or not x for x in values)
                    or len(values) != len(set(values))):
                raise ValueError("reference evidence/missing fields must be unique string lists")
        if not isinstance(case.get("gold_citations"), list):
            raise ValueError("reference citations must be a list")
    chunks = [json.loads(line) for line in safe_path(corpus).read_text(encoding="utf-8").splitlines() if line.strip()]
    pairs = {(x["source_id"], x["chunk_id"]) for x in chunks}
    for case in inputs["rubric"]["cases"]:
        if not set(case["gold_evidence_chunk_ids"]).issubset({p[1] for p in pairs}):
            raise ValueError("gold evidence not in corpus")
        if any(citation_pair(x) not in pairs
               for x in case["gold_citations"]):
            raise ValueError("gold citation not in corpus")
    inputs["corpus_pairs"] = pairs
    return inputs


def manual_template(inputs: dict[str, Any]) -> dict[str, Any]:
    """Blank human worksheet, deliberately containing no reference answers."""
    return {"schema_version": "ai-v2-manual-comparator-1", "partition": "DEVELOPMENT",
            "corpus_sha256": inputs["corpus_sha256"], "rubric_sha256": inputs["rubric_sha256"],
            "note": "Fill from protocol, without gold or retrieval. PENDING is not a completed baseline.",
            "cases": [{"case_id": c["case_id"], "protocol_text": c["protocol_text"], "status": "PENDING",
                       "fields": {}, "missing_fields": [], "citations": [], "reviewer_ids": [],
                       "elapsed_seconds": None} for c in inputs["rubric"]["cases"]]}


def load_manual(path: Path | None, inputs: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}
    data = read_json(path)
    if (not isinstance(data, dict) or data.get("schema_version") != "ai-v2-manual-comparator-1"
            or data.get("partition") != "DEVELOPMENT"
            or any(data.get(k) != inputs[k] for k in ("corpus_sha256", "rubric_sha256"))
            or not isinstance(data.get("cases"), list)):
        raise ValueError("manual worksheet identity mismatch")
    expected = {c["case_id"]: c for c in inputs["rubric"]["cases"]}
    rows = {}
    for row in data["cases"]:
        key = row.get("case_id") if isinstance(row, dict) else None
        if key not in expected or key in rows or row.get("protocol_text") != expected[key]["protocol_text"]:
            raise ValueError("manual worksheet case/input mismatch")
        if row.get("status") not in VALID | {"PENDING", "ERROR"}:
            raise ValueError("invalid manual status")
        fields = row.get("fields")
        missing = row.get("missing_fields")
        citations = row.get("citations")
        if (not isinstance(fields, dict) or set(fields) - (intake._ALLOWED_FIELDS - {"citations", "missing_fields"})
                or intake._contains_forbidden_key(fields)
                or not isinstance(missing, list) or any(not isinstance(x, str) for x in missing)
                or len(missing) != len(set(missing))
                or not isinstance(citations, list)):
            raise ValueError("invalid manual output fields")
        for field_name in ("name", *intake._REQUIRED_FIELDS):
            if field_name in fields and (not isinstance(fields[field_name], str) or not fields[field_name].strip()):
                raise ValueError("manual scalar fields must be nonempty strings")
        if row["status"] in VALID:
            expected_missing = {field_name for field_name in intake._REQUIRED_FIELDS if field_name not in fields}
            if set(missing) != expected_missing or (row["status"] == "ABSTAINED" and (fields or citations)):
                raise ValueError("manual missing fields or abstention contradict the draft contract")
        elapsed = row.get("elapsed_seconds")
        if elapsed is not None and (isinstance(elapsed, bool) or not isinstance(elapsed, (int, float))
                                    or not math.isfinite(elapsed) or elapsed < 0):
            raise ValueError("manual elapsed time must be nonnegative or null")
        reviewers = row.get("reviewer_ids")
        if row["status"] != "PENDING" and (not isinstance(reviewers, list) or not reviewers
                or any(x not in inputs["rubric"]["reviewer_ids"] for x in reviewers)):
            raise ValueError("manual outputs need an actual named internal reviewer")
        rows[key] = row
    return rows


def claim_units(record: dict[str, Any]) -> list[dict[str, Any]]:
    """Scalar string assertions in raw generation, not auto support judgments."""
    value = record.get("raw_output")
    units = []

    def visit(item: Any, path: str) -> None:
        if isinstance(item, dict):
            for key in sorted(item):
                if key not in {"citations", "missing_fields"}:
                    visit(item[key], path + "/" + key)
        elif isinstance(item, list):
            for index, child in enumerate(item):
                visit(child, path + "/" + str(index))
        elif isinstance(item, str) and item.strip():
            identity = [record["system_id"], record["case_id"], path, item]
            units.append({"claim_id": digest(encoded(identity)), "field_path": path, "text": item})

    visit(value, "")
    return units


def _gold_set_precision_at_k(retrieved: list[str], gold: list[str], *, k: int = 5) -> float | None:
    """Per-case precision using explicitly gold-labeled IDs and actual hits."""
    if not gold:
        return None
    selected = retrieved[:k]
    if len(selected) != len(set(selected)):
        raise ValueError("retrieval results must be unique top-k")
    return len(set(selected) & set(gold)) / len(selected) if selected else 0.0


def _required_comparison_row(record: Mapping[str, Any], diagnostic_case_ids: set[str]) -> bool:
    """The manual arm is required for protocol cases, not the retrieval-only probe."""
    return not (record.get("system_id") == "manual_template"
                and record.get("case_id") in diagnostic_case_ids)


def raw_output_schema_valid(value: Any) -> bool:
    """Validate the model-facing protocol JSON contract before intake sanitizing it."""
    if isinstance(value, str):
        try:
            def no_duplicate_keys(pairs):
                result = {}
                for key, item in pairs:
                    if key in result:
                        raise ValueError("duplicate JSON key")
                    result[key] = item
                return result
            value = json.loads(value, object_pairs_hook=no_duplicate_keys,
                               parse_constant=lambda _: (_ for _ in ()).throw(ValueError("invalid JSON constant")))
        except (json.JSONDecodeError, TypeError, ValueError):
            return False
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        return False
    if set(value) - intake._ALLOWED_FIELDS:
        return False
    required = intake.provider_response_format()["json_schema"]["schema"]["required"]
    if not set(required).issubset(value):
        return False

    def text(item: Any) -> bool:
        return isinstance(item, str) and bool(item.strip())

    for key in ("name", *intake._REQUIRED_FIELDS):
        if key in value and not text(value[key]):
            return False
    if "context" in value:
        context = value["context"]
        if (not isinstance(context, Mapping) or not context
                or any(not isinstance(key, str) or key not in intake._ALLOWED_CONTEXT_FIELDS
                       or not text(item) for key, item in context.items())):
            return False
    for key, allowed in (("candidate_suggestions", intake._ALLOWED_SUGGESTION_FIELDS),
                         ("control_suggestions", intake._ALLOWED_CONTROL_FIELDS)):
        if key not in value:
            continue
        suggestions = value[key]
        if not isinstance(suggestions, list):
            return False
        for item in suggestions:
            if not isinstance(item, Mapping) or any(not isinstance(k, str) or k not in allowed for k in item):
                return False
            for field, child in item.items():
                if field == "expected_direction":
                    if child not in intake._ALLOWED_DIRECTIONS:
                        return False
                elif field == "sources":
                    if (not isinstance(child, list)
                            or any(not isinstance(source, Mapping) or not source
                                   or any(not isinstance(sk, str) or sk not in intake._ALLOWED_SOURCE_FIELDS
                                          or not text(sv) for sk, sv in source.items())
                                   for source in child)):
                        return False
                elif not text(child):
                    return False
    if "citations" in value:
        citations = value["citations"]
        if (not isinstance(citations, list)
                or any(not isinstance(citation, Mapping)
                       or set(citation) != {"source_id", "chunk_id"}
                       or not text(citation.get("source_id")) or not text(citation.get("chunk_id"))
                       for citation in citations)):
            return False
    if "missing_fields" in value:
        missing = value["missing_fields"]
        if (not isinstance(missing, list) or any(not text(item) for item in missing)
                or len(missing) != len(set(missing)) or not set(missing).issubset(intake._REQUIRED_FIELDS)):
            return False
    return True


def _processed_draft_schema_valid(draft: Any, *, system_id: str, input_sha256: str) -> bool:
    """Validate the actual post-intake draft shape; never infer answer correctness."""
    if not isinstance(draft, dict):
        return False
    is_rag = system_id == "llm_rag"
    required = {"schema_version", "status", "source_uri", "source_sha256", "prompt_version", "provider_id",
                "created_at", "proposed_fields", "missing_fields", "guardrail_events", "approved",
                "study_created", "mapping_created"}
    allowed = required | ({"rag", "provenance"} if is_rag else set())
    if (set(draft) - allowed or not required.issubset(draft)
            or draft.get("schema_version") != ("protocol-rag-intake-draft-1" if is_rag else "protocol-intake-draft-1")
            or draft.get("source_sha256") != input_sha256
            or not isinstance(draft.get("prompt_version"), str) or not draft["prompt_version"].strip()
            or not isinstance(draft.get("created_at"), str) or not draft["created_at"].strip()
            or any(draft.get(flag) is not False for flag in ("approved", "study_created", "mapping_created"))):
        return False
    if draft.get("source_uri") is not None and not isinstance(draft.get("source_uri"), str):
        return False
    fields = draft.get("proposed_fields")
    if (not isinstance(fields, dict)
            or set(fields) - (intake._ALLOWED_FIELDS - {"missing_fields"})
            or intake._contains_forbidden_key(fields)):
        return False
    def text(item: Any) -> bool:
        return isinstance(item, str) and bool(item.strip())
    for key in ("name", *intake._REQUIRED_FIELDS):
        if key in fields and not text(fields[key]):
            return False
    if "context" in fields:
        context = fields["context"]
        if (not isinstance(context, dict) or not context
                or any(key not in intake._ALLOWED_CONTEXT_FIELDS or not text(item)
                       for key, item in context.items())):
            return False
    for key, allowed_fields in (("candidate_suggestions", intake._ALLOWED_SUGGESTION_FIELDS),
                                ("control_suggestions", intake._ALLOWED_CONTROL_FIELDS)):
        if key not in fields:
            continue
        items = fields[key]
        if not isinstance(items, list):
            return False
        for item in items:
            if (not isinstance(item, dict) or set(item) - allowed_fields
                    or any(field != "expected_direction" and field != "sources" and not text(value)
                           for field, value in item.items())
                    or ("expected_direction" in item and item["expected_direction"] not in intake._ALLOWED_DIRECTIONS)):
                return False
            if "sources" in item and (not isinstance(item["sources"], list)
                    or any(not isinstance(source, dict) or not source
                           or set(source) - intake._ALLOWED_SOURCE_FIELDS
                           or any(not text(value) for value in source.values())
                           for source in item["sources"])):
                return False
    missing = draft.get("missing_fields")
    if (not isinstance(missing, list) or any(not text(item) for item in missing)
            or len(missing) != len(set(missing))
            or set(missing) != {key for key in intake._REQUIRED_FIELDS if not text(fields.get(key))}):
        return False
    guardrails = draft.get("guardrail_events")
    if not isinstance(guardrails, list) or any(not text(item) for item in guardrails):
        return False
    citations = fields.get("citations", [])
    if not isinstance(citations, list):
        return False
    if is_rag:
        rag = draft.get("rag")
        base_rag_fields = {"corpus_id", "corpus_sha256", "manifest_sha256", "query_sha256",
                           "retrieval_sha256", "retrieved_evidence"}
        generated_rag_fields = {"provider_sharing_approved", "protocol_text_sharing_approved",
                                "citation_validation", "evidence_citations"}
        if (not isinstance(rag, dict) or not base_rag_fields.issubset(rag)
                or set(rag) - (base_rag_fields | generated_rag_fields)
                or any(not text(rag.get(key)) for key in ("corpus_id",))
                or any(not isinstance(rag.get(key), str) or len(rag[key]) != 64
                       or any(char not in "0123456789abcdef" for char in rag[key])
                       for key in ("corpus_sha256", "manifest_sha256", "query_sha256", "retrieval_sha256"))
                or not isinstance(rag.get("retrieved_evidence"), list)):
            return False
        evidence = rag["retrieved_evidence"]
        evidence_pairs = set()
        for item in evidence:
            if (not isinstance(item, dict)
                    or set(item) != {"source_id", "citation", "chunk_id", "retrieval_score", "provenance", "access_class", "text"}
                    or not text(item.get("source_id")) or not text(item.get("chunk_id"))
                    or not text(item.get("text")) or not text(item.get("citation"))
                    or isinstance(item.get("retrieval_score"), bool)
                    or not isinstance(item.get("retrieval_score"), (int, float))
                    or not math.isfinite(item["retrieval_score"])
                    or not text(item.get("provenance")) or not text(item.get("access_class"))):
                return False
            pair = (item["source_id"], item["chunk_id"])
            if pair in evidence_pairs:
                return False
            evidence_pairs.add(pair)
        for item in citations:
            if (not isinstance(item, dict) or not {"source_id", "chunk_id"}.issubset(item)
                    or set(item) - {"source_id", "chunk_id", "citation", "locator"}
                    or not text(item.get("source_id")) or not text(item.get("chunk_id"))
                    or (item["source_id"], item["chunk_id"]) not in evidence_pairs
                    or any(k in item and not text(item[k]) for k in ("citation", "locator"))):
                return False
        if draft.get("status") == "ABSTAINED_NO_EVIDENCE":
            return (set(rag) == base_rag_fields and not evidence and not fields
                    and draft.get("provider_id") is None and not ("provenance" in draft)
                    and {"no_approved_evidence_match", "provider_not_called"}.issubset(set(guardrails)))
        provenance = draft.get("provenance")
        provenance_fields = {"provider_id", "model_id", "prompt_version", "corpus_sha256",
                             "manifest_sha256", "retrieval_sha256", "generator_output_sha256"}
        if (draft.get("status") != "DRAFT_REQUIRES_RESEARCHER_REVIEW" or not evidence
                or set(rag) != base_rag_fields | generated_rag_fields
                or rag.get("provider_sharing_approved") is not True
                or rag.get("protocol_text_sharing_approved") is not True
                or rag.get("citation_validation") not in {"PASS", "PASS_WITH_UNSUPPORTED_CITATIONS_REMOVED",
                                                           "UNSUPPORTED_CITATIONS_REMOVED", "NO_CITATIONS_RETURNED"}
                or not isinstance(rag.get("evidence_citations"), list)
                or not isinstance(provenance, dict) or set(provenance) != provenance_fields
                or any(not text(provenance.get(key)) for key in ("provider_id", "model_id", "prompt_version"))
                or provenance.get("provider_id") != draft.get("provider_id")
                or provenance.get("prompt_version") != draft.get("prompt_version")
                or any(provenance.get(key) != rag.get(source_key)
                       for key, source_key in (("corpus_sha256", "corpus_sha256"),
                                               ("manifest_sha256", "manifest_sha256"),
                                               ("retrieval_sha256", "retrieval_sha256")))
                or any(not isinstance(provenance.get(key), str) or len(provenance[key]) != 64
                       or any(char not in "0123456789abcdef" for char in provenance[key])
                       for key in ("generator_output_sha256",))):
            return False
        if any(not isinstance(item, dict) or set(item) != {"source_id", "chunk_id", "citation", "locator"}
               or not text(item.get("source_id")) or not text(item.get("chunk_id"))
               or not text(item.get("citation")) or not text(item.get("locator"))
               or (item["source_id"], item["chunk_id"]) not in evidence_pairs
               for item in rag["evidence_citations"]):
            return False
        if citations != rag["evidence_citations"]:
            return False
    else:
        if draft.get("status") != "DRAFT_REQUIRES_RESEARCHER_REVIEW" or not text(draft.get("provider_id")):
            return False
        for item in citations:
            if (not isinstance(item, dict) or not item
                    or set(item) - intake._ALLOWED_SOURCE_FIELDS
                    or any(not text(value) for value in item.values())):
                return False
    return True


def _schema_metrics(rows: list[dict[str, Any]], *, denominator: int, system_id: str) -> dict[str, Any]:
    raw_statuses = Counter(row.get("raw_schema_status", "NOT_RECORDED") for row in rows)
    raw_observed = [row for row in rows if row.get("raw_schema_status") in {"VALID", "INVALID"}]
    raw_valid = sum(row.get("raw_schema_status") == "VALID" for row in raw_observed)
    processed_statuses = Counter(row.get("processed_schema_status", "NOT_RECORDED") for row in rows)
    processed_observed = [row for row in rows if row.get("processed_schema_status") in {"VALID", "INVALID"}]
    processed_valid = sum(row.get("processed_schema_status") == "VALID" for row in processed_observed)
    return {
        "raw_output_schema": {
            "status_counts": dict(raw_statuses), "response_denominator": len(raw_observed),
            "valid_count": raw_valid,
            "valid_rate_among_responses": raw_valid / len(raw_observed) if raw_observed else None,
            "case_denominator": denominator,
            "valid_rate_per_case": raw_valid / denominator if denominator else None,
            "meaning": "raw provider JSON response; manual arm is human worksheet output, not provider output",
        },
        "processed_draft_schema": {
            "status_counts": dict(processed_statuses), "produced_denominator": len(processed_observed),
            "valid_count": processed_valid,
            "valid_rate_among_produced": processed_valid / len(processed_observed) if processed_observed else None,
            "case_denominator": denominator,
            "valid_rate_per_case": processed_valid / denominator if denominator and system_id != "manual_template" else None,
            "meaning": "post-sanitization Workbench draft; manual arm is not applicable",
        },
    }


class CapturedProvider:
    """Both arms call the SAME evidence-conditioned provider method/prompt."""
    def __init__(self, provider: Any):
        self.provider = provider
        self.provider_id = provider.provider_id
        self.model = provider.model
        self.endpoint = provider.endpoint
        self.raw = None
        self.attempted = False

    def extract_with_evidence(self, text: str, *, evidence: list[dict[str, Any]]) -> Any:
        self.attempted = True
        self.raw = self.provider.extract_with_evidence(text, evidence=evidence)
        return self.raw

    def extract(self, text: str, *, source_uri=None) -> Any:
        return self.extract_with_evidence(text, evidence=[])


class CapturedCorpus:
    def __init__(self, corpus):
        self.corpus = corpus
        self.hits = []

    def __getattr__(self, key):
        return getattr(self.corpus, key)

    def retrieve(self, text, *, k):
        hits = self.corpus.retrieve(text, k=k)
        self.hits = [hit.as_dict() for hit in hits]
        return hits


def run_comparison(inputs: dict[str, Any], manifest: Path, provider: Any, output_dir: Path,
                   *, manual_path: Path | None = None, secrets: tuple[str, ...] = (),
                   test_only: bool = False) -> dict[str, Any]:
    rubric = inputs["rubric"]
    privacy = rubric.get("privacy_decision", {})
    if (inputs.get("mode") != "rag-draft" or rubric.get("status") != "APPROVED"
            or provider.provider_id != privacy.get("provider_id")
            or provider.endpoint != privacy.get("provider_endpoint")):
        raise ValueError("generation requires approved inputs and exact provider binding")
    manual = load_manual(manual_path, inputs)
    output_dir = safe_path(output_dir)
    roots = inputs["protected_input_roots"] + ([str(safe_path(manual_path).parent)] if manual_path else [])
    if any(output_dir.is_relative_to(Path(root)) for root in roots):
        raise ValueError("run directory must be outside all input packages")
    snapshot = load_frozen_evidence_corpus(manifest, retrieval_log_path=output_dir / "retrieval.jsonl")
    if (snapshot.manifest_sha256 != inputs["expected_manifest_sha256"]
            or snapshot.corpus_sha256 != inputs["corpus_sha256"]
            or not snapshot.provider_sharing_approved or not snapshot.protocol_text_sharing_approved
            or snapshot.approved_provider_id != provider.provider_id
            or snapshot.approved_provider_endpoint != provider.endpoint):
        raise ValueError("manifest mismatch or sharing not approved")
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "cases").mkdir()
    files = {}

    def write(name, value):
        data = encoded(redact(value, secrets))
        with (output_dir / name).open("xb") as stream:
            stream.write(data)
        files[name] = digest(data)

    identity = (provider.provider_id, provider.model, provider.endpoint)
    config = {"schema_version": "ai-v2-comparison-run-2", "partition": "DEVELOPMENT",
              "policy_version": POLICY_VERSION, "prompt_version": PROMPT_VERSION,
              "provider_id": identity[0], "configured_model_id": identity[1], "provider_endpoint": identity[2],
              "corpus_sha256": inputs["corpus_sha256"], "rubric_sha256": inputs["rubric_sha256"],
              "manifest_sha256": inputs["expected_manifest_sha256"], "retrieval_k": 5,
              "started_at": datetime.now(UTC).isoformat(), "test_only": test_only,
              "synthetic_fixture": rubric.get("synthetic_fixture") is True,
              "independent_review_claim": False, "heldout_status": "LOCKED_NOT_RUN",
              "order": "case-major; alternate no-retrieval/RAG arm order by case ordinal; no retries",
              "manual_input_sha256": digest(safe_path(manual_path).read_bytes()) if manual_path else None,
              "code_sha256": {"comparison": digest(Path(__file__).read_bytes()),
                              "intake": digest(Path(intake.__file__).read_bytes())}}
    write("run_config.json", config)
    records = []
    blocked = False
    for index, case in enumerate(rubric["cases"]):
        order = ["manual_template", *(SYSTEMS[1:] if index % 2 == 0 else reversed(SYSTEMS[1:]))]
        for system in order:
            record = {"system_id": system, "case_id": case["case_id"], "status": "NOT_RUN",
                      "input_sha256": digest(case["protocol_text"].encode()), "fields": {},
                      "missing_fields": [], "citations": [], "retrieved_evidence": [],
                      "raw_response": None, "raw_output": None, "draft": None, "provider_called": False,
                      "provider_attempted": False, "raw_schema_valid": None,
                      "raw_schema_status": "NOT_OBSERVED", "processed_schema_valid": None,
                      "processed_schema_status": "NOT_PRODUCED",
                      "elapsed_seconds": None, "error": None, "started_at": datetime.now(UTC).isoformat()}
            if system == "manual_template":
                row = manual.get(case["case_id"])
                if row is not None and row["status"] != "PENDING":
                    record.update({key: row[key] for key in ("status", "fields", "missing_fields", "citations", "elapsed_seconds")})
                    record["raw_output"] = {**row["fields"], "citations": row["citations"], "missing_fields": row["missing_fields"]}
                    record["raw_response"] = record["raw_output"]
                    record["reviewer_ids"] = row["reviewer_ids"]
                    if row["status"] in VALID:
                        record["raw_schema_valid"] = raw_output_schema_valid(record["raw_response"])
                        record["raw_schema_status"] = "VALID" if record["raw_schema_valid"] else "INVALID"
                    else:
                        record["raw_schema_status"] = "NO_RESPONSE"
                record["processed_schema_status"] = "NOT_APPLICABLE_MANUAL_TEMPLATE"
                record["timing_source"] = "human_self_reported"
            elif not blocked:
                capture = CapturedProvider(provider)
                captured_corpus = CapturedCorpus(snapshot)
                start = time.perf_counter()
                try:
                    if (provider.provider_id, provider.model, provider.endpoint) != identity:
                        blocked = True
                        raise ValueError("provider configuration drift")
                    if system == "llm_rag":
                        draft = intake.create_rag_intake_draft(case["protocol_text"], captured_corpus, capture, k=5,
                                                              prompt_version=PROMPT_VERSION)
                        record["retrieved_evidence"] = draft["rag"]["retrieved_evidence"]
                    else:
                        draft = intake.create_intake_draft(case["protocol_text"], capture, prompt_version=PROMPT_VERSION)
                    # Preserve raw assertions/citations BEFORE downstream sanitization.
                    raw = intake._parse_provider_output(capture.raw) if capture.attempted else None
                    if capture.attempted:
                        record["raw_schema_valid"] = raw_output_schema_valid(capture.raw)
                        record["raw_schema_status"] = "VALID" if record["raw_schema_valid"] else "INVALID"
                    record.update(status="ABSTAINED" if draft["status"] == "ABSTAINED_NO_EVIDENCE" else "COMPLETED",
                                  draft=draft, raw_response=capture.raw, raw_output=raw,
                                  fields={k: v for k, v in draft["proposed_fields"].items() if k != "citations"},
                                  citations=draft["proposed_fields"].get("citations", []), missing_fields=draft["missing_fields"],
                                  provider_called=capture.attempted)
                    record["processed_schema_valid"] = _processed_draft_schema_valid(
                        draft, system_id=system, input_sha256=record["input_sha256"])
                    record["processed_schema_status"] = "VALID" if record["processed_schema_valid"] else "INVALID"
                    if (provider.provider_id, provider.model, provider.endpoint) != identity:
                        blocked = True
                        raise ValueError("provider configuration drift")
                except (OSError, RuntimeError, ValueError, TypeError) as error:
                    record.update(status="ERROR", error={"type": type(error).__name__, "message": "Generation failed; no retry."},
                                  provider_called=None if capture.attempted else False)
                    # Retain serializable raw failures for annotation; no untrusted error text.
                    try:
                        encoded(capture.raw)
                        record["raw_response"] = capture.raw
                        record["raw_output"] = intake._parse_provider_output(capture.raw)
                    except (ValueError, TypeError):
                        pass
                record["provider_attempted"] = capture.attempted
                if capture.attempted and record["raw_schema_status"] == "NOT_OBSERVED":
                    if capture.raw is None:
                        record["raw_schema_status"] = "NO_RESPONSE"
                    else:
                        record["raw_schema_valid"] = raw_output_schema_valid(capture.raw)
                        record["raw_schema_status"] = "VALID" if record["raw_schema_valid"] else "INVALID"
                elif not capture.attempted:
                    record["raw_schema_status"] = "NOT_CALLED"
                record["elapsed_seconds"] = time.perf_counter() - start
                record["timing_source"] = "in_process_retrieval_plus_generation"
                if system == "llm_rag":
                    record["retrieved_evidence"] = captured_corpus.hits
            elif system != "manual_template":
                record["raw_schema_status"] = "NOT_RUN"
            record["finished_at"] = datetime.now(UTC).isoformat()
            record = redact(record, secrets)
            write("cases/" + system + "--" + case["case_id"] + ".json", record)
            records.append(record)
    write("case_outputs.json", {"schema_version": "ai-v2-comparison-outputs-2", "records": records})
    reviews = {"schema_version": "ai-v2-comparison-claims-1", "case_outputs_sha256": files["case_outputs.json"],
               "reviews": [{"system_id": r["system_id"], "case_id": r["case_id"], **unit,
                            "support_status": "PENDING", "reviewer_ids": [], "reason": ""}
                           for r in records for unit in claim_units(r)]}
    write("claim_review_template.json", reviews)
    result = score_comparison(inputs, records, config, files["case_outputs.json"])
    write("metrics.json", result)
    with (output_dir / "report.md").open("x", encoding="utf-8") as stream:
        stream.write(markdown_report(result))
    files["report.md"] = digest((output_dir / "report.md").read_bytes())
    log_path = output_dir / "retrieval.jsonl"
    if log_path.exists():
        files["retrieval.jsonl"] = digest(log_path.read_bytes())
    diagnostic_case_ids = {c["case_id"] for c in rubric["cases"]
                           if c.get("category") == "no_lexical_evidence_probe"}
    required_records = [r for r in records if _required_comparison_row(r, diagnostic_case_ids)]
    summary = {**config, "finished_at": datetime.now(UTC).isoformat(), "artifact_sha256": files,
               "status": "PARTIAL_FAILURE" if any(r["status"] in {"ERROR", "NOT_RUN"} for r in required_records) else "COMPLETE",
               "status_counts": dict(Counter(r["status"] for r in records)),
               "required_status_counts": dict(Counter(r["status"] for r in required_records)),
               "required_output_count": len(required_records),
               "non_required_output_count": len(records) - len(required_records),
               "note": "Manual diagnostic-only rows may remain NOT_RUN and are not required for completion. No manual answers/support judgments fabricated. Missing final manifest means interrupted run."}
    write("run_manifest.json", summary)
    return result


def score_comparison(inputs, records, config, outputs_sha, annotations=None):
    cases = {c["case_id"]: c for c in inputs["rubric"]["cases"]}
    if any(config.get(key) != inputs[key] for key in ("corpus_sha256", "rubric_sha256")) or config.get("retrieval_k") != 5:
        raise ValueError("reference identity or k drift")
    if config.get("partition") != "DEVELOPMENT" or config.get("policy_version") != POLICY_VERSION:
        raise ValueError("unsupported comparison scope/policy")
    indexed = {}
    for r in records:
        key = (r["system_id"], r["case_id"])
        if (key in indexed or key[0] not in SYSTEMS or key[1] not in cases
                or r["status"] not in VALID | {"ERROR", "NOT_RUN"}
                or r["input_sha256"] != digest(cases[key[1]]["protocol_text"].encode())):
            raise ValueError("comparison output identity/status mismatch")
        indexed[key] = r
    if set(indexed) != {(s, c) for s in SYSTEMS for c in cases}:
        raise ValueError("every arm must retain every case, including failures")
    diagnostic_cases = {case_id: case for case_id, case in cases.items()
                        if case.get("category") == "no_lexical_evidence_probe"}
    protocol_cases = {case_id: case for case_id, case in cases.items() if case_id not in diagnostic_cases}
    if not protocol_cases:
        raise ValueError("comparison requires at least one protocol-extraction case")
    expected_claims = {(r["system_id"], r["case_id"], u["claim_id"]): u for r in records for u in claim_units(r)}
    decisions = {}
    if annotations is not None:
        if (annotations.get("schema_version") != "ai-v2-comparison-claims-1"
                or annotations.get("case_outputs_sha256") != outputs_sha or not isinstance(annotations.get("reviews"), list)):
            raise ValueError("claim annotations must bind the exact output bytes")
        for row in annotations["reviews"]:
            key = (row.get("system_id"), row.get("case_id"), row.get("claim_id"))
            if key not in expected_claims or key in decisions or any(row.get(k) != expected_claims[key][k] for k in ("text", "field_path")):
                raise ValueError("claim annotation identity/text mismatch")
            decision = row.get("support_status")
            if decision not in {"SUPPORTED", "UNSUPPORTED", "UNCERTAIN", "PENDING"}:
                raise ValueError("invalid human support decision")
            reviewers = row.get("reviewer_ids")
            if decision != "PENDING" and (not isinstance(reviewers, list) or not reviewers
                    or any(x not in inputs["rubric"]["reviewer_ids"] for x in reviewers)):
                raise ValueError("support decisions need named reference reviewers")
            decisions[key] = decision
    systems = []
    for system in SYSTEMS:
        selected = [indexed[system, c] for c in protocol_cases]
        counts = Counter(r["status"] for r in selected)
        all_case_counts = Counter(indexed[system, c]["status"] for c in cases)
        field_correct = field_total = present_correct = present_total = 0
        tp = fp = fn = 0
        raw_tp = raw_fp = raw_fn = raw_missing_cases = raw_declaration_valid = 0
        recall = []
        precision = []
        precision_relevant_hits = precision_returned_hits = 0
        raw_ok = raw_gold = raw_total = accepted_ok = accepted_total = 0
        for case_id, case in protocol_cases.items():
            r = indexed[system, case_id]
            valid = r["status"] in VALID
            for field in case["required_fields"]:
                field_total += 1
                correct = valid and r["fields"].get(field) == case["gold_fields"][field]
                field_correct += correct
                if case["gold_fields"][field] is not None:
                    present_total += 1
                    present_correct += correct
            expected = set(case["gold_missing_fields"])
            predicted = set(r["missing_fields"]) if valid else set()
            tp += len(expected & predicted)
            fp += len(predicted - expected)
            fn += len(expected - predicted)
            if system == "llm_rag":
                found = [x["chunk_id"] for x in r["retrieved_evidence"]]
                if len(found) > 5 or len(found) != len(set(found)):
                    raise ValueError("retrieval results must be unique top-5")
                gold = case["gold_evidence_chunk_ids"]
                if gold:
                    relevant = len(set(found) & set(gold))
                    recall.append(relevant / len(gold))
                    precision.append(_gold_set_precision_at_k(found, gold, k=5))
                    precision_relevant_hits += relevant
                    precision_returned_hits += len(found)
            raw = r.get("raw_output")
            # Runtime missing_fields is recomputed by the sanitizer. Measure the
            # model's own declaration separately, without credit for that repair.
            if r["provider_called"] is not False or (system == "manual_template" and valid):
                raw_missing_cases += 1
                declared = raw.get("missing_fields") if isinstance(raw, dict) else None
                well_formed = (isinstance(declared, list) and all(isinstance(x, str) for x in declared)
                               and len(set(declared)) == len(declared))
                raw_declaration_valid += well_formed
                declared_set = set(declared) if well_formed else set()
                raw_tp += len(expected & declared_set)
                raw_fp += len(declared_set - expected)
                raw_fn += len(expected - declared_set)
            cites = raw.get("citations", []) if isinstance(raw, dict) else []
            if cites is not None and not isinstance(cites, list):
                cites = [cites]  # Malformed citation is a wrong citation, not dropped.
            gold_pairs = {(x["source_id"], x["chunk_id"]) for x in case["gold_citations"]}
            for cite in cites or []:
                pair = citation_pair(cite)
                raw_total += 1
                raw_ok += pair in inputs["corpus_pairs"]
                raw_gold += pair in gold_pairs
            for cite in r["citations"]:
                pair = citation_pair(cite)
                accepted_total += 1
                accepted_ok += pair in inputs["corpus_pairs"]
        elapsed = sorted(r["elapsed_seconds"] for r in selected if r["elapsed_seconds"] is not None and r["status"] != "NOT_RUN")
        claims = [key for key in expected_claims if key[0] == system and key[1] in protocol_cases]
        support = Counter(decisions.get(key, "PENDING") for key in claims)
        determinate = support["SUPPORTED"] + support["UNSUPPORTED"]
        schemas = _schema_metrics(selected, denominator=len(protocol_cases), system_id=system)
        systems.append({"system_id": system, "case_count": len(protocol_cases),
                        "artifact_case_count": len(cases), "status_counts": dict(counts),
                        "artifact_status_counts": dict(all_case_counts),
                        "measurement_status": "NOT_MEASURED" if counts["NOT_RUN"] == len(protocol_cases) else "MEASURED_WITH_FAILURES" if counts["ERROR"] or counts["NOT_RUN"] else "MEASURED",
                        "completion_rate": counts["COMPLETED"] / len(protocol_cases),
                        "error_rate": counts["ERROR"] / len(protocol_cases), "not_run_rate": counts["NOT_RUN"] / len(protocol_cases),
                        "runtime_success_rate": (counts["COMPLETED"] + counts["ABSTAINED"]) / len(protocol_cases),
                        "fully_specified_protocol_count": sum(r["status"] == "COMPLETED" and not r["missing_fields"] for r in selected),
                        "field_exact": {"correct": field_correct, "denominator": field_total, "accuracy": field_correct / field_total if counts["NOT_RUN"] != len(protocol_cases) else None,
                                        "non_null_correct": present_correct, "non_null_denominator": present_total,
                                        "non_null_accuracy": present_correct / present_total if present_total and counts["NOT_RUN"] != len(protocol_cases) else None},
                        "missing_fields": {"tp": tp, "fp": fp, "fn": fn,
                                           "precision": tp / (tp + fp) if tp + fp and counts["NOT_RUN"] != len(protocol_cases) else None,
                                           "recall": tp / (tp + fn) if tp + fn and counts["NOT_RUN"] != len(protocol_cases) else None,
                                           "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn and counts["NOT_RUN"] != len(protocol_cases) else None},
                        "raw_missing_declaration": {"attempted_cases": raw_missing_cases,
                                                    "well_formed_declaration_cases": raw_declaration_valid,
                                                    "tp": raw_tp, "fp": raw_fp, "fn": raw_fn,
                                                    "f1": 2 * raw_tp / (2 * raw_tp + raw_fp + raw_fn) if 2 * raw_tp + raw_fp + raw_fn else None},
                        "retrieval": {"applicable": system == "llm_rag", "relevance_basis": "gold-set chunk IDs only; non-gold chunks are unjudged",
                                      "assessable_cases": len(recall), "recall_at_5": statistics.mean(recall) if recall else None,
                                      "precision_at_5": statistics.mean(precision) if precision else None,
                                      "precision_case_denominator": len(precision),
                                      "precision_returned_hit_denominator_sum": precision_returned_hits,
                                      "precision_relevant_hit_numerator_sum": precision_relevant_hits,
                                      "precision_formula": "macro mean over assessable protocol cases of |returned_top5 ∩ gold_ids| / |returned_top5|; use actual unique returned-hit count, no padding to k",
                                      "precision_empty_gold_rule": "exclude from Precision@5 and Recall@5 (N/A); diagnostic case reported separately",
                                      "precision_zero_hit_rule": "score 0 only when gold set is non-empty",
                                      "empty_gold_cases": sum(not case["gold_evidence_chunk_ids"] for case in protocol_cases.values()),
                                      "non_retrieval_value": None},
                        "schema_validity": schemas,
                        "citations": {"raw_count": raw_total, "raw_existing_source_count": raw_ok,
                                      "raw_source_precision": raw_ok / raw_total if raw_total else None,
                                      "raw_gold_match_count": raw_gold, "raw_gold_precision": raw_gold / raw_total if raw_total else None,
                                      "accepted_count": accepted_total, "accepted_source_precision": accepted_ok / accepted_total if accepted_total else None},
                        "claim_review": {"claim_count": len(claims), "status_counts": dict(support),
                                         "determinate_denominator": determinate,
                                         "review_coverage": (len(claims) - support["PENDING"]) / len(claims) if claims else None,
                                         "unsupported_claim_rate": support["UNSUPPORTED"] / determinate if determinate else None,
                                         "status": "PENDING_HUMAN_REVIEW" if support["PENDING"] else "NO_CLAIMS" if not claims else "ANNOTATED"},
                        "latency": {"denominator": len(elapsed), "mean_seconds": statistics.mean(elapsed) if elapsed else None,
                                    "median_seconds": statistics.median(elapsed) if elapsed else None,
                                    "p95_seconds": elapsed[math.ceil(.95 * len(elapsed)) - 1] if elapsed else None,
                                    "source": "human_self_reported" if system == "manual_template" else "in_process_retrieval_plus_generation"}})
    diagnostics = [{"case_id": case_id, "category": case.get("category"), "diagnostic_type": "LEXICAL_NO_HIT_PROBE",
                    "systems": [{"system_id": system, "status": indexed[system, case_id]["status"],
                                 "provider_attempted": indexed[system, case_id].get("provider_attempted"),
                                 "provider_called": indexed[system, case_id].get("provider_called"),
                                 "retrieved_hit_count": len(indexed[system, case_id].get("retrieved_evidence", [])),
                                 "abstained_without_evidence": (indexed[system, case_id]["status"] == "ABSTAINED"
                                                                and not indexed[system, case_id].get("retrieved_evidence")),
                                 "raw_schema_status": indexed[system, case_id].get("raw_schema_status", "NOT_RECORDED"),
                                 "processed_schema_status": indexed[system, case_id].get("processed_schema_status", "NOT_RECORDED")}
                                for system in SYSTEMS]} for case_id, case in diagnostic_cases.items()]
    required_records = [r for r in records if _required_comparison_row(r, set(diagnostic_cases))]
    return {"schema_version": "ai-v2-comparison-metrics-2", "partition": "DEVELOPMENT", "policy_version": POLICY_VERSION,
            "status": "SOFTWARE_TEST_STUB_RESULTS" if config["test_only"] else
            "MEASURED_OWNER_REVIEWED_SYNTHETIC_DEMO_NOT_INDEPENDENT" if config["synthetic_fixture"] else
            "MEASURED_INTERNAL_DEVELOPMENT_NOT_INDEPENDENT",
            "comparison_complete": all(r["status"] in VALID for r in required_records),
            "case_outputs_sha256": outputs_sha, "corpus_sha256": inputs["corpus_sha256"],
            "rubric_sha256": inputs["rubric_sha256"], "retrieval_k": 5,
            "configured_model_id": config["configured_model_id"], "prompt_version": config["prompt_version"],
            "independent_review_claim": False, "heldout_status": "LOCKED_NOT_RUN",
            "case_count": len(protocol_cases), "artifact_case_count": len(cases),
            "protocol_extraction_case_ids": list(protocol_cases),
            "diagnostic_case_count": len(diagnostic_cases), "lexical_no_hit_diagnostics": diagnostics,
            "systems": systems,
            "limitations": ["Configured model identity, not independently observed backend revision.",
                            "Same prompt/provider; evidence, RAG no-hit gate and citation guardrails differ. Not a pure retrieval-only causal ablation.",
                            "Exact match is not semantic accuracy. Null golds also scored; non-null accuracy reported separately.",
                            "Citation existence/gold match is not support. Unsupported claims require bound human annotations.",
                            "Workflow missing_fields is sanitizer-computed; raw model missing declarations reported separately on generation attempts (no-hit skips excluded).",
                            "Manual time is self-reported; model time excludes startup, installation and artifact writes.",
                            "Failures stay in the 11-case protocol denominator; case-012 lexical probe is reported separately.",
                            "Precision@5 uses gold-set chunk IDs as relevance judgments; non-gold chunks are unjudged.",
                            "No biological or wet-lab validation claim."]}


def markdown_report(result):
    def val(x):
        return "N/A" if x is None else f"{x:.3f}"
    lines = ["# Development comparator report", "", "Status: `" + result["status"] + "`",
             "", f"Protocol extraction cases: {result['case_count']}; diagnostic cases: {result['diagnostic_case_count']}; all artifacts retained: {result['artifact_case_count']}.",
             "", "All required comparison outputs complete (manual baseline required only for 11 protocol cases): " + str(result["comparison_complete"]),
             "", "## Protocol extraction aggregate (diagnostic case excluded)",
             "", "| System | Complete | Abstained | Error | Not run | Runtime success | Recall@5 | Gold-set Precision@5 | Field exact | Missing F1 | Raw schema valid / responses | Processed schema valid / produced | Mean seconds |",
             "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for s in result["systems"]:
        schema = s["schema_validity"]
        cells = [s["system_id"], val(s["completion_rate"]), str(s["status_counts"].get("ABSTAINED", 0)),
                 val(s["error_rate"]), val(s["not_run_rate"]), val(s["runtime_success_rate"]),
                 val(s["retrieval"]["recall_at_5"]), val(s["retrieval"]["precision_at_5"]),
                 val(s["field_exact"]["accuracy"]), val(s["missing_fields"]["f1"]),
                 val(schema["raw_output_schema"]["valid_rate_among_responses"]),
                 val(schema["processed_draft_schema"]["valid_rate_among_produced"]), val(s["latency"]["mean_seconds"])]
        lines.append("| " + " | ".join(cells) + " |")
    lines += ["", "Raw schema denominator = observed JSON responses (manual worksheet or model response); its case-rate denominator is all 11 protocol cases. Processed schema denominator = produced Workbench drafts; its case-rate denominator is all 11 cases. Error/no-response, abstention, not-run, and provider-not-called counts remain explicit in the status counts; see metrics.json.",
              "", "Gold-set Precision@5 = relevant returned gold IDs / actual unique hits returned (up to 5), macro-averaged only over cases with nonempty gold IDs. Fewer than five hits use the actual hit count; zero hits score 0 only for a nonempty gold set. Empty gold and non-retrieval arms are N/A. This is gold-set relevance; non-gold chunks are unjudged.",
              "", "## Lexical no-hit diagnostic (not part of extraction aggregate)", ""]
    for diagnostic in result["lexical_no_hit_diagnostics"]:
        lines += [f"Case `{diagnostic['case_id']}` — `{diagnostic['diagnostic_type']}`", "",
                  "| System | Status | Provider attempted | Provider called | Retrieved hits | Abstained without evidence | Raw schema | Processed schema |",
                  "| --- | --- | --- | --- | --- | --- | --- | --- |"]
        for row in diagnostic["systems"]:
            lines.append("| " + " | ".join([row["system_id"], row["status"], str(row["provider_attempted"]),
                                                 str(row["provider_called"]), str(row["retrieved_hit_count"]),
                                                 str(row["abstained_without_evidence"]), row["raw_schema_status"],
                                                 row["processed_schema_status"]]) + " |")
        lines.append("")
    lines += ["N/A is not zero; errors, not-run and abstention remain visible. Support metrics may be pending human review. See metrics.json for denominators and status counts.", ""]
    lines += ["- " + text for text in result["limitations"]]
    return "\n".join(lines) + "\n\nHELDOUT_STATUS = LOCKED_NOT_RUN\n"


def verify_run(run_dir: Path, inputs: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
    root = safe_path(run_dir)
    manifest = read_json(root / "run_manifest.json")
    if manifest.get("schema_version") != "ai-v2-comparison-run-2" or not isinstance(manifest.get("artifact_sha256"), dict):
        raise ValueError("missing final comparison manifest")
    for name, expected in manifest["artifact_sha256"].items():
        path = safe_path(root / name)
        if not path.is_relative_to(root) or digest(path.read_bytes()) != expected:
            raise ValueError("comparison artifact integrity failed")
    for name in ("run_config.json", "case_outputs.json"):
        if name not in manifest["artifact_sha256"]:
            raise ValueError("required comparison artifact is not hashed")
    config = read_json(root / "run_config.json")
    if any(config.get(k) != manifest.get(k) for k in config):
        raise ValueError("run configuration differs from final manifest")
    if any(config.get(k) != inputs[k] for k in ("corpus_sha256", "rubric_sha256")):
        raise ValueError("frozen reference changed after generation")
    records = read_json(root / "case_outputs.json")["records"]
    return config, records, manifest["artifact_sha256"]["case_outputs.json"]
