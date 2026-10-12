"""Create a local-only synthesis of the owner A/B review for the synthetic pilot.

This script reads only the explicitly supplied owner-review record,
reconciliation, frozen development package, original run, and offline replay.
It never calls a provider or reads held-out material. Output is created in a
new directory and existing output is never overwritten.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BRANCHES = ("llm_no_retrieval", "llm_rag")
AXIS_A = ("SUPPORTED", "PARTIAL", "UNSUPPORTED")
AXIS_B = ("SUPPORTED", "PARTIAL", "UNSUPPORTED", "N/A")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rate(count: int, denominator: int) -> dict[str, Any]:
    return {"count": count, "denominator": denominator,
            "fraction": count / denominator if denominator else None,
            "percent": 100 * count / denominator if denominator else None}


def reconcile_record(record: dict[str, Any]) -> dict[str, Any]:
    inventory = record["original_claim_units"]
    decisions = record["owner_confirmed_decisions"]
    denominator = record["denominator_rule"]
    includes = denominator["includes_owner_approved"]
    exclusions = denominator["exclusions_owner_approved"]

    inventory_ids = [row["claim_id"] for row in inventory]
    decision_ids = [row["claim_id"] for row in decisions]
    if len(inventory_ids) != len(set(inventory_ids)):
        raise ValueError("duplicate IDs in original inventory")
    if len(decision_ids) != len(set(decision_ids)):
        raise ValueError("duplicate IDs in owner decisions")
    by_id = {row["claim_id"]: row for row in decisions}
    inventory_set = set(inventory_ids)
    if set(decision_ids) != inventory_set:
        raise ValueError("owner decision IDs do not exactly match original inventory")
    include_ids = [row["claim_id"] for row in includes]
    exclude_ids = [row["claim_id"] for row in exclusions]
    if len(include_ids) != len(set(include_ids)) or len(exclude_ids) != len(set(exclude_ids)):
        raise ValueError("duplicate ID in include/exclude index")
    expected_include = {key for key, row in by_id.items()
                        if row.get("denominator_classification") == "INCLUDE_CONTENT_SUPPORT"}
    expected_exclude = {key for key, row in by_id.items()
                        if row.get("denominator_classification") == "EXCLUDE_CONTENT_SUPPORT_KEEP_INVENTORY"}
    if set(include_ids) != expected_include:
        raise ValueError("secondary INCLUDE index differs from per-ID owner decisions")
    if set(exclude_ids) != expected_exclude:
        raise ValueError("exclusion index differs from per-ID owner decisions")
    if set(include_ids) & set(exclude_ids) or set(include_ids) | set(exclude_ids) != inventory_set:
        raise ValueError("include/exclude sets do not partition the original inventory")
    if record.get("unreviewed_claim_ids"):
        raise ValueError("pending claim IDs remain")

    included = set(include_ids)
    excluded = set(exclude_ids)
    all_counts: dict[str, Any] = {}
    included_counts: dict[str, Any] = {}
    fidelity: dict[str, Any] = {}
    for branch in BRANCHES:
        all_rows = [by_id[key] for key in inventory_set if by_id[key]["branch"] == branch]
        inc_rows = [by_id[key] for key in included if by_id[key]["branch"] == branch]
        a_counts = Counter(row["axis_a"] for row in inc_rows)
        b_all = Counter(row["axis_b"] for row in all_rows)
        b_inc = Counter(row["axis_b"] for row in inc_rows)
        if set(a_counts) - set(AXIS_A) or set(b_all) - set(AXIS_B) or set(b_inc) - set(AXIS_B):
            raise ValueError(f"unexpected A/B label in {branch}")
        fidelity[branch] = {
            "denominator": len(inc_rows),
            "counts": {label: a_counts[label] for label in AXIS_A},
            "rates": {label: rate(a_counts[label], len(inc_rows)) for label in AXIS_A},
        }
        all_counts[branch] = {"denominator": len(all_rows),
                              "counts": {label: b_all[label] for label in AXIS_B}}
        included_counts[branch] = {"denominator": len(inc_rows),
                                   "counts": {label: b_inc[label] for label in AXIS_B}}

    unresolved = [row for row in decisions if row.get("critical_classification") == "UNRESOLVED"]
    if len(unresolved) != record["progress"]["severity_unresolved_units"]:
        raise ValueError("severity-unresolved count differs from progress record")
    omissions = record["owner_confirmed_omission_diagnostics"]
    if len(omissions) != record["progress"]["omission_diagnostics_severity_unresolved"]:
        raise ValueError("omission-diagnostic count differs from progress record")
    return {
        "inventory_total": len(inventory_ids), "inventory_unique": len(inventory_set),
        "decision_count": len(decisions), "include_count": len(included),
        "exclude_count": len(excluded), "pending_count": len(record["unreviewed_claim_ids"]),
        "include_ids": sorted(included), "exclude_ids": sorted(excluded),
        "fidelity_axis_a_included": fidelity,
        "axis_b_all_reviewed_inventory": all_counts,
        "axis_b_included_only": included_counts,
        "unresolved_claim_severity": [{key: row.get(key) for key in (
            "claim_id", "case_id", "branch", "field_path", "axis_a", "axis_b",
            "denominator_classification", "critical_classification",
            "extraction_error_description", "linked_review_note")}
            for row in unresolved],
        "unresolved_omission_diagnostics": omissions,
    }


def check_corrections(record: dict[str, Any], review_dir: Path) -> list[dict[str, Any]]:
    checked = []
    for item in record["record_correction_history"]:
        result = {"correction_id": item["correction_id"],
                  "recorded_at": item["recorded_at"], "status": "CHECKED"}
        if item["correction_id"] == "INVENTORY_WORDING_BATCH_016_CASE_002_V1":
            snapshot = ROOT / item["snapshot_path"]
            corrected = ROOT / item["target_note"]
            if sha256(snapshot) != item["presented_batch_hash_preserved"]:
                raise ValueError("batch-016 preserved snapshot hash mismatch")
            if sha256(snapshot) != item["prior_note_sha256"]:
                raise ValueError("batch-016 prior note hash mismatch")
            if sha256(corrected) != item["corrected_note_sha256"]:
                raise ValueError("batch-016 corrected note hash mismatch")
            result["verified_files"] = [
                {"path": item["snapshot_path"], "sha256": sha256(snapshot)},
                {"path": item["target_note"], "sha256": sha256(corrected)},
            ]
        elif item["correction_id"] == "OWNER_INCLUDE_INDEX_RECONCILIATION_20261010_V1":
            snapshot = ROOT / item["prior_record_snapshot"]
            old = read_json(snapshot)
            old_includes = old["denominator_rule"]["includes_owner_approved"]
            old_owner_includes = [d for d in old["owner_confirmed_decisions"]
                                  if d.get("denominator_classification") == "INCLUDE_CONTENT_SUPPORT"]
            if sha256(snapshot) != "698ecbb83bfb0017c66aa3b715ba580a7ba4c8c053eae3ea3b377339b7226701":
                raise ValueError("pre-batch-017 snapshot hash mismatch")
            if len(old_includes) != item["prior_include_index_entries"]:
                raise ValueError("recorded prior INCLUDE index count mismatch")
            if len(old_owner_includes) != item["owner_decision_include_count_before_batch_017"]:
                raise ValueError("recorded pre-batch-017 owner INCLUDE count mismatch")
            if len(record["denominator_rule"]["includes_owner_approved"]) != item["reconciled_include_index_entries"]:
                raise ValueError("reconciled INCLUDE index count mismatch")
            if item["owner_decisions_changed"] or not item["no_new_owner_decision_created_by_this_correction"]:
                raise ValueError("correction history claims owner-decision changes")
            result["verified_files"] = [{"path": item["prior_record_snapshot"], "sha256": sha256(snapshot)}]
            result["counts"] = {"old_index": len(old_includes),
                                 "old_owner_include_decisions": len(old_owner_includes),
                                 "new_index": len(record["denominator_rule"]["includes_owner_approved"]),
                                 "owner_decisions_changed": False}
        else:
            raise ValueError(f"unrecognized correction entry: {item['correction_id']}")
        checked.append(result)
    return checked


def summarize_run(metrics: dict[str, Any]) -> dict[str, Any]:
    arms = {}
    for row in metrics["systems"]:
        arm = row["system_id"]
        arms[arm] = {
            "status_counts": row["status_counts"],
            "field_exact": row["field_exact"],
            "workflow_missing_fields": row["missing_fields"],
            "raw_parsed_schema": row["schema_validity"]["raw_output_schema"],
            "processed_draft_schema": row["schema_validity"]["processed_draft_schema"],
            "latency": row["latency"],
            "retrieval": row["retrieval"],
            "citations": row["citations"],
        }
    return {"status": metrics["status"], "comparison_complete": metrics["comparison_complete"],
            "protocol_extraction_case_count": metrics["case_count"],
            "diagnostic_case_count": metrics["diagnostic_case_count"],
            "artifact_case_count": metrics["artifact_case_count"],
            "heldout_status": metrics["heldout_status"], "arms": arms,
            "case_012_lexical_no_hit": metrics["lexical_no_hit_diagnostics"]}


def summarize_replay(data: dict[str, Any]) -> dict[str, Any]:
    arms = {}
    for arm, row in data["metrics"].items():
        arms[arm] = {
            "field_exact": row["field_exact"],
            "workflow_missing_fields": row["workflow_missing_fields"],
            "model_declared_missing_fields": row["model_declared_missing_fields"],
            "schema_validity": row["schema_validity"],
            "status_counts": row["status_counts"],
            "citations": row["citations"],
            "retrieval": row["retrieval"],
        }
    return {"label": data["label"],
            "does_not_replace_frozen_v2_metrics": data["does_not_replace_frozen_v2_metrics"],
            "post_hoc_diagnostic_not_independent_or_new_gemini_run": data[
                "post_hoc_diagnostic_not_independent_or_new_gemini_run"],
            "heldout_status": data["heldout_status"], "arms": arms,
            "case_012_lexical_no_hit": data["lexical_no_hit_diagnostics"]}


def build(output_dir: Path, review_dir: Path, run_dir: Path,
          replay_dir: Path, packet_dir: Path, frozen_dir: Path) -> None:
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite existing report directory: {output_dir}")
    record_path = review_dir / "owner_review_record.json"
    reconciliation_path = review_dir / "reconciliation_owner_ab_20261010.md"
    record = read_json(record_path)
    reconciliation = reconciliation_path.read_text(encoding="utf-8")
    counts = reconcile_record(record)
    if counts["inventory_total"] != 105 or counts["include_count"] != 102 or counts["exclude_count"] != 3 or counts["pending_count"] != 0:
        raise ValueError("owner A/B inventory differs from requested 105/102/3/0")
    if counts["fidelity_axis_a_included"]["llm_no_retrieval"]["denominator"] != 52 or counts["fidelity_axis_a_included"]["llm_rag"]["denominator"] != 50:
        raise ValueError("included A-axis denominators differ from expected 52/50")
    if "PASS for the requested offline inventory/A-B reconciliation" not in reconciliation:
        raise ValueError("reconciliation report does not record PASS")

    corrections = check_corrections(record, review_dir)
    run_metrics = read_json(run_dir / "metrics.json")
    run_config = read_json(run_dir / "run_config.json")
    replay = read_json(replay_dir / "original_vs_replay_metrics.json")
    replay_outputs = replay_dir / "offline_replay_outputs.json"
    case_outputs = run_dir / "case_outputs.json"
    if sha256(case_outputs) != run_metrics["case_outputs_sha256"]:
        raise ValueError("original run outputs hash does not match metrics")
    if replay["original_case_outputs_sha256"] != run_metrics["case_outputs_sha256"]:
        raise ValueError("replay is not bound to original run output hash")
    if replay["original_metrics_sha256"] != sha256(run_dir / "metrics.json"):
        raise ValueError("replay original metrics hash mismatch")
    if run_metrics["comparison_complete"] is not False:
        raise ValueError("expected original comparison to remain incomplete")
    if run_metrics["heldout_status"] != "LOCKED_NOT_RUN":
        raise ValueError("unexpected held-out status")

    # Verify the package hashes recorded in the run configuration.
    package_checks = {
        "protocol_development_corpus_draft.jsonl": run_config["corpus_sha256"],
        "reference_owner_reviewed.json": run_config["rubric_sha256"],
        "corpus.manifest.json": run_config["manifest_sha256"],
        "manual_template_pending.json": run_config["manual_input_sha256"],
    }
    for name, expected in package_checks.items():
        if sha256(frozen_dir / name) != expected:
            raise ValueError(f"frozen package hash mismatch: {name}")

    bound = []
    for relpath, expected in record["artifact_bindings_sha256"].items():
        path = ROOT / relpath
        actual = sha256(path) if path.is_file() else None
        bound.append({"path": relpath, "expected_sha256": expected,
                      "actual_sha256": actual,
                      "status": "MATCH" if actual == expected else "DISCREPANCY"})
    mismatches = [row for row in bound if row["status"] != "MATCH"]
    if mismatches:
        raise ValueError(f"{len(mismatches)} registered artifact hash mismatch(es)")

    fixed_paths = [
        record_path, reconciliation_path,
        packet_dir / "claim_support_review_packet.json",
        packet_dir / "claim_support_review_packet.md",
        run_dir / "run_config.json", run_dir / "run_manifest.json", case_outputs,
        run_dir / "metrics.json", run_dir / "report.md", run_dir / "retrieval.jsonl",
        run_dir / "claim_review_template.json",
        replay_dir / "offline_replay_outputs.json",
        replay_dir / "original_vs_replay_metrics.json",
        replay_dir / "case_level_changes.md", replay_dir / "runtime_fix_report.md",
        review_dir / "batch_016_case_010_names_case_002_core_fields.md",
        review_dir / "batch_016_case_010_names_case_002_core_fields_before_inventory_correction.md",
        review_dir / "owner_review_record_before_batch_017_confirmation.json",
        frozen_dir / "protocol_development_corpus_draft.jsonl",
        frozen_dir / "reference_owner_reviewed.json", frozen_dir / "corpus.manifest.json",
        frozen_dir / "manual_template_pending.json", frozen_dir / "comparison_policy.json",
        frozen_dir / "owner_decision.json", frozen_dir / "freeze_inventory.json",
    ]
    sources = []
    for path in fixed_paths:
        if not path.is_file():
            raise FileNotFoundError(path)
        sources.append({"path": str(path.relative_to(ROOT)), "sha256": sha256(path)})

    recorded = datetime.now(timezone(timedelta(hours=7))).isoformat()
    summary = {
        "schema_version": "owner-reviewed-synthetic-pilot-summary-v1",
        "created_at": recorded,
        "scope": "offline synthesis; synthetic software-test protocol fixtures only",
        "review": {"status": record["status"], "owner_ab_review_complete": record["owner_ab_review_complete"],
                   "owner_review_complete": record["owner_review_complete"],
                   "reviewer_ids": record["owner_reviewer_ids"], "ai_assisted": True,
                   "independent_review_claim": record["independent_review_claim"],
                   "classification_post_hoc": True},
        "source_reconciliation": {key: counts[key] for key in (
            "inventory_total", "inventory_unique", "decision_count", "include_count",
            "exclude_count", "pending_count")},
        "axis_a_owner_reviewed_content_unit_fidelity": {
            "fixture": "synthetic", "classification_post_hoc": True,
            "denominators_are_content_units_not_independent_statistical_samples": True,
            "branches": counts["fidelity_axis_a_included"]},
        "axis_b_cited_guide_only_diagnostic": {
            "claim_to_citation_attribution": "UNRESOLVED_FOR_50_REVIEWED_RAG_UNITS",
            "not_citation_precision_or_error_rate": True,
            "all_reviewed_inventory": counts["axis_b_all_reviewed_inventory"],
            "included_content_units_only": counts["axis_b_included_only"]},
        "open_items": {"severity_unresolved_claim_units": counts["unresolved_claim_severity"],
                       "severity_unresolved_omission_diagnostics": counts["unresolved_omission_diagnostics"],
                       "critical_error_rate_computed": False,
                       "severity_status": "OPEN"},
        "original_gemini_run_metrics": summarize_run(run_metrics),
        "offline_replay_metrics": summarize_replay(replay),
        "comparison_complete": False,
        "manual_baseline": "PENDING / NOT_RUN for all 11 extraction cases",
        "biological_validity": "NOT_ESTABLISHED",
        "heldout_status": "LOCKED_NOT_RUN",
        "correction_history_checks": corrections,
        "registered_artifact_binding_count": len(bound),
    }
    inventory = {
        "schema_version": "owner-reviewed-pilot-source-hash-inventory-v1",
        "created_at": recorded,
        "primary_sources": sources,
        "owner_record_bound_artifacts": {"count": len(bound), "mismatch_count": 0,
                                          "entries": bound},
        "hash_algorithm": "SHA-256",
        "note": "All listed hashes are file-byte hashes. Registered owner-record bindings were independently recomputed.",
    }
    report = render_report(summary, counts, run_config, corrections)

    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "summary_metrics.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "source_hash_inventory.json").write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "pilot_owner_reviewed_summary.md").write_text(report, encoding="utf-8")
    print(json.dumps({"status": "SUMMARY_CREATED", "output_dir": str(output_dir),
                      "inventory": counts["inventory_total"], "included": counts["include_count"],
                      "excluded": counts["exclude_count"], "pending": counts["pending_count"],
                      "registered_hashes_checked": len(bound), "hash_mismatches": 0,
                      "provider_called": False, "heldout_read": False,
                      "simulation_run": False}, ensure_ascii=False))


def render_report(summary: dict[str, Any], counts: dict[str, Any],
                  run_config: dict[str, Any], corrections: list[dict[str, Any]]) -> str:
    fidelity = counts["fidelity_axis_a_included"]
    lines = [
        "# Synthetic pilot — owner-reviewed A/B summary", "",
        f"- Generated: {summary['created_at']} (UTC+07:00)",
        "- Review: OWNER_REVIEWED, AI_ASSISTED, one owner reviewer (`owner-le-tan-vi`), `independent_review_claim=false`.",
        "- Scope: synthetic software-test protocol fixtures; content classification was post hoc.",
        f"- A/B review: {counts['inventory_unique']}/{counts['inventory_total']} unique units; {counts['include_count']} included; {counts['exclude_count']} excluded from content denominator only; {counts['pending_count']} pending.",
        f"- Record state remains `{summary['review']['status']}`; `owner_review_complete={str(summary['review']['owner_review_complete']).lower()}` because severity/attribution remain open.", "",
        "## Source reconciliation", "",
        "Per-ID decision sets and secondary indices match exactly: 105 unique inventory IDs, 105 unique A/B decisions, 102 INCLUDE and 3 EXCLUDE, with 0 pending. The excluded IDs remain in the inventory: one missing-value placeholder and two RAG source-metadata units.",
        "The historical INCLUDE-index discrepancy was reconciled by correction `OWNER_INCLUDE_INDEX_RECONCILIATION_20261010_V1`: 33 index entries had been present versus 98 owner-confirmed INCLUDE decisions; 65 historical classifications were restored to the index and four batch-017 decisions added. It did not change any owner decision. The earlier batch-016 case-002 correction is wording-only; its prior/corrected note hashes and snapshot were checked.",
        f"Registered source-artifact bindings: {summary['registered_artifact_binding_count']} checked, 0 mismatches. See `source_hash_inventory.json` for exact hashes.", "",
        "## A — input fidelity", "",
        "Owner-reviewed content-unit fidelity on the synthetic fixture; post-hoc content classification. Denominators contain only included content assertions. PARTIAL remains separate from SUPPORTED.",
        "| Branch | Label | Count / denominator | Rate |", "|---|---|---:|---:|",
    ]
    for branch in BRANCHES:
        for label in AXIS_A:
            cell = fidelity[branch]["rates"][label]
            lines.append(f"| `{branch}` | {label} | {cell['count']}/{cell['denominator']} | {cell['percent']:.2f}% |")
    lines += [
        "", "These are descriptive counts of reviewed units nested within 11 cases, not independent statistical samples. No p-value, claim-level confidence interval, or superiority conclusion is calculated. The observed zero UNSUPPORTED RAG units does not establish that the system never hallucinates.",
        "", "## B — cited-guide-only support diagnostic", "",
        "B labels assess whether the cited guide text alone supports the reviewed value. They are not citation precision, citation-error rate, or hallucination rate. Citations are response-level; claim-to-citation attribution remains unresolved for 50 reviewed RAG units. No model citation intent was reconstructed.",
        "| Branch | Scope | Units | SUPPORTED | PARTIAL | UNSUPPORTED | N/A |", "|---|---|---:|---:|---:|---:|---:|",
    ]
    for branch in BRANCHES:
        for scope, table in (("all reviewed inventory", counts["axis_b_all_reviewed_inventory"]),
                             ("included content only", counts["axis_b_included_only"])):
            row = table[branch]
            c = row["counts"]
            lines.append(f"| `{branch}` | {scope} | {row['denominator']} | {c['SUPPORTED']} | {c['PARTIAL']} | {c['UNSUPPORTED']} | {c['N/A']} |")
    lines += ["", "## Unresolved severity and omissions", "",
              "Five claim-unit severity decisions remain UNRESOLVED; no critical-error rate is computed. Two case-011 rationale omissions remain separate diagnostics, each severity UNRESOLVED and adding no claim unit. The omission remains part of the composite `control_suggestions` mismatch; a supported scalar role does not make the full composite field correct.",
              "", "| Case | Branch | Field | A / B | Claim ID |", "|---|---|---|---|---|"]
    for row in counts["unresolved_claim_severity"]:
        lines.append(f"| {row['case_id']} | `{row['branch']}` | `{row['field_path']}` | {row['axis_a']} / {row['axis_b']} | `{row['claim_id']}` |")
    lines += ["", "Omission diagnostics:"]
    for row in counts["unresolved_omission_diagnostics"]:
        lines.append(f"- `{row['case_id']}` / `{row['branch']}` / `{row['field_path']}` — {row['diagnostic_type']}; severity `{row['severity']}`; composite mismatch preserved.")

    original = summary["original_gemini_run_metrics"]
    replay = summary["offline_replay_metrics"]
    lines += ["", "## Original Gemini run (11 extraction cases)", "",
              f"Run `{original['status']}`; `comparison_complete={str(original['comparison_complete']).lower()}`. The manual-template arm is NOT_RUN for all 11 cases, so there is no complete three-arm comparison.",
              "| Arm | Exact fields | Missing-fields F1 | Raw-parsed schema | Processed draft schema | Mean latency |", "|---|---:|---:|---:|---:|---:|"]
    for arm in ("manual_template", "llm_no_retrieval", "llm_rag"):
        row = original["arms"][arm]
        exact = row["field_exact"]
        if arm == "manual_template":
            exact_text, miss_text, latency = "NOT MEASURED", "NOT MEASURED", "N/A"
        else:
            exact_text = f"{exact['correct']}/{exact['denominator']} ({100*exact['accuracy']:.2f}%)"
            miss_text = f"{row['workflow_missing_fields']['f1']:.3f}"
            latency = f"{row['latency']['mean_seconds']:.3f}s"
        raw = row["raw_parsed_schema"]
        processed = row["processed_draft_schema"]
        raw_text = (f"{raw['valid_count']}/{raw['response_denominator']}" if raw['response_denominator'] else "N/A")
        processed_text = (f"{processed['valid_count']}/{processed['produced_denominator']}" if processed['produced_denominator'] else "N/A")
        lines.append(f"| `{arm}` | {exact_text} | {miss_text} | {raw_text} | {processed_text} | {latency} |")
    rag = original["arms"]["llm_rag"]
    lines += ["", f"RAG retrieval on the 11 extraction cases: Recall@5={rag['retrieval']['recall_at_5']:.3f}; gold-set Precision@5={rag['retrieval']['precision_at_5']:.3f} ({rag['retrieval']['precision_relevant_hit_numerator_sum']}/{rag['retrieval']['precision_returned_hit_denominator_sum']} matched/returned hits). Non-gold chunks are unjudged; this is not semantic citation support.",
              "Raw-parsed schema means validation of the stored parsed JSON mapping before Workbench processing; it is not the original HTTP body or exact raw JSON string. Processed schema is reported separately. Both LLM arms were valid 11/11 on each stored mapping/draft in this run.",
              "", "## Offline replay (separate from the Gemini run)", "",
              "The replay reprocesses saved outputs; it is post-processing, not a new Gemini call or model improvement. Original run artifacts and metrics remain unchanged.",
              "| Arm | Exact fields original → replay | Workflow missing F1 original → replay | Schema/status |", "|---|---:|---:|---|"]
    for arm in ("manual_template", "llm_no_retrieval", "llm_rag"):
        row = replay["arms"][arm]
        a, b = row["field_exact"]["original"], row["field_exact"]["replay"]
        m1, m2 = row["workflow_missing_fields"]["original"], row["workflow_missing_fields"]["replay"]
        exact_text = "NOT MEASURED" if a["accuracy"] is None else f"{a['correct']}/{a['denominator']} ({100*a['accuracy']:.2f}%) → {b['correct']}/{b['denominator']} ({100*b['accuracy']:.2f}%)"
        miss_text = "N/A" if m1["f1"] is None else f"{m1['f1']:.3f} → {m2['f1']:.3f}"
        raw0 = row["schema_validity"]["original"]["raw_output_schema"]
        raw1 = row["schema_validity"]["replay"]["raw_output_schema"]
        proc0 = row["schema_validity"]["original"]["processed_draft_schema"]
        proc1 = row["schema_validity"]["replay"]["processed_draft_schema"]
        schema_text = (f"raw {raw0['valid_count']}/{raw0['response_denominator']}→{raw1['valid_count']}/{raw1['response_denominator']}; "
                       f"draft {proc0['valid_count']}/{proc0['produced_denominator']}→{proc1['valid_count']}/{proc1['produced_denominator']}; "
                       f"status {row['status_counts']['original']}→{row['status_counts']['replay']}")
        lines.append(f"| `{arm}` | {exact_text} | {miss_text} | {schema_text} |")
    lines += ["", "Case 012 remains a separate lexical no-hit diagnostic, outside the 11-case extraction aggregate. In both original run and replay: no-retrieval called the provider with zero retrieved hits; RAG had zero hits, abstained, and did not call the provider; manual template was not run.",
              "", "## Limits and remaining work", "",
              "- The manual baseline is still PENDING/NOT_RUN; the three-arm comparison remains incomplete (`comparison_complete=false`). Complete and review the manual-template arm before claiming a full comparison.",
              "- The synthetic fixture does not demonstrate understanding of biological protocols or biological/wet-lab validity.",
              "- Severity and claim-to-citation attribution remain OPEN. No critical-error rate or citation-error rate is reported.",
              "- Held-out remains `LOCKED_NOT_RUN`; no held-out was read, and no provider or simulation was run for this summary.",
              "- Configured provider identity in the original run was `" + run_config["provider_id"] + "`, model `" + run_config["configured_model_id"] + "`; this summary only reads stored artifacts.",
              "", "Source hashes and all 66 owner-record artifact bindings are in `source_hash_inventory.json`.", ""]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-dir", type=Path, default=Path(".workbench/ai-v2-audits/step4-owner-claim-support-review-20261010-v1"))
    parser.add_argument("--run-dir", type=Path, default=Path(".workbench/ai-v2-comparisons/paired-20261009T131833878Z"))
    parser.add_argument("--replay-dir", type=Path, default=Path(".workbench/ai-v2-audits/offline-replay-postprocessing-20261009-v2"))
    parser.add_argument("--packet-dir", type=Path, default=Path(".workbench/ai-v2-audits/step2-field-claims-review-20261009-v10"))
    parser.add_argument("--frozen-dir", type=Path, default=Path(".workbench/evidence/owner_demo_protocol_frozen_v2"))
    parser.add_argument("--output-dir", type=Path, default=Path(".workbench/ai-v2-audits/pilot-owner-reviewed-summary-20261010-v1"))
    args = parser.parse_args()
    paths = [args.review_dir, args.run_dir, args.replay_dir, args.packet_dir, args.frozen_dir, args.output_dir]
    resolved = [p if p.is_absolute() else ROOT / p for p in paths]
    build(resolved[5], resolved[0], resolved[1], resolved[2], resolved[3], resolved[4])


if __name__ == "__main__":
    main()
