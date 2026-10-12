"""Prepare a reviewable synthetic comparison package; freeze only recorded decisions.

Preparation and freezing are local operations. Provider execution stays in
compare_ai_v2_protocols.py and requires its explicit flag and local credential.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from audit_ai_v2_draft_eval_inputs import audit_inputs
from create_rag_manifest import build_manifest
from drosophila_pd.ai_v2.comparison import (
    POLICY_VERSION, PROMPT_VERSION, digest, encoded, load_manual, manual_template,
    prepare_inputs, read_json, safe_path,
)
from drosophila_pd.workbench import intake
from drosophila_pd.workbench.rag import FrozenEvidenceCorpus

MODEL = "gemini-3.1-flash-lite"
BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"
ENDPOINT = BASE_URL + "/chat/completions"
REVIEWER = "owner-le-tan-vi"
DECISION_FIELDS = {
    "schema_version", "status", "review_package_sha256", "corpus_sha256",
    "rubric_sha256", "reviewer_id", "confirmed_at", "owner_statement",
    "corpus_approved", "rubric_approved", "case003_context_accepted",
    "case012_diagnostic_only_accepted", "model_id", "provider_id",
    "provider_endpoint", "api_service_tier", "corpus_text_sharing_approved",
    "protocol_text_sharing_approved", "independent_review_claim",
}
CODE_FILES = (
    "scripts/prepare_ai_v2_owner_demo.py", "scripts/create_rag_manifest.py",
    "scripts/audit_ai_v2_draft_eval_inputs.py", "scripts/compare_ai_v2_protocols.py",
    "src/drosophila_pd/ai_v2/comparison.py", "src/drosophila_pd/ai_v2/collection.py",
    "src/drosophila_pd/workbench/intake.py", "src/drosophila_pd/workbench/rag.py",
)


def code_hashes() -> dict[str, str]:
    return {name: digest((ROOT / name).read_bytes()) for name in CODE_FILES}


def write_new(path: Path, content: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(content)


def inventory(folder: Path, names: list[str]) -> dict[str, str]:
    return {name: digest((folder / name).read_bytes()) for name in names}


def verify_inventory(folder: Path, filename: str) -> dict:
    data = read_json(folder / filename)
    files = data.get("artifact_sha256")
    if not isinstance(files, dict) or not files:
        raise ValueError("package inventory is missing")
    for name, expected in files.items():
        path = safe_path(folder / name)
        if not path.is_relative_to(folder.resolve()) or not path.is_file():
            raise ValueError("inventory contains an unavailable package file")
        if digest(path.read_bytes()) != expected:
            raise ValueError("package bytes changed since preparation/freeze")
    if data.get("implementation_sha256") != code_hashes():
        raise ValueError("implementation changed; prepare a new review version")
    return data


class PreviewCorpus(FrozenEvidenceCorpus):
    """Use runtime lexical scoring in memory, without an approved manifest."""

    def _append_log(self, event: dict) -> None:
        pass  # Preview records below are separate from runtime audit logs.


class PreviewResponse:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, _):
        return b'{"choices":[{"message":{"content":"{}"}}]}'


def request_previews(inputs: dict, corpus_path: Path) -> list[dict]:
    chunks = tuple(json.loads(line) for line in corpus_path.read_text("utf-8").splitlines())
    corpus = PreviewCorpus(
        corpus_id="pending-local-preview", corpus_sha256=inputs["corpus_sha256"],
        manifest_sha256="", chunks=chunks,
        approved_source_ids=frozenset(x["source_id"] for x in chunks),
        denied_source_ids=frozenset(), provider_sharing_approved=False,
        protocol_text_sharing_approved=False, approved_provider_id="",
        approved_provider_endpoint="", retrieval_log_path=Path("unused-preview-log"),
    )
    provider = intake.OpenAICompatibleIntakeProvider(BASE_URL, MODEL, api_key_env=None)
    previews = []
    for case in inputs["rubric"]["cases"]:
        hits = [hit.as_dict() for hit in corpus.retrieve(case["protocol_text"], k=5)]
        for arm in ("llm_no_retrieval", "llm_rag"):
            evidence = [{k: hit[k] for k in ("source_id", "citation", "chunk_id", "text")}
                        for hit in hits] if arm == "llm_rag" else []
            preview = {"case_id": case["case_id"], "system_id": arm,
                       "status": "PREVIEW_NOT_SENT", "provider_called": False,
                       "would_call_if_authorized": arm != "llm_rag" or bool(hits),
                       "retrieved_chunk_ids": [hit["chunk_id"] for hit in hits] if arm == "llm_rag" else []}
            if preview["would_call_if_authorized"]:
                captured = {}

                def capture(request, *, timeout):
                    captured.update(endpoint=request.full_url, timeout_s=timeout,
                                    body=json.loads(request.data.decode("utf-8")))
                    return PreviewResponse()

                # Capture the actual adapter request before transport. No key is read.
                with patch.object(intake, "urlopen", side_effect=capture):
                    provider.extract_with_evidence(case["protocol_text"], evidence=evidence)
                preview.update(captured)
            else:
                preview["local_behavior"] = "ABSTAINED_NO_EVIDENCE"
            previews.append(preview)
    return previews


def worksheet_markdown(worksheet: dict) -> str:
    lines = ["# Worksheet baseline của owner — chưa điền", "",
             "Owner đã xem reference; baseline tương lai là nội bộ, không mù. Không có gold trong worksheet này.",
             "11 case trích xuất cần câu trả lời. Case 012 chỉ là diagnostic, không cần manual answer.",
             "Điền fields từ protocol, missing_fields từ 4 trường lõi; citations chỉ dùng nguồn thực sự biết.",
             "Giữ PENDING cho case chưa trả lời. Thời gian là thời gian owner tự đo, không tự ước lượng.", ""]
    for case in worksheet["cases"]:
        lines.extend([f"## {case['case_id']}", "", "```text", case["protocol_text"], "```", "",
                      "```json", json.dumps({k: case[k] for k in
                      ("status", "fields", "missing_fields", "citations", "reviewer_ids", "elapsed_seconds")},
                      ensure_ascii=False, indent=2), "```", ""])
    return "\n".join(lines)


def prepare_review(corpus_path: Path, rubric_path: Path, plan_path: Path, target: Path) -> dict:
    corpus_path, rubric_path, plan_path, target = map(safe_path, (corpus_path, rubric_path, plan_path, target))
    audit = audit_inputs(corpus_path, rubric_path)
    inputs = prepare_inputs(corpus_path, rubric_path)
    if (inputs["rubric"].get("synthetic_fixture") is not True
            or len(inputs["rubric"]["cases"]) != 12):
        raise ValueError("this preparation supports the 12-case synthetic internal demo only")
    cases = inputs["rubric"]["cases"]
    if ([case["case_id"] for case in cases] != [f"AI_PROTO_DEV_DRAFT_{i:03d}" for i in range(1, 13)]
            or cases[2]["gold_fields"].get("context") != {"sex": "female"}
            or cases[11].get("category") != "no_lexical_evidence_probe"
            or any(case.get("category") == "no_lexical_evidence_probe" for case in cases[:11])):
        raise ValueError("prepare requires the case-003 context proposal and separate case-012 diagnostic")
    if any(target.is_relative_to(Path(root)) for root in inputs["protected_input_roots"]):
        raise ValueError("review package must be separate from source inputs")
    source_path = rubric_path.parent / inputs["rubric"]["source_document_file"]
    previews = request_previews(inputs, corpus_path)
    policy = {
        "status": "PROPOSED_NOT_FROZEN", "evaluation_mode": "OWNER_REVIEWED_DEMO",
        "synthetic_fixture": True, "independent_review_claim": False,
        "policy_version": POLICY_VERSION, "prompt_version": PROMPT_VERSION,
        "retrieval_k": 5, "protocol_case_count": 11, "diagnostic_case_count": 1,
        "run_count_per_arm": 1, "temperature": 0, "response_format": intake.provider_response_format(),
        "timeout_s": 60, "automatic_retries": 0, "model_fallback": False,
        "model_id_proposal": MODEL, "provider_id_proposal": "openai-compatible:" + MODEL,
        "provider_endpoint_proposal": ENDPOINT,
        "manual_baseline_policy": "KEEP_PENDING_REPORT_NOT_MEASURED",
        "manual_baseline_note": "Owner has seen references; no manual answer or elapsed time supplied.",
        "max_provider_requests": sum(row["would_call_if_authorized"] for row in previews),
        "gold_or_review_sent": False, "provider_called": False,
        "claim_support_policy": "Human review of exact output bytes; pending/N/A until reviewed.",
        "heldout_status": "LOCKED_NOT_RUN",
    }
    worksheet = manual_template(inputs)
    worksheet["note"] = policy["manual_baseline_note"] + " PENDING is not a completed manual baseline."
    names = [corpus_path.name, rubric_path.name, source_path.name, "measurement_plan.md",
             "structural_audit.json", "comparison_policy_proposal.json", "request_previews.json",
             "manual_template_pending.json", "manual_worksheet.md"]
    target.mkdir(parents=True, exist_ok=False)
    for name, data in ((corpus_path.name, corpus_path.read_bytes()), (rubric_path.name, rubric_path.read_bytes()),
                       (source_path.name, source_path.read_bytes()), ("measurement_plan.md", plan_path.read_bytes()),
                       ("structural_audit.json", encoded(audit)), ("comparison_policy_proposal.json", encoded(policy)),
                       ("request_previews.json", encoded(previews)), ("manual_template_pending.json", encoded(worksheet)),
                       ("manual_worksheet.md", worksheet_markdown(worksheet).encode("utf-8"))):
        write_new(target / name, data)
    inv = {"schema_version": "ai-v2-owner-review-package-1", "status": "PENDING_OWNER_DECISION",
           "prepared_at": datetime.now().astimezone().isoformat(),
           "corpus_file": corpus_path.name, "rubric_file": rubric_path.name,
           "corpus_sha256": inputs["corpus_sha256"], "rubric_sha256": inputs["rubric_sha256"],
           "implementation_sha256": code_hashes(), "artifact_sha256": inventory(target, names)}
    inv_bytes = encoded(inv)
    write_new(target / "review_inventory.json", inv_bytes)
    decision = {"schema_version": "ai-v2-owner-demo-decision-1", "status": "PENDING_OWNER_DECISION",
                "review_package_sha256": digest(inv_bytes), "corpus_sha256": inputs["corpus_sha256"],
                "rubric_sha256": inputs["rubric_sha256"], "reviewer_id": REVIEWER,
                "confirmed_at": None, "owner_statement": "", "corpus_approved": False,
                "rubric_approved": False, "case003_context_accepted": False,
                "case012_diagnostic_only_accepted": False, "model_id": "", "provider_id": "",
                "provider_endpoint": "", "api_service_tier": "UNKNOWN",
                "corpus_text_sharing_approved": False, "protocol_text_sharing_approved": False,
                "independent_review_claim": False}
    write_new(target / "owner_decision_pending.json", encoded(decision))
    summary = {"status": "REVIEW_READY_PENDING_OWNER_AND_CREDENTIAL", **audit,
               "review_package_sha256": digest(inv_bytes), "rubric_sha256": inputs["rubric_sha256"],
               "manual_completed": 0, "manual_pending": 12, "provider_called": False,
               "freeze_created": False, "heldout_status": "LOCKED_NOT_RUN"}
    summary["status"] = "REVIEW_READY_PENDING_OWNER_AND_CREDENTIAL"
    write_new(target / "readiness.json", encoded(summary))
    write_new(target / "README.md", (
        "# Package sẵn để owner chốt\n\n"
        "Trạng thái: PENDING_OWNER_DECISION. Phạm vi: OWNER_REVIEWED_DEMO, synthetic, một owner, AI-assisted, không độc lập.\n\n"
        f"Corpus SHA-256: `{inputs['corpus_sha256']}`\n\nRubric proposal SHA-256: `{inputs['rubric_sha256']}`\n\n"
        f"Review inventory SHA-256: `{digest(inv_bytes)}`\n\n"
        "Case 003: giữ context.sex=female, bỏ feeding_state không xác định. Không thêm feeding_state vào missing_fields vì runtime chỉ dùng 4 trường lõi.\n\n"
        "Case 012: lexical no-hit diagnostic riêng; không vào aggregate 11 case.\n\n"
        "Baseline: 12 dòng PENDING, 0 câu trả lời của owner. Khi chạy với bản này manual_template là NOT_MEASURED và comparison_complete=false.\n\n"
        f"Model đề xuất: `{MODEL}`. Provider ID: `openai-compatible:{MODEL}`. Endpoint: `{ENDPOINT}`.\n\n"
        "Xem measurement_plan.md, comparison_policy_proposal.json và request_previews.json trước khi chốt. Preview bắt request của adapter tại máy; chưa gửi mạng, chưa dùng API key.\n\n"
        "Mẫu owner_decision_pending.json chỉ ghi người dự kiến; tất cả approval=false. Khi owner xác nhận, ghi nguyên văn xác nhận và thời điểm có timezone vào một file quyết định version mới. Utility freeze kiểm tra hash và quyết định trước khi tạo snapshot/manifest.\n\n"
        "Gemini API tier phải là PAID hoặc UNPAID theo project thực tế; không suy ra từ Gemini Pro. Dữ liệu ra máy gồm protocol synthetic, system prompt và tối đa 5 chunk, không gồm gold/rubric/review.\n\n"
        "Nguồn Google đã đối chiếu: [model](https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-lite), "
        "[compatibility](https://ai.google.dev/gemini-api/docs/openai), [terms](https://ai.google.dev/gemini-api/terms), "
        "[pricing](https://ai.google.dev/gemini-api/docs/pricing). Free tier có thể dùng input/output để cải thiện dịch vụ; "
        "Paid không dùng cho việc đó nhưng có lưu log giới hạn cho an toàn/pháp lý. Tier/quota của owner chưa xác minh.\n\n"
        "Không có freeze/provider run/AI-quality result trong package này. HELDOUT_STATUS = LOCKED_NOT_RUN.\n"
    ).encode("utf-8"))
    return summary


def freeze_review(review_dir: Path, decision_path: Path, target: Path) -> dict:
    review_dir, decision_path, target = map(safe_path, (review_dir, decision_path, target))
    inv = verify_inventory(review_dir, "review_inventory.json")
    d = read_json(decision_path)
    if not isinstance(d, dict) or set(d) != DECISION_FIELDS:
        raise ValueError("owner decision has missing or unsupported fields")
    if (d["schema_version"] != "ai-v2-owner-demo-decision-1" or d["status"] != "OWNER_CONFIRMED"
            or d["reviewer_id"] != REVIEWER or d["independent_review_claim"] is not False
            or not isinstance(d["owner_statement"], str) or not d["owner_statement"].strip()):
        raise ValueError("an actual single-owner confirmation is required")
    confirmed = datetime.fromisoformat(d["confirmed_at"]) if isinstance(d["confirmed_at"], str) else None
    if confirmed is None or confirmed.utcoffset() is None:
        raise ValueError("owner confirmation needs a timezone-aware timestamp")
    if (d["review_package_sha256"] != digest((review_dir / "review_inventory.json").read_bytes())
            or any(d[k] != inv[k] for k in ("corpus_sha256", "rubric_sha256"))):
        raise ValueError("decision does not identify this exact review package")
    for key in ("corpus_approved", "rubric_approved", "case003_context_accepted",
                "case012_diagnostic_only_accepted", "corpus_text_sharing_approved",
                "protocol_text_sharing_approved"):
        if d[key] is not True:
            raise ValueError("required package/provider decision remains unconfirmed: " + key)
    if (d["model_id"] != MODEL or d["provider_id"] != "openai-compatible:" + MODEL
            or d["provider_endpoint"] != ENDPOINT or d["api_service_tier"] not in {"PAID", "UNPAID"}):
        raise ValueError("provider or service tier differs from the reviewed proposal")
    if target.is_relative_to(review_dir) or target.is_relative_to(decision_path.parent):
        raise ValueError("freeze must use a separate new directory")
    corpus = review_dir / inv["corpus_file"]
    draft = review_dir / inv["rubric_file"]
    audit_inputs(corpus, draft)
    reviewed = copy.deepcopy(read_json(draft))
    reviewed.update(schema_version="ai-v2-assistant-reference-reviewed-1", status="APPROVED",
                    reviewer_ids=[REVIEWER], evaluation_mode="OWNER_REVIEWED_DEMO", owner_demo=True,
                    independent_review_claim=False, reviewed_at=d["confirmed_at"])
    reviewed["privacy_decision"] = {"status": "APPROVED", "corpus_text_sharing_approved": True,
                                   "protocol_text_sharing_approved": True,
                                   "provider_id": d["provider_id"], "provider_endpoint": d["provider_endpoint"]}
    target.mkdir(parents=True, exist_ok=False)
    write_new(target / corpus.name, corpus.read_bytes())
    source_name = reviewed["source_document_file"]
    write_new(target / source_name, (review_dir / source_name).read_bytes())
    write_new(target / "reference_owner_reviewed.json", encoded(reviewed))
    write_new(target / "owner_decision.json", decision_path.read_bytes())
    write_new(target / "measurement_plan.md", (review_dir / "measurement_plan.md").read_bytes())
    policy = read_json(review_dir / "comparison_policy_proposal.json")
    policy["status"] = "FROZEN_OWNER_REVIEWED_DEMO"
    write_new(target / "comparison_policy.json", encoded(policy))
    manifest_path = target / "corpus.manifest.json"
    args = argparse.Namespace(corpus=target / corpus.name, manifest=manifest_path,
                              corpus_id="owner-reviewed-synthetic-protocol-development-v1",
                              approved_source_id=["SYNTHETIC_PROTOCOL_GUIDE_V1"], denied_source_id=[],
                              reviewed_by=[REVIEWER], owner_approved=True, outcome_free=True,
                              provider_sharing_approved=True, protocol_text_sharing_approved=True,
                              approved_provider_id=d["provider_id"], approved_provider_endpoint=d["provider_endpoint"])
    _, manifest_report = build_manifest(args)
    inputs = prepare_inputs(target / corpus.name, target / "reference_owner_reviewed.json", manifest_path, generation=True)
    worksheet = read_json(review_dir / "manual_template_pending.json")
    if any(row["status"] != "PENDING" or row["fields"] or row["reviewer_ids"] for row in worksheet["cases"]):
        raise ValueError("this freeze path preserves the blank manual baseline only")
    worksheet["rubric_sha256"] = inputs["rubric_sha256"]
    write_new(target / "manual_template_pending.json", encoded(worksheet))
    load_manual(target / "manual_template_pending.json", inputs)
    files = [p.name for p in target.iterdir() if p.is_file()]
    frozen = {"schema_version": "ai-v2-owner-demo-freeze-1", "status": "FROZEN_OWNER_REVIEWED_DEMO",
              "review_package_sha256": d["review_package_sha256"], "reviewer_ids": [REVIEWER],
              "review_method": "AI-assisted; actual owner decision recorded separately",
              "independent_review_claim": False, "synthetic_fixture": True,
              "implementation_sha256": code_hashes(), "artifact_sha256": inventory(target, files),
              "provider_called": False, "heldout_status": "LOCKED_NOT_RUN"}
    write_new(target / "freeze_inventory.json", encoded(frozen))
    verify_inventory(target, "freeze_inventory.json")
    return {"status": frozen["status"], **manifest_report, "rubric_sha256": inputs["rubric_sha256"],
            "manual_baseline_status": "NOT_MEASURED", "provider_called": False, "heldout_status": "LOCKED_NOT_RUN"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--prepare", action="store_true")
    modes.add_argument("--freeze", action="store_true")
    modes.add_argument("--check-frozen", action="store_true")
    parser.add_argument("--corpus", type=Path)
    parser.add_argument("--rubric", type=Path)
    parser.add_argument("--measurement-plan", type=Path)
    parser.add_argument("--review-package", type=Path)
    parser.add_argument("--decision", type=Path)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    try:
        if args.prepare:
            if any(x is None for x in (args.corpus, args.rubric, args.measurement_plan, args.output_dir)):
                raise ValueError("prepare needs corpus, rubric, plan and new output directory")
            result = prepare_review(args.corpus, args.rubric, args.measurement_plan, args.output_dir)
        elif args.freeze:
            if any(x is None for x in (args.review_package, args.decision, args.output_dir)):
                raise ValueError("freeze needs exact review package, decision and new output directory")
            result = freeze_review(args.review_package, args.decision, args.output_dir)
        else:
            if args.review_package is None:
                raise ValueError("check-frozen needs frozen package path")
            checked = verify_inventory(safe_path(args.review_package), "freeze_inventory.json")
            result = {"status": "FROZEN_INTEGRITY_PASS", "provider_called": False,
                      "artifact_count": len(checked["artifact_sha256"]), "heldout_status": "LOCKED_NOT_RUN"}
        print(encoded(result).decode("utf-8"))
        return 0
    except (ValueError, TypeError, OSError, KeyError):
        print(encoded({"status": "BLOCKED", "message": "Check exact package hashes, recorded owner decisions, provider/tier and fresh paths.",
                       "provider_called": False, "heldout_status": "LOCKED_NOT_RUN"}).decode("utf-8"))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
