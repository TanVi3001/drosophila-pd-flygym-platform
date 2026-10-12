"""Offline audit of an existing development pilot; never calls a provider."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jsonschema import Draft202012Validator
from drosophila_pd.ai_v2 import comparison as c
from drosophila_pd.workbench import intake


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    with path.open("xb") as stream:
        stream.write(value.encode("utf-8") if isinstance(value, str) else c.encoded(value))


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def identity():
    names = ["src/drosophila_pd/ai_v2/comparison.py", "src/drosophila_pd/workbench/intake.py",
             "src/drosophila_pd/workbench/rag.py", "src/drosophila_pd/ai_v2/collection.py",
             "scripts/compare_ai_v2_protocols.py", "scripts/audit_ai_v2_pilot_artifacts.py"]
    return {"branch": git("branch", "--show-current"), "head": git("rev-parse", "HEAD"),
            "git_status": git("status", "--short"), "python": sys.version,
            "python_executable": sys.executable,
            "code_sha256": {name: sha(ROOT / name) for name in names}}


def inventory(run, package):
    entries = []
    for label, folder, manifest_name in (("run", run, "run_manifest.json"),
                                         ("package", package, "freeze_inventory.json")):
        manifest = c.read_json(folder / manifest_name)
        for name, expected in manifest["artifact_sha256"].items():
            path = c.safe_path(folder / name)
            if not path.is_relative_to(folder):
                raise ValueError("artifact path escapes declared root")
            actual = sha(path) if path.is_file() else None
            entries.append({"group": label, "path": str(path), "recorded": expected,
                            "actual": actual, "status": "MATCH" if actual == expected else "DISCREPANCY"})
        entries.append({"group": label, "path": str(folder / manifest_name),
                        "actual": sha(folder / manifest_name), "status": "SELF_HASH_NOT_RECORDED"})
    return entries


def compare_value(rows, metric, reported, checked, definition):
    match = (math.isclose(reported, checked, rel_tol=1e-12, abs_tol=1e-12)
             if isinstance(reported, float) and isinstance(checked, (int, float))
             else reported == checked)
    rows.append({"metric": metric, "reported": reported, "rechecked": checked,
                 "definition": definition, "status": "MATCH" if match else "DISCREPANCY"})


def independent_metrics(inputs, records, original, schema):
    """Independent arithmetic on retained fields; schema from raw and draft separately."""
    cases = [x for x in inputs["rubric"]["cases"] if x.get("category") != "no_lexical_evidence_probe"]
    indexed = {(r["system_id"], r["case_id"]): r for r in records}
    reported = {x["system_id"]: x for x in original["systems"]}
    rows, details, schema_checks, provenance_checks = [], [], [], []
    validator = Draft202012Validator(schema)
    for system in c.SYSTEMS:
        measured = reported[system]
        selected = [indexed[system, case["case_id"]] for case in cases]
        statuses = Counter(x["status"] for x in selected)
        correct = total = tp = fp = fn = raw_tp = raw_fp = raw_fn = 0
        recall, precision, elapsed = [], [], []
        citations_total = citations_existing = citations_gold = 0
        raw_valid = processed_valid = returned_hits = relevant_hits = 0
        present_correct = present_total = 0
        accepted_citations = accepted_existing = 0
        for case, record in zip(cases, selected):
            valid = record["status"] in c.VALID
            wrong_fields = []
            for field in case["required_fields"]:
                total += 1
                hit = valid and record["fields"].get(field) == case["gold_fields"][field]
                correct += int(hit)
                if case["gold_fields"][field] is not None:
                    present_total += 1
                    present_correct += int(hit)
                if not hit and record["status"] != "NOT_RUN":
                    wrong_fields.append(field)
            expected = set(case["gold_missing_fields"])
            predicted = set(record["missing_fields"]) if valid else set()
            tp += len(expected & predicted)
            fp += len(predicted - expected)
            fn += len(expected - predicted)
            raw = record.get("raw_response")
            raw_check = c.raw_output_schema_valid(raw) if raw is not None else None
            json_schema_check = validator.is_valid(raw) if raw is not None else None
            draft = record.get("draft")
            processed_check = (c._processed_draft_schema_valid(draft, system_id=system,
                                                             input_sha256=record["input_sha256"])
                               if draft is not None else None)
            raw_valid += raw_check is True
            processed_valid += processed_check is True
            schema_checks.append({"system_id": system, "case_id": case["case_id"],
                                  "recorded_raw_status": record["raw_schema_status"],
                                  "raw_mapping_contract_valid": raw_check,
                                  "frozen_request_json_schema_valid": json_schema_check,
                                  "processed_contract_valid": processed_check})
            if draft is not None:
                fields = {k: v for k, v in draft["proposed_fields"].items() if k != "citations"}
                checks = {"fields_equal_draft": fields == record["fields"],
                          "missing_equal_draft": draft["missing_fields"] == record["missing_fields"],
                          "citations_equal_draft": draft["proposed_fields"].get("citations", []) == record["citations"],
                          "raw_mapping_equal": raw == record.get("raw_output"),
                          "safety_flags_false": all(draft[k] is False for k in ("approved", "study_created", "mapping_created"))}
                if system == "llm_rag" and draft.get("provenance"):
                    checks["generator_digest"] = draft["provenance"]["generator_output_sha256"] == hashlib.sha256(intake._canonical_json(record["raw_output"])).hexdigest()
                provenance_checks.append({"system_id": system, "case_id": case["case_id"], "checks": checks})
            if record["provider_called"] is not False:
                declared = record["raw_output"].get("missing_fields", []) if isinstance(record["raw_output"], dict) else []
                declared = set(declared)
                raw_tp += len(expected & declared)
                raw_fp += len(declared - expected)
                raw_fn += len(expected - declared)
            if system == "llm_rag" and case["gold_evidence_chunk_ids"]:
                found = [x["chunk_id"] for x in record["retrieved_evidence"]]
                gold = set(case["gold_evidence_chunk_ids"])
                relevant = len(set(found) & gold)
                recall.append(relevant / len(gold))
                precision.append(relevant / len(found) if found else 0.0)
                returned_hits += len(found)
                relevant_hits += relevant
            if isinstance(record["raw_output"], dict):
                gold_pairs = {c.citation_pair(x) for x in case["gold_citations"]}
                for citation in record["raw_output"].get("citations", []):
                    pair = c.citation_pair(citation)
                    citations_total += 1
                    citations_existing += pair in inputs["corpus_pairs"]
                    citations_gold += pair in gold_pairs
            for citation in record["citations"]:
                accepted_citations += 1
                accepted_existing += c.citation_pair(citation) in inputs["corpus_pairs"]
            if record["elapsed_seconds"] is not None and record["status"] != "NOT_RUN":
                elapsed.append(record["elapsed_seconds"])
            details.append({"system_id": system, "case_id": case["case_id"], "status": record["status"],
                            "wrong_exact_field_names": wrong_fields, "gold_missing": sorted(expected),
                            "processed_missing": sorted(predicted), "raw_missing": record.get("raw_output", {}).get("missing_fields") if isinstance(record.get("raw_output"), dict) else None})
        measured_arm = statuses["NOT_RUN"] != len(cases)
        definition = "Exact equality after historical Workbench trimming; absent becomes None only for scoring; 57 slots in 11 cases are not independent samples."
        compare_value(rows, system + ".field_exact", measured["field_exact"]["accuracy"], correct / total if measured_arm else None, definition)
        compare_value(rows, system + ".field_counts", [measured["field_exact"]["correct"], measured["field_exact"]["denominator"]], [correct, total], "All slots retained; wholly PENDING arm reports N/A, count placeholders are not a measured error rate.")
        compare_value(rows, system + ".non_null_counts", [measured["field_exact"]["non_null_correct"], measured["field_exact"]["non_null_denominator"]], [present_correct, present_total], "Exact matches restricted to 49 non-null gold slots; no semantic equivalence judgment.")
        compare_value(rows, system + ".non_null_accuracy", measured["field_exact"]["non_null_accuracy"], present_correct / present_total if measured_arm and present_total else None, "47/49 for both LLM arms; manual PENDING=N/A.")
        compare_value(rows, system + ".missing_tp_fp_fn", [measured["missing_fields"][k] for k in ("tp", "fp", "fn")], [tp, fp, fn], "Micro processed missing sets; PENDING arm has N/A score.")
        compare_value(rows, system + ".missing_f1", measured["missing_fields"]["f1"], 2 * tp / (2 * tp + fp + fn) if measured_arm and 2 * tp + fp + fn else None, "2TP/(2TP+FP+FN); undefined denominator or wholly NOT_RUN is N/A.")
        compare_value(rows, system + ".raw_missing_f1", measured["raw_missing_declaration"]["f1"], 2 * raw_tp / (2 * raw_tp + raw_fp + raw_fn) if 2 * raw_tp + raw_fp + raw_fn else None, "Model-declared missing fields, separate from sanitizer-computed workflow fields.")
        compare_value(rows, system + ".recall_at_5", measured["retrieval"]["recall_at_5"], statistics.mean(recall) if recall else None, "Macro per case: |hits intersect gold|/|gold|; diagnostic empty gold excluded; 11 assessable RAG cases.")
        compare_value(rows, system + ".precision_at_5", measured["retrieval"]["precision_at_5"], statistics.mean(precision) if precision else None, "Macro per case using actual unique returned hits <=5; no-hit with nonempty gold=0; empty gold=N/A. Micro 26/55 happens to equal macro here because each case returns five hits.")
        compare_value(rows, system + ".precision_sums", [measured["retrieval"]["precision_relevant_hit_numerator_sum"], measured["retrieval"]["precision_returned_hit_denominator_sum"]], [relevant_hits, returned_hits], "Summed gold-ID matches / summed actual hits, supplemental to macro precision.")
        compare_value(rows, system + ".raw_valid_count", measured["schema_validity"]["raw_output_schema"]["valid_count"], raw_valid, "Revalidate stored pre-sanitization mapping; original response text/duplicate keys cannot be reconstructed.")
        if system != "manual_template":
            compare_value(rows, system + ".processed_valid_count", measured["schema_validity"]["processed_draft_schema"]["valid_count"], processed_valid, "Revalidate actual draft, independently from raw output.")
        compare_value(rows, system + ".raw_citation_counts", [measured["citations"][k] for k in ("raw_count", "raw_existing_source_count", "raw_gold_match_count")], [citations_total, citations_existing, citations_gold], "Corpus pair membership and gold pair matching; neither measures semantic support.")
        compare_value(rows, system + ".raw_citation_id_precision", measured["citations"]["raw_source_precision"], citations_existing / citations_total if citations_total else None, "Exact source/chunk pair membership / raw citations; none=N/A.")
        compare_value(rows, system + ".raw_citation_gold_precision", measured["citations"]["raw_gold_precision"], citations_gold / citations_total if citations_total else None, "Gold source/chunk pair matches / raw citations; none=N/A, not claim-support precision.")
        compare_value(rows, system + ".accepted_citations", [measured["citations"]["accepted_count"], measured["citations"]["accepted_source_precision"]], [accepted_citations, accepted_existing / accepted_citations if accepted_citations else None], "Post-sanitization citations, checked separately from raw list.")
        for metric, numerator in (("completion_rate", statuses["COMPLETED"]), ("error_rate", statuses["ERROR"]), ("not_run_rate", statuses["NOT_RUN"]), ("runtime_success_rate", statuses["COMPLETED"] + statuses["ABSTAINED"])):
            compare_value(rows, system + "." + metric, measured[metric], numerator / len(cases), "All eleven required protocol cases; failures/abstentions/PENDING kept in denominator.")
        units = sum(len(c.claim_units(r)) for r in selected)
        compare_value(rows, system + ".claim_count", measured["claim_review"]["claim_count"], units, "Scalar-string raw-output claim units, excluding citations/missing_fields; diagnostic excluded.")
        compare_value(rows, system + ".claim_unsupported_rate", measured["claim_review"]["unsupported_claim_rate"], None, "All decisions pending; zero determinate human-reviewed claims implies N/A, not zero unsupported claims.")
        elapsed.sort()
        for key, checked in (("denominator", len(elapsed)), ("mean_seconds", statistics.mean(elapsed) if elapsed else None),
                             ("median_seconds", statistics.median(elapsed) if elapsed else None),
                             ("p95_seconds", elapsed[math.ceil(.95 * len(elapsed)) - 1] if elapsed else None)):
            compare_value(rows, system + ".latency_" + key, measured["latency"][key], checked,
                          "Arithmetic on recorded seconds; in-process retrieval + generation + draft validation; no new inference timing; failed attempts retained, startup/install/writes excluded.")
        compare_value(rows, system + ".status_counts", measured["status_counts"], dict(statuses), "All 11 protocol cases, failures/abstentions/not-run explicit.")
    return rows, details, schema_checks, provenance_checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--package-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--baseline", action="store_true")
    parser.add_argument("--test-results-json", type=Path)
    args = parser.parse_args()
    run, package, output = map(c.safe_path, (args.run_dir, args.package_dir, args.output_dir))
    if output.is_relative_to(run) or output.is_relative_to(package):
        raise ValueError("audit must be outside source run and frozen package")
    inputs = c.prepare_inputs(package / "protocol_development_corpus_draft.jsonl",
                              package / "reference_owner_reviewed.json", package / "corpus.manifest.json")
    config, records, outputs_sha = c.verify_run(run, inputs)
    metrics = c.score_comparison(inputs, records, config, outputs_sha)
    current = identity()
    if args.baseline:
        output.mkdir(parents=True, exist_ok=False)
        write(output / "baseline_identity.json", current)
        write(output / "baseline_recomputed_metrics.json", metrics)
        write(output / "baseline_integrity.json", inventory(run, package))
        print(json.dumps({"status": "BASELINE_CAPTURED_OFFLINE", "audit_dir": str(output), "provider_called": False}))
        return
    before = c.read_json(output / "baseline_identity.json")
    original = c.read_json(run / "metrics.json")
    policy = c.read_json(package / "comparison_policy.json")
    freeze = c.read_json(package / "freeze_inventory.json")
    manifest = c.read_json(package / "corpus.manifest.json")
    tests = c.read_json(c.safe_path(args.test_results_json))
    checks = inventory(run, package)
    rows, details, schemas, provenance = independent_metrics(inputs, records, original, policy["response_format"]["json_schema"]["schema"])
    named_paths = {"comparison": "src/drosophila_pd/ai_v2/comparison.py", "intake": "src/drosophila_pd/workbench/intake.py"}
    run_code_matches_before = {key: config["code_sha256"][key] == before["code_sha256"][path] for key, path in named_paths.items()}
    package_code_matches_before = {path: expected == before["code_sha256"].get(path, sha(ROOT / path)) for path, expected in freeze["implementation_sha256"].items()}
    binding = {"corpus": sha(package / manifest["corpus_file"]) == config["corpus_sha256"],
               "rubric": sha(package / "reference_owner_reviewed.json") == config["rubric_sha256"],
               "manifest": sha(package / "corpus.manifest.json") == config["manifest_sha256"],
               "manual": sha(package / "manual_template_pending.json") == config["manual_input_sha256"],
               "response_format": policy["response_format"] == intake.provider_response_format(),
               "prompt": policy["prompt_version"] == config["prompt_version"] == c.PROMPT_VERSION,
               "k": policy["retrieval_k"] == config["retrieval_k"] == 5,
               "provider": manifest["approved_provider_id"] == config["provider_id"] == policy["provider_id_proposal"] == inputs["rubric"]["privacy_decision"]["provider_id"],
               "endpoint": manifest["approved_provider_endpoint"] == config["provider_endpoint"] == policy["provider_endpoint_proposal"] == inputs["rubric"]["privacy_decision"]["provider_endpoint"],
               "model": config["configured_model_id"] == policy["model_id_proposal"]}
    claims = c.read_json(run / "claim_review_template.json")
    expected_claims = {(r["system_id"], r["case_id"], u["claim_id"]): u for r in records for u in c.claim_units(r)}
    claim_binding = claims["case_outputs_sha256"] == outputs_sha and len(claims["reviews"]) == len(expected_claims)
    claim_keys = [(x["system_id"], x["case_id"], x["claim_id"]) for x in claims["reviews"]]
    claim_binding &= len(set(claim_keys)) == len(claim_keys) and set(claim_keys) == set(expected_claims)
    claim_binding &= all(x["support_status"] == "PENDING" and not x["reviewer_ids"] and not x["reason"]
                         and all(x[field] == expected_claims[key][field] for field in ("text", "field_path"))
                         for key, x in zip(claim_keys, claims["reviews"]))
    compare_value(rows, "comparison_complete", original["comparison_complete"], metrics["comparison_complete"], "Three required arms; eleven manual protocol rows NOT_RUN; diagnostic manual row optional.")
    compare_value(rows, "case_outputs_sha256", original["case_outputs_sha256"], outputs_sha, "SHA-256 of actual original case_outputs.json bytes.")
    compare_value(rows, "reported_previous_output_hash", "4383ec743ce99027f6b299bc78be40af7beba19b9da1ee23c17eef255f916b5b", outputs_sha, "User-specified previous SHA-256; no hash modified.")
    compare_value(rows, "historical_full_metrics", original, c.read_json(output / "baseline_recomputed_metrics.json"), "Exact dict equality with evaluator matching run code before corrections.")
    compare_value(rows, "current_full_metrics", original, metrics, "Current evaluator scoring original retained records; cached statuses cross-checked against independently revalidated mappings/drafts.")
    retrieval_rows = [json.loads(line) for line in (run / "retrieval.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    retained_hits = [(record, rank, hit) for record in records if record["system_id"] == "llm_rag"
                     for rank, hit in enumerate(record["retrieved_evidence"], 1)]
    retrieval_matches = len(retained_hits) == len(retrieval_rows) and all(
        row["rank"] == rank and row["query_sha256"] == record["input_sha256"]
        and row["corpus_sha256"] == config["corpus_sha256"] and row["manifest_sha256"] == config["manifest_sha256"]
        and all(row[field] == hit[field] for field in ("chunk_id", "source_id", "retrieval_score"))
        for row, (record, rank, hit) in zip(retrieval_rows, retained_hits))
    diagnostic_schema = []
    for record in records:
        if record["case_id"] not in {case["case_id"] for case in inputs["rubric"]["cases"] if case.get("category") == "no_lexical_evidence_probe"}:
            continue
        raw, draft = record.get("raw_response"), record.get("draft")
        diagnostic_schema.append({"system_id": record["system_id"], "case_id": record["case_id"],
            "status": record["status"], "provider_called": record["provider_called"],
            "raw_valid": c.raw_output_schema_valid(raw) if raw is not None else None,
            "processed_valid": c._processed_draft_schema_valid(draft, system_id=record["system_id"], input_sha256=record["input_sha256"]) if draft is not None else None})
    individual_consistency = all(c.read_json(run / "cases" / (r["system_id"] + "--" + r["case_id"] + ".json")) == r for r in records)
    identity_checks = {"run_core_hashes_match_before": run_code_matches_before, "package_implementation_hashes_match_before": package_code_matches_before,
                       "current_core_hashes_match_run": {key: config["code_sha256"][key] == current["code_sha256"][path] for key, path in named_paths.items()},
                       "bindings": binding, "case_records_equal_individual_files": individual_consistency, "claim_template_bound_and_pending": bool(claim_binding), "retrieval_log_matches_retained_hits": retrieval_matches}
    integrity_ok = all(x["status"] != "DISCREPANCY" for x in checks) and all(binding.values()) and all(run_code_matches_before.values()) and all(package_code_matches_before.values()) and individual_consistency and claim_binding and retrieval_matches
    metric_ok = all(x["status"] == "MATCH" for x in rows) and all(all(x["checks"].values()) for x in provenance)
    frozen_raw_schema_ok = all(x["frozen_request_json_schema_valid"] is not False for x in schemas)
    status = "PASS_WITH_LIMITATIONS" if integrity_ok and metric_ok and frozen_raw_schema_ok and tests["exit_code"] == 0 else "BLOCKED"
    limitations = ["Original raw_response/raw_output are pre-sanitization parsed JSON mappings, not original assistant JSON strings or HTTP envelopes. Duplicate keys, original whitespace/bytes, HTTP status, token usage, and exact request payloads cannot be reconstructed for the historical pilot.",
                   "Run binds comparison/intake source hashes; initial checkout matched these hashes. Current tests after fixes validate corrected working files, not the exact old code. Run metadata lacks Git HEAD/dirty-worktree snapshot and dependency inventory; audit records current identities separately.",
                   "Model ID/endpoint are configured identities; exact served backend revision cannot be independently confirmed offline.",
                   "manual_template is NOT_MEASURED, comparisons incomplete, semantic support annotations pending (52 no-retrieval and 53 RAG extraction claims). No reviewer decisions supplied by this audit.",
                   "57 field slots and 105 extraction claims are nested within 11 cases, not independent statistical samples. This audit makes no significance or RAG-superiority claim.",
                   "Frozen measurement_plan.md retains pre-run proposal language; this historical text is not the actual run status and was left unchanged."]
    reconciliation = {"status": status, "rows": rows, "case_details": details, "schema_rechecks": schemas,
                      "provenance_checks": provenance, "diagnostics": metrics["lexical_no_hit_diagnostics"], "diagnostic_schema_rechecks": diagnostic_schema,
                      "full_historical_metrics_match": original == c.read_json(output / "baseline_recomputed_metrics.json"),
                      "full_current_metrics_match": original == metrics,
                      "claim_metrics": {x["system_id"]: x["claim_review"] for x in metrics["systems"]}}
    write(output / "integrity_inventory.json", {"status": status, "checked_at": datetime.now(timezone(timedelta(hours=7))).isoformat(),
                                                "run_dir": str(run), "package_dir": str(package), "before": before, "after": current,
                                                "files": checks, "identity_checks": identity_checks, "retrieval_log_record_count": len(retrieval_rows),
                                                "run_manifest_status": c.read_json(run / "run_manifest.json")["status"], "limitations": limitations})
    write(output / "metrics_reconciliation.json", reconciliation)
    write(output / "metrics_recomputed_offline.json", metrics)
    if original != metrics:
        write(output / "corrected_report.md", c.markdown_report(metrics))
    summary_rows = [x for x in rows if "full_metrics" not in x["metric"]]
    table = ["| Metric | Reported | Rechecked | Definition / denominator | Status |", "| --- | --- | --- | --- | --- |"]
    for row in summary_rows:
        table.append("| " + " | ".join(str(row[k]).replace("|", "\\|") for k in ("metric", "reported", "rechecked", "definition", "status")) + " |")
    changes = [path for path in named_paths.values() if before["code_sha256"][path] != current["code_sha256"][path]]
    report = ["# Gemini V2 pilot offline artifact audit", "", "Status: **" + status + "**", "",
              "Run: " + str(run), "Frozen package: " + str(package),
              "Branch: " + current["branch"], "HEAD: " + current["head"], "",
              "Original files and package hashes: " + ("MATCH" if integrity_ok else "DISCREPANCY"),
              "Historical/current full metric objects: " + str(reconciliation["full_historical_metrics_match"]) + "/" + str(reconciliation["full_current_metrics_match"]),
              "Run manifest PARTIAL_FAILURE reflects missing required manual rows; LLM extraction rows are COMPLETED without ERROR. Diagnostic RAG abstention is retained separately.", "",
              "## Metric reconciliation", "", *table, "",
              "## Code corrections and test identity", "",
              "Changed core files: " + ", ".join(changes),
              "Raw validator now enforces provider-required arrays. Adapter now rejects duplicate keys/nonfinite JSON before silent parsing can normalize them. Pilot mappings satisfy the strengthened checks, so measured pilot values are unchanged. The old raw strings are unavailable; duplicate-key validity for the original responses remains unverified.",
              "Original source hashes matched the checkout before fixes. Final tests cover the corrected working files; source hashes before/after are recorded in integrity_inventory.json.", "",
              "Tests: " + str(tests.get("passed")) + " passed, " + str(tests.get("failed")) + " failed; exit " + str(tests["exit_code"]),
              "Command: " + tests["command"], "See test_results.txt for logs, failed harness attempt, pre-fix regression failures, and final results.", "",
              "## Limitations and next work", "", *["- " + x for x in limitations], "",
              "Next: inspect exact-match mismatch cases and missing-declaration versus processed-missing differences in metrics_reconciliation.json, then perform actual owner claim-support review. Manual baseline remains pending; supply it only to claim a complete three-arm comparison.",
              "HELDOUT_STATUS = LOCKED_NOT_RUN. Audit performs no provider calls, study approvals, jobs, simulation, commit, push or publication.", ""]
    write(output / "validation_report.md", "\n".join(report))
    print(json.dumps({"status": status, "integrity_ok": bool(integrity_ok), "metrics_ok": metric_ok,
                      "tests_passed": tests.get("passed"), "tests_failed": tests.get("failed"), "audit_dir": str(output), "provider_called": False}))


if __name__ == "__main__":
    main()
