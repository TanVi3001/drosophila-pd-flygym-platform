"""Verify the narrow missing-placeholder fix and replay saved development outputs offline."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from drosophila_pd.ai_v2 import comparison  # noqa: E402
from drosophila_pd.workbench import intake  # noqa: E402


DEFAULT_RUN = Path(".workbench/ai-v2-comparisons/paired-20261009T131833878Z")
DEFAULT_STEP2 = Path(".workbench/ai-v2-audits/step2-field-claims-review-20261009-v10")
DEFAULT_PACKAGE = Path(".workbench/evidence/owner_demo_protocol_frozen_v2")
DEFAULT_AUDIT = Path(".workbench/ai-v2-audits/offline-replay-postprocessing-20261009-v2")
LABEL = "OFFLINE_REPLAY_POSTPROCESSING_DIAGNOSTIC"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_exclusive(path: Path, payload: Any) -> None:
    data = comparison.encoded(payload)
    with path.open("xb") as stream:
        stream.write(data)


def write_text_exclusive(path: Path, text: str) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(text)


def test_command(command: list[str], cwd: Path) -> tuple[int, str]:
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, encoding="utf-8")
    rendered = "$ " + subprocess.list2cmdline(command) + "\n"
    rendered += f"exit_code={result.returncode}\n"
    rendered += result.stdout
    if result.stderr:
        rendered += "\n[stderr]\n" + result.stderr
    if not rendered.endswith("\n"):
        rendered += "\n"
    return result.returncode, rendered


class LocalReplayProvider:
    """Return only a previously saved parsed object; has no network implementation."""

    def __init__(self, raw: dict[str, Any], config: dict[str, Any]) -> None:
        self._raw = copy.deepcopy(raw)
        self.provider_id = config["provider_id"]
        self.model = config["configured_model_id"]
        self.endpoint = config["provider_endpoint"]
        self.invocations = 0

    def extract(self, _protocol_text: str, *, source_uri: str | None = None) -> dict[str, Any]:
        self.invocations += 1
        return copy.deepcopy(self._raw)

    def extract_with_evidence(
        self, _protocol_text: str, *, evidence: list[dict[str, Any]],
    ) -> dict[str, Any]:
        self.invocations += 1
        return copy.deepcopy(self._raw)


class SavedEvidenceCorpus:
    """Expose exactly the run's saved retrieval hits to the local RAG postprocessor."""

    def __init__(self, manifest: dict[str, Any], manifest_sha256: str,
                 corpus_sha256: str, evidence: list[dict[str, Any]]) -> None:
        self.corpus_id = manifest["corpus_id"]
        self.corpus_sha256 = corpus_sha256
        self.manifest_sha256 = manifest_sha256
        self.provider_sharing_approved = manifest["provider_sharing_approved"]
        self.protocol_text_sharing_approved = manifest["protocol_text_sharing_approved"]
        self.approved_provider_id = manifest["approved_provider_id"]
        self.approved_provider_endpoint = manifest["approved_provider_endpoint"]
        self._hits = [
            SimpleNamespace(
                evidence=SimpleNamespace(
                    source_id=item["source_id"], citation=item["citation"],
                    chunk_id=item["chunk_id"], retrieval_score=item["retrieval_score"],
                    provenance=item["provenance"], access_class=item["access_class"],
                ),
                text=item["text"],
            )
            for item in evidence
        ]

    def retrieve(self, _query: str, *, k: int) -> list[Any]:
        if k != 5 or len(self._hits) > k:
            raise ValueError("saved replay evidence does not match the frozen top-5 policy")
        return self._hits


def _map_metrics(metrics: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["system_id"]: item for item in metrics["systems"]}


def _trace_rows(records: list[dict[str, Any]], replayed: list[dict[str, Any]]) -> list[dict[str, Any]]:
    replay_index = {(row["system_id"], row["case_id"]): row for row in replayed}
    traces = []
    for original in records:
        key = (original["system_id"], original["case_id"])
        replay = replay_index[key]
        raw = original.get("raw_output")
        declared = raw.get("missing_fields") if isinstance(raw, dict) else None
        traces.append({
            "system_id": key[0], "case_id": key[1],
            "model_declared_missing_fields": copy.deepcopy(declared),
            "original_runtime_missing_fields": copy.deepcopy(original.get("missing_fields")),
            "replay_runtime_missing_fields": copy.deepcopy(replay.get("missing_fields")),
            "raw_parsed_output_sha256_before": sha256(comparison.encoded(raw)) if raw is not None else None,
            "raw_parsed_output_sha256_after": sha256(comparison.encoded(replay.get("raw_output")))
            if replay.get("raw_output") is not None else None,
        })
    return traces


def _build_case_report(original: list[dict[str, Any]], replayed: list[dict[str, Any]],
                       step2: dict[str, Any]) -> str:
    original_index = {(row["system_id"], row["case_id"]): row for row in original}
    replay_index = {(row["system_id"], row["case_id"]): row for row in replayed}
    changed = []
    for key, before in original_index.items():
        after = replay_index[key]
        fields_changed = before.get("fields") != after.get("fields")
        missing_changed = before.get("missing_fields") != after.get("missing_fields")
        citations_changed = before.get("citations") != after.get("citations")
        draft_fields_before = (before.get("draft") or {}).get("proposed_fields")
        draft_fields_after = (after.get("draft") or {}).get("proposed_fields")
        if fields_changed or missing_changed or citations_changed or draft_fields_before != draft_fields_after:
            changed.append((key, before, after, fields_changed, missing_changed, citations_changed))

    lines = [
        "# Case-level changes — offline replay diagnostic", "",
        f"Label: `{LABEL}`. The replay consumes only saved parsed objects and saved retrieval hits; it is not a new Gemini run.", "",
        "## Actual processed-output changes", "",
    ]
    if not changed:
        lines.append("No processed output changed.")
    else:
        lines += [
            "| Case | Arm | Changed fields | Runtime missing before → replay | Citations changed? |",
            "| --- | --- | --- | --- | --- |",
        ]
        for (system, case_id), before, after, fields_changed, missing_changed, citations_changed in changed:
            field_names = []
            old_fields = before.get("fields", {})
            new_fields = after.get("fields", {})
            for field in sorted(set(old_fields) | set(new_fields)):
                if old_fields.get(field) != new_fields.get(field):
                    field_names.append(field)
            if not field_names and (before.get("draft") or {}).get("proposed_fields") != (after.get("draft") or {}).get("proposed_fields"):
                field_names.append("draft metadata only")
            if missing_changed:
                field_names.append("missing_fields")
            lines.append(
                f"| `{case_id}` | `{system}` | {', '.join(field_names) or 'none'} | "
                f"`{before.get('missing_fields')}` → `{after.get('missing_fields')}` | {citations_changed} |"
            )

    lines += ["", "## Three Step 2 missing-set discrepancies", "",
              "| Case / arm | Model-parsed value and declaration | Original runtime | Replay runtime | Classification |",
              "| --- | --- | --- | --- | --- |"]
    discrepancy_rows = [
        ("AI_PROTO_DEV_DRAFT_004", "llm_no_retrieval", "model supplied a speculative nonempty hypothesis while declaring it missing", "[]", "[]", "Model output inconsistency; runtime presence-based result is not changed by this narrow sentinel fix."),
        ("AI_PROTO_DEV_DRAFT_004", "llm_rag", 'hypothesis="missing"; model declared [hypothesis]', "[]", "[hypothesis]", 'Confirmed runtime bug: exact placeholder was treated as a value; now omitted and derived missing.'),
        ("AI_PROTO_DEV_DRAFT_006", "llm_no_retrieval", "assay omitted; model declared []", "[assay]", "[assay]", "Model declaration error; runtime correctly derives absence. No runtime bug."),
    ]
    actual_by_key = {(row["system_id"], row["case_id"]): row for row in original}
    replay_by_key = {(row["system_id"], row["case_id"]): row for row in replayed}
    for case_id, arm, description, old, new, classification in discrepancy_rows:
        before = actual_by_key[(arm, case_id)]
        after = replay_by_key[(arm, case_id)]
        raw = before.get("raw_output") or {}
        value_field = "assay" if case_id == "AI_PROTO_DEV_DRAFT_006" else "hypothesis"
        actual_description = (f"`{description}`; parsed {value_field}={raw.get(value_field)!r}; "
                              f"declared `{raw.get('missing_fields')}`")
        lines.append(f"| `{case_id}` / `{arm}` | {actual_description} | `{before.get('missing_fields')}` | `{after.get('missing_fields')}` | {classification} |")

    lines += ["", "## Preserved issues outside this fix", "",
              "- `AI_PROTO_DEV_DRAFT_003`: both arms retain `sex=female` plus `specimen_context='not specified beyond the fictional protocol'`. No context rewrite or conversion to another field was performed; this remains an output/reference interpretation issue for owner review.",
              "- `AI_PROTO_DEV_DRAFT_011`: RAG still removes nested `sources` from the control suggestion by design. The missing rationale is not invented; citation metadata is not promoted into claim support.",
              "- Case 012 remains the lexical no-hit diagnostic, separate from the 11 protocol extraction cases. The RAG arm retains its no-hit abstention and provider-not-called state.",
              "- Raw parsed objects and raw declared missing lists are unchanged. See `offline_replay_outputs.json` → `missing_fields_provenance` for model declaration, original runtime derivation, and replay derivation side by side.",
              "", "## Step 2 packet cross-check", "",
              f"The authoritative packet `{DEFAULT_STEP2.as_posix()}/field_error_analysis.json` contains {len(step2.get('missing_field_comparison', []))} missing-set rows overall. Only the three discrepancy rows above were replayed; the packet and source run were not modified.", ""]
    return "\n".join(lines)


def _metric_projection(original: dict[str, Any], replay: dict[str, Any]) -> dict[str, Any]:
    old_by_system = _map_metrics(original)
    new_by_system = _map_metrics(replay)
    output = {}
    for system in ("manual_template", "llm_no_retrieval", "llm_rag"):
        old = old_by_system[system]
        new = new_by_system[system]
        output[system] = {
            "case_denominator": old["case_count"],
            "status_counts": {"original": old["status_counts"], "replay": new["status_counts"]},
            "field_exact": {"original": old["field_exact"], "replay": new["field_exact"]},
            "workflow_missing_fields": {"original": old["missing_fields"], "replay": new["missing_fields"]},
            "model_declared_missing_fields": {
                "original": old["raw_missing_declaration"], "replay": new["raw_missing_declaration"],
            },
            "schema_validity": {"original": old["schema_validity"], "replay": new["schema_validity"]},
            "citations": {"original": old["citations"], "replay": new["citations"]},
            "retrieval": {"original": old["retrieval"], "replay": new["retrieval"]},
            "latency_note": "Historical provider-run elapsed_seconds were preserved; offline processing latency was not measured.",
        }
    return output


def _run(args: argparse.Namespace) -> dict[str, Any]:
    repo = ROOT
    run_dir = (repo / args.run_dir).resolve()
    step2_dir = (repo / args.step2_dir).resolve()
    package_dir = (repo / args.frozen_package).resolve()
    audit_dir = (repo / args.audit_dir).resolve()
    if audit_dir.exists():
        raise FileExistsError(f"audit output already exists; refusing overwrite: {audit_dir}")
    for path in (run_dir, step2_dir, package_dir):
        if not path.is_dir() or not path.is_relative_to(repo):
            raise ValueError(f"expected source directory missing or outside repo: {path}")

    corpus_path = package_dir / "protocol_development_corpus_draft.jsonl"
    rubric_path = package_dir / "reference_owner_reviewed.json"
    manifest_path = package_dir / "corpus.manifest.json"
    inputs = comparison.prepare_inputs(corpus_path, rubric_path, manifest_path, generation=False)
    config, original_records, outputs_sha = comparison.verify_run(run_dir, inputs)
    original_metrics = comparison.read_json(run_dir / "metrics.json")
    recomputed_original = comparison.score_comparison(inputs, original_records, config, outputs_sha)
    if recomputed_original != original_metrics:
        raise ValueError("current evaluator no longer exactly reproduces the saved frozen metrics")

    expected_identity = {
        "case_outputs_sha256": outputs_sha,
        "corpus_sha256": inputs["corpus_sha256"],
        "rubric_sha256": inputs["rubric_sha256"],
        "manifest_sha256": inputs["expected_manifest_sha256"],
    }
    step2 = comparison.read_json(step2_dir / "field_error_analysis.json")
    step2_identity = step2.get("run_identity", {})
    for key, value in expected_identity.items():
        if step2_identity.get(key) != value:
            raise ValueError(f"authoritative Step 2 packet identity mismatch: {key}")

    expected_discrepancies = {
        ("AI_PROTO_DEV_DRAFT_004", "llm_no_retrieval"): (["hypothesis"], []),
        ("AI_PROTO_DEV_DRAFT_004", "llm_rag"): (["hypothesis"], []),
        ("AI_PROTO_DEV_DRAFT_006", "llm_no_retrieval"): ([], ["assay"]),
    }
    found = {(row["case_id"], row["branch"]): (row["model_declared"], row["runtime_computed"])
             for row in step2.get("missing_field_comparison", []) if row.get("same_as_sets") is False}
    if found != expected_discrepancies:
        raise ValueError(f"Step 2 missing-set discrepancies differ from the reviewed three-row set: {found}")
    original_index = {(row["system_id"], row["case_id"]): row for row in original_records}
    for (case_id, system), (declared, runtime) in expected_discrepancies.items():
        row = original_index[(system, case_id)]
        actual_declared = (row.get("raw_output") or {}).get("missing_fields")
        if actual_declared != declared or row.get("missing_fields") != runtime:
            raise ValueError(f"Step 2 discrepancy does not match stored raw/processed record: {case_id}/{system}")

    manifest = comparison.read_json(manifest_path)
    if (manifest.get("owner_approved") is not True
            or manifest.get("provider_sharing_approved") is not True
            or manifest.get("protocol_text_sharing_approved") is not True
            or manifest.get("approved_provider_id") != config.get("provider_id")
            or manifest.get("approved_provider_endpoint") != config.get("provider_endpoint")):
        raise ValueError("frozen manifest does not match the historical run identity; replay stopped")

    test_cmd = [sys.executable, "-m", "pytest", "-q", "tests/test_workbench_intake.py",
                "tests/test_workbench_rag_runtime.py", "tests/test_ai_v2_comparison.py"]
    test_code, test_log = test_command(test_cmd, repo)
    diff_code, diff_log = test_command(["git", "diff", "--check"], repo)
    whitespace_code, whitespace_log = test_command([
        sys.executable, "-c",
        "from pathlib import Path; fs=['src/drosophila_pd/workbench/intake.py','tests/test_workbench_intake.py','tests/test_ai_v2_comparison.py','scripts/replay_ai_v2_postprocessing.py']; bad=[f'{p}:{n}' for p in fs for n,line in enumerate(Path(p).read_bytes().splitlines(),1) if line.endswith((b' ',b'\\t'))]; print('trailing_whitespace:',bad); raise SystemExit(bool(bad))",
    ], repo)
    test_log = "STEP 3 REGRESSION TESTS\n" + test_log + "\nGIT DIFF CHECK\n" + diff_log + "\nNEW/UNTRACKED FILE WHITESPACE CHECK\n" + whitespace_log
    if test_code or diff_code or whitespace_code:
        print(test_log, file=sys.stderr)
        raise RuntimeError("tests or diff/whitespace checks failed; replay outputs were not created")

    rubric = inputs["rubric"]
    cases = {case["case_id"]: case for case in rubric["cases"]}
    replayed = copy.deepcopy(original_records)
    invocation_count = 0
    processed_rows = 0
    replay_preservation_checks = []
    for record in replayed:
        if (record.get("system_id") not in {"llm_no_retrieval", "llm_rag"}
                or record.get("status") != "COMPLETED"
                or not isinstance(record.get("raw_output"), dict)):
            continue
        raw = copy.deepcopy(record["raw_output"])
        provider = LocalReplayProvider(raw, config)
        original_citations = copy.deepcopy(record.get("citations", []))
        original_raw_digest = sha256(comparison.encoded(record["raw_output"]))
        if record["system_id"] == "llm_rag":
            corpus = SavedEvidenceCorpus(manifest, inputs["expected_manifest_sha256"],
                                         inputs["corpus_sha256"], record["retrieved_evidence"])
            draft = intake.create_rag_intake_draft(
                cases[record["case_id"]]["protocol_text"], corpus, provider, k=5,
                prompt_version=config["prompt_version"],
            )
            if draft["rag"]["retrieved_evidence"] != record["retrieved_evidence"]:
                raise ValueError(f"saved retrieval evidence changed during local replay: {record['case_id']}")
            original_rag = (record.get("draft") or {}).get("rag", {})
            if draft["rag"]["retrieval_sha256"] != original_rag.get("retrieval_sha256"):
                raise ValueError(f"retrieval identity changed during local replay: {record['case_id']}")
        else:
            draft = intake.create_intake_draft(
                cases[record["case_id"]]["protocol_text"], provider,
                prompt_version=config["prompt_version"],
            )
        if provider.invocations != 1:
            raise ValueError("local replay did not consume exactly one saved parsed object")
        invocation_count += provider.invocations
        new_citations = draft["proposed_fields"].get("citations", [])
        if new_citations != original_citations:
            raise ValueError(f"placeholder post-processing unexpectedly changed citations: {record['case_id']}")
        record.update(
            draft=draft,
            fields={key: value for key, value in draft["proposed_fields"].items() if key != "citations"},
            citations=new_citations,
            missing_fields=draft["missing_fields"],
        )
        record["processed_schema_valid"] = comparison._processed_draft_schema_valid(
            draft, system_id=record["system_id"], input_sha256=record["input_sha256"],
        )
        record["processed_schema_status"] = "VALID" if record["processed_schema_valid"] else "INVALID"
        if record["raw_output"] != raw or sha256(comparison.encoded(record["raw_output"])) != original_raw_digest:
            raise ValueError("raw parsed provider object was modified during replay")
        replay_preservation_checks.append({
            "system_id": record["system_id"], "case_id": record["case_id"],
            "raw_parsed_object_unchanged": True, "citation_ids_unchanged": True,
        })
        processed_rows += 1

    replay_sha = comparison.digest(comparison.encoded({
        "schema_version": "ai-v2-comparison-outputs-2", "records": replayed,
    }))
    replay_metrics = comparison.score_comparison(inputs, replayed, config, replay_sha)
    if replay_metrics["lexical_no_hit_diagnostics"] != original_metrics["lexical_no_hit_diagnostics"]:
        raise ValueError("diagnostic separation/provider-call behavior changed during replay")
    if len(replayed) != len(original_records):
        raise ValueError("replay changed the number of source records")
    old_by_system = _map_metrics(original_metrics)
    new_by_system = _map_metrics(replay_metrics)
    rag_old = old_by_system["llm_rag"]
    rag_new = new_by_system["llm_rag"]
    if (rag_old["schema_validity"] != rag_new["schema_validity"]
            or rag_old["citations"] != rag_new["citations"]):
        raise ValueError("schema or citation metrics changed unexpectedly")
    old_retrieval_ids = {
        (row["system_id"], row["case_id"]): [
            (item["source_id"], item["chunk_id"]) for item in row.get("retrieved_evidence", [])
        ] for row in original_records
    }
    new_retrieval_ids = {
        (row["system_id"], row["case_id"]): [
            (item["source_id"], item["chunk_id"]) for item in row.get("retrieved_evidence", [])
        ] for row in replayed
    }
    if old_retrieval_ids != new_retrieval_ids:
        raise ValueError("retrieved chunk IDs changed unexpectedly")

    run_code = config.get("code_sha256", {})
    before = {"intake": args.before_intake_sha256.lower(),
              "comparison": args.before_comparison_sha256.lower()}
    current = {
        "intake": sha256((repo / "src/drosophila_pd/workbench/intake.py").read_bytes()),
        "comparison": sha256((repo / "src/drosophila_pd/ai_v2/comparison.py").read_bytes()),
    }
    if current["comparison"] != before["comparison"]:
        raise ValueError("comparison/evaluator source changed during this task; refusing to claim unchanged evaluator")

    audit_dir.mkdir(parents=True, exist_ok=False)
    test_path = audit_dir / "test_results.txt"
    with test_path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(test_log)
    replay_payload = {
        "label": LABEL,
        "status": "OFFLINE_REPLAY_COMPLETE",
        "partition": "DEVELOPMENT",
        "heldout_status": "LOCKED_NOT_READ",
        "provider_called": False,
        "outbound_provider_calls": 0,
        "local_saved_object_replay_invocations": invocation_count,
        "original_run_dir": str(run_dir),
        "original_case_outputs_sha256": outputs_sha,
        "replay_case_outputs_sha256": replay_sha,
        "corpus_sha256": inputs["corpus_sha256"],
        "rubric_sha256": inputs["rubric_sha256"],
        "manifest_sha256": inputs["expected_manifest_sha256"],
        "evaluator_policy_version": comparison.POLICY_VERSION,
        "raw_response_text_reconstructed": False,
        "retrieval_recomputed": False,
        "replay_method": "Saved raw_output parsed mappings and saved retrieval hits passed to the local postprocessor; no network-capable provider object used.",
        "preservation_checks": replay_preservation_checks,
        "missing_fields_provenance": _trace_rows(original_records, replayed),
        "records": replayed,
    }
    write_exclusive(audit_dir / "offline_replay_outputs.json", replay_payload)
    metrics_payload = {
        "label": LABEL,
        "post_hoc_diagnostic_not_independent_or_new_gemini_run": True,
        "does_not_replace_frozen_v2_metrics": True,
        "evaluator_policy_version": comparison.POLICY_VERSION,
        "stored_original_metrics_exactly_reproduced_before_replay": True,
        "original_metrics_sha256": sha256((run_dir / "metrics.json").read_bytes()),
        "original_case_outputs_sha256": outputs_sha,
        "replay_case_outputs_sha256": replay_sha,
        "heldout_status": "LOCKED_NOT_READ",
        "metrics": _metric_projection(original_metrics, replay_metrics),
        "lexical_no_hit_diagnostics": {
            "original": original_metrics["lexical_no_hit_diagnostics"],
            "replay": replay_metrics["lexical_no_hit_diagnostics"],
            "identical": True,
        },
    }
    write_exclusive(audit_dir / "original_vs_replay_metrics.json", metrics_payload)
    write_text_exclusive(audit_dir / "case_level_changes.md", _build_case_report(original_records, replayed, step2))

    report = f"""# Runtime placeholder fix and offline replay report

Label: `{LABEL}`
Interpretation: post-hoc diagnostic over saved development outputs; not an independent evaluation or a new Gemini run. It does not replace the frozen V2 metrics.

## Root cause and narrow fix

`docs/ai_v2/rag_contract.md` and `intake.py::_protocol_output_contract` say unavailable required values must be omitted and named in `missing_fields`; the frozen synthetic protocol's “Extraction rules” also says unknown required fields remain absent. The response schema types core fields as strings. Before this fix, `_format_intake_draft` accepted every nonempty string as present. Thus the exact parsed placeholder `hypothesis: "missing"` was retained as a hypothesis and removed from runtime-derived `missing_fields` even though the model declared it missing.

The runtime now treats only the exact trimmed lowercase string `"missing"` as absent for the five core scalar text slots (`name`, `hypothesis`, `falsifiable_prediction`, `assay`, `primary_metric`). Empty/whitespace and non-string values remain absent as before. No substring matching is used; text such as “The missing signal is predicted…” remains a value. No content is synthesized. Context, suggestions, citations, rubric, prompt and evaluator rules were not changed.

## Three Step 2 discrepancies and classification

| Case / arm | Stored parsed value | Model-declared missing | Original runtime | Corrected replay | Classification |
| --- | --- | --- | --- | --- | --- |
| `AI_PROTO_DEV_DRAFT_004` / no retrieval | Nonempty speculative hypothesis sentence | `hypothesis` | `[]` | `[]` | Model output inconsistency / unsupported value; runtime's presence-based rule behaved consistently. Not fixed by a placeholder rule. |
| `AI_PROTO_DEV_DRAFT_004` / RAG | `hypothesis="missing"` | `hypothesis` | `[]` | `[hypothesis]` | Confirmed runtime post-processing bug: exact missing placeholder was treated as data. Fixed. |
| `AI_PROTO_DEV_DRAFT_006` / no retrieval | `assay` omitted | `[]` | `[assay]` | `[assay]` | Model's missing declaration error; runtime correctly detects absent processed value. |

The Step 2 authoritative packet and stored records matched these three rows exactly. A mismatch between model declaration and runtime derivation is not automatically a runtime defect.

## Offline replay method and identity

- Input run: `{run_dir}`; original output SHA-256 `{outputs_sha}`.
- Frozen corpus/rubric/manifest SHA-256: `{inputs['corpus_sha256']}` / `{inputs['rubric_sha256']}` / `{inputs['expected_manifest_sha256']}`.
- Original saved metrics were re-scored first and matched exactly as parsed JSON objects using existing policy `{comparison.POLICY_VERSION}`; no evaluator rule was changed.
- Replay used only each record's saved `raw_output` parsed mapping and saved top-5 retrieval records. It did not reconstruct provider response text, recompute retrieval, read held-out data, or contact a provider.
- Local stub invocations: `{invocation_count}`; outbound provider calls: `0`.
- Historical provider elapsed times remain attached to records; offline replay latency was not measured.

## Code identity

| File | Frozen run code SHA-256 | Immediately before this fix | After fix/replay | Note |
| --- | --- | --- | --- | --- |
| `src/drosophila_pd/workbench/intake.py` | `{run_code.get('intake')}` | `{before['intake']}` | `{current['intake']}` | Only the exact core-string placeholder handling changed in this task. |
| `src/drosophila_pd/ai_v2/comparison.py` | `{run_code.get('comparison')}` | `{before['comparison']}` | `{current['comparison']}` | Not edited in this task. Current evaluator exactly reproduced the stored original metrics before replay. Its byte hash differs from the historical run hash. |

## Replay metric highlights

- RAG workflow `missing_fields`, aggregated over the same 11 protocol cases (diagnostic case 012 excluded): original TP/FP/FN `{rag_old['missing_fields']['tp']}/{rag_old['missing_fields']['fp']}/{rag_old['missing_fields']['fn']}`, F1 `{rag_old['missing_fields']['f1']:.3f}`; replay TP/FP/FN `{rag_new['missing_fields']['tp']}/{rag_new['missing_fields']['fp']}/{rag_new['missing_fields']['fn']}`, F1 `{rag_new['missing_fields']['f1']:.3f}`. F1 uses `2TP/(2TP+FP+FN)`; its denominator is `{2 * rag_old['missing_fields']['tp'] + rag_old['missing_fields']['fp'] + rag_old['missing_fields']['fn']}` original and `{2 * rag_new['missing_fields']['tp'] + rag_new['missing_fields']['fp'] + rag_new['missing_fields']['fn']}` replay. Precision denominator is `TP+FP`; recall denominator is `TP+FN`.
- RAG field exact: `{rag_old['field_exact']['correct']}/{rag_old['field_exact']['denominator']}` → `{rag_new['field_exact']['correct']}/{rag_new['field_exact']['denominator']}`.
- RAG raw/model-declared missing F1 remains `{rag_old['raw_missing_declaration']['f1']:.3f}` → `{rag_new['raw_missing_declaration']['f1']:.3f}`; the raw object is unchanged.
- Raw schema, processed schema, citation metrics, retrieval IDs, status counts and case-012 diagnostic are checked in `original_vs_replay_metrics.json`. Retrieval IDs and citations are invariant; case 012 remains separate and unchanged.
- No-retrieval model errors remain: the unsupported speculative hypothesis in case 004 and the undeclared missing assay in case 006. This fix does not improve them.

## Checks and pending items

The actual regression test command and `git diff --check` output are in `test_results.txt`. Frozen corpus, rubric, prompt, source run and Step 2 packet remain unchanged. No manual baseline was filled and no study, job or simulation was approved/run.

Owner follow-up remains required for the saved human claim-support annotations and the interpretation of case 003's `specimen_context` phrase. The manual comparator baseline remains `PENDING`; this replay is not a full three-arm comparison and makes no independent-review or biological-validation claim.
"""
    with (audit_dir / "runtime_fix_report.md").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(report)

    files = {}
    for name in ("runtime_fix_report.md", "offline_replay_outputs.json",
                 "original_vs_replay_metrics.json", "case_level_changes.md", "test_results.txt"):
        files[name] = sha256((audit_dir / name).read_bytes())
    inventory = {
        "algorithm": "SHA-256",
        "label": LABEL,
        "files": files,
        "source_inputs": {
            "original_case_outputs.json": outputs_sha,
            "original_metrics.json": sha256((run_dir / "metrics.json").read_bytes()),
            "step2_field_error_analysis.json": sha256((step2_dir / "field_error_analysis.json").read_bytes()),
            "frozen_corpus.jsonl": inputs["corpus_sha256"],
            "frozen_rubric.json": inputs["rubric_sha256"],
            "frozen_manifest.json": inputs["expected_manifest_sha256"],
        },
        "code_sha256": {
            "frozen_run": run_code,
            "before_step3_fix": before,
            "after_step3_fix": current,
            "audit_driver": sha256(Path(__file__).read_bytes()),
        },
        "inventory_self_hash": "not included; a file cannot include its own stable digest",
    }
    write_exclusive(audit_dir / "sha256_inventory.json", inventory)
    return {
        "status": "PASS",
        "label": LABEL,
        "audit_dir": str(audit_dir),
        "processed_provider_rows_replayed": processed_rows,
        "local_saved_object_replay_invocations": invocation_count,
        "outbound_provider_calls": 0,
        "test_command_exit_code": test_code,
        "git_diff_check_exit_code": diff_code,
        "replay_metric_sha256": sha256((audit_dir / "original_vs_replay_metrics.json").read_bytes()),
        "heldout_status": "LOCKED_NOT_READ",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    parser.add_argument("--step2-dir", type=Path, default=DEFAULT_STEP2)
    parser.add_argument("--frozen-package", type=Path, default=DEFAULT_PACKAGE)
    parser.add_argument("--audit-dir", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--before-intake-sha256", required=True)
    parser.add_argument("--before-comparison-sha256", required=True)
    args = parser.parse_args()
    try:
        result = _run(args)
    except Exception as error:
        print(f"STEP3 FAILED: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
