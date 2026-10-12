"""Offline, separately labeled scoring; never routes Codex output to manual_template."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from importlib.metadata import version
from pathlib import Path

from jsonschema import Draft202012Validator
from drosophila_pd.ai_v2 import comparison

ROOT = Path(__file__).resolve().parents[1]
LABEL = "AI_ASSISTED_TEMPLATE_REFERENCE_EXPOSED"
CODEX = "codex_ai_assisted_template"


def read(path):
    return json.loads(comparison.safe_path(Path(path)).read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_entries(entries):
    for entry in entries:
        path = comparison.safe_path(ROOT / entry["path"])
        if sha(path) != entry["sha256"]:
            raise ValueError(f"hash mismatch: {entry['path']}")


def score_content(cases, rows):
    """Same field equality and missing-set counts as score_comparison; no repairs."""
    cases = [c for c in cases if c.get("category") != "no_lexical_evidence_probe"]
    ids = [r["case_id"] for r in rows]
    if len(ids) != len(set(ids)) or set(ids) != {c["case_id"] for c in cases}:
        raise ValueError("rows must exactly match unique extraction case IDs")
    by_id = {r["case_id"]: r for r in rows}
    correct = total = present_correct = present_total = tp = fp = fn = completed = 0
    details = []
    for case in cases:
        row = by_id[case["case_id"]]
        valid = row["status"] in comparison.VALID
        completed += row["status"] == "COMPLETED"
        checks = []
        for field in case["required_fields"]:
            gold = case["gold_fields"][field]
            actual = row["fields"].get(field)
            match = valid and actual == gold
            correct += match
            total += 1
            if gold is not None:
                present_total += 1
                present_correct += match
            checks.append({"field": field, "output_present": field in row["fields"],
                           "output_value": actual, "frozen_reference_value": gold,
                           "exact_match": match})
        expected = set(case["gold_missing_fields"])
        predicted = set(row["missing_fields"]) if valid else set()
        case_tp, case_fp, case_fn = len(expected & predicted), len(predicted - expected), len(expected - predicted)
        tp += case_tp
        fp += case_fp
        fn += case_fn
        details.append({"case_id": case["case_id"], "status": row["status"],
                        "input_sha256": comparison.digest(case["protocol_text"].encode()),
                        "field_checks": checks, "field_errors": [c for c in checks if not c["exact_match"]],
                        "missing_fields": {"output": sorted(predicted), "reference": sorted(expected),
                                           "tp": case_tp, "fp": case_fp, "fn": case_fn}})
    not_measured = all(r["status"] == "NOT_RUN" for r in rows)
    return {
        "field_exact": {"correct": correct, "denominator": total,
                        "accuracy": correct / total if total and not not_measured else None,
                        "non_null_correct": present_correct, "non_null_denominator": present_total,
                        "non_null_accuracy": present_correct / present_total if present_total and not not_measured else None},
        "missing_fields": {"tp": tp, "fp": fp, "fn": fn,
                           "precision": tp / (tp + fp) if tp + fp and not not_measured else None,
                           "recall": tp / (tp + fn) if tp + fn and not not_measured else None,
                           "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn and not not_measured else None},
        "completion": {"count": completed, "denominator": len(cases),
                       "rate": completed / len(cases) if cases else None},
    }, details


def task_na(reason):
    return {"status": "N/A", "value": None, "reason": reason}


def load_codex(folder, inputs):
    inventory = read(folder / "source_hash_inventory.json")
    verify_entries(inventory["source_and_preserved_hashes"] + inventory["artifacts"])
    provenance = read(folder / "provenance_manifest_v1.json")
    worksheet = read(folder / "ai_assisted_template_worksheet_v1.json")
    if (provenance["label"] != LABEL or provenance["generator"] != "Codex"
            or provenance["baseline_is_manual"] or provenance["owner_review_complete"]
            or provenance["provider_called"] or provenance["retrieval_performed"]
            or worksheet["schema_version"] != "ai-v2-ai-assisted-template-1"
            or worksheet["partition"] != "DEVELOPMENT"):
        raise ValueError("Codex provenance/schema identity mismatch")
    for key in ("corpus_sha256", "rubric_sha256"):
        if worksheet[key] != inputs[key]:
            raise ValueError(f"Codex {key} mismatch")
    cases = {c["case_id"]: c for c in inputs["rubric"]["cases"] if c.get("category") != "no_lexical_evidence_probe"}
    if len(cases) != 11:
        raise ValueError("expected exactly 11 frozen extraction cases")
    ids = [c["case_id"] for c in worksheet["cases"]]
    if len(ids) != 11 or len(set(ids)) != 11 or set(ids) != set(cases):
        raise ValueError("Codex must contain exactly the 11 extraction IDs")
    policy = read(Path(inputs["frozen_dir"]) / "comparison_policy.json")
    schema = policy["response_format"]["json_schema"]["schema"]
    if read(folder / "frozen_response_schema.json") != schema:
        raise ValueError("Codex schema snapshot differs from frozen schema")
    validator = Draft202012Validator(schema)
    saved = [json.loads(line) for line in (folder / "outputs.jsonl").read_text(encoding="utf-8").splitlines()]
    if len(saved) != 11:
        raise ValueError("wrong output inventory size")
    rows, schema_results = [], []
    for item, output_record in zip(worksheet["cases"], saved, strict=True):
        case_id = item["case_id"]
        if item["protocol_text"] != cases[case_id]["protocol_text"]:
            raise ValueError(f"protocol input drift: {case_id}")
        output = {**item["fields"], "missing_fields": item["missing_fields"], "citations": item["citations"]}
        if output_record != {"case_id": case_id, "output": output}:
            raise ValueError(f"worksheet/output mismatch: {case_id}")
        errors = [e.message for e in validator.iter_errors(output)]
        contract_valid = comparison.raw_output_schema_valid(output)
        schema_results.append({"case_id": case_id, "frozen_json_schema_valid": not errors,
                               "comparison_raw_contract_valid": contract_valid, "errors": errors})
        rows.append({"case_id": case_id, "fields": item["fields"], "missing_fields": item["missing_fields"],
                     "status": "COMPLETED", "input_sha256": comparison.digest(item["protocol_text"].encode())})
    return rows, schema_results


def metric_parity(inputs, records, config, output_hash, original):
    current = comparison.score_comparison(inputs, records, config, output_hash)
    parity = {}
    details = {}
    for branch, numerator, tp, fn in (("llm_no_retrieval", 53, 6, 2), ("llm_rag", 54, 7, 1)):
        actual = next(s for s in current["systems"] if s["system_id"] == branch)
        saved = next(s for s in original["systems"] if s["system_id"] == branch)
        selected = [r for r in records if r["system_id"] == branch and r["case_id"] in current["protocol_extraction_case_ids"]]
        independent, case_details = score_content(inputs["rubric"]["cases"], selected)
        checks = {key: actual[key] == saved[key] for key in ("field_exact", "missing_fields", "schema_validity", "completion_rate")}
        checks["separate_field_scorer"] = independent["field_exact"] == actual["field_exact"]
        checks["separate_missing_scorer"] = independent["missing_fields"] == actual["missing_fields"]
        checks["expected_counts"] = (actual["field_exact"]["correct"] == numerator
            and actual["field_exact"]["denominator"] == 57
            and actual["missing_fields"]["tp"] == tp and actual["missing_fields"]["fp"] == 0
            and actual["missing_fields"]["fn"] == fn
            and math.isclose(actual["missing_fields"]["f1"], 2*tp/(2*tp+fn), abs_tol=1e-12))
        parity[branch] = {"checks": checks, "pass": all(checks.values())}
        details[branch] = case_details
    return all(p["pass"] for p in parity.values()), parity, details


def render(metrics, details):
    systems = metrics["systems"]
    header = "| Metric | Gemini no-retrieval — original | Gemini RAG — original | Codex AI-assisted — reference-exposed |"
    def cells(values):
        return "| " + " | ".join(values) + " |"
    def exact(s):
        m=s["field_exact"]
        return f"{m['correct']}/{m['denominator']} ({m['accuracy']:.2%})"
    lines = ["# Separate offline synthetic comparison", "", header, "|---|---|---|---|",
             cells(["Field exact"]+[exact(s) for s in systems]),
             cells(["Missing TP / FP / FN"]+[f"{s['missing_fields']['tp']} / {s['missing_fields']['fp']} / {s['missing_fields']['fn']}" for s in systems]),
             cells(["Missing precision / recall / F1"]+[" / ".join(f"{s['missing_fields'][k]:.4f}" for k in ("precision","recall","f1")) for s in systems]),
             cells(["Schema-valid response objects"]+[f"{s['schema_validity']['count']}/11" for s in systems]),
             cells(["Completion"]+[f"{s['completion']['count']}/11" for s in systems]), "",
             "## Scoring identity and parity", "", f"Commit: `{metrics['scoring_identity']['commit']}`. Dirty: `{metrics['scoring_identity']['dirty']}`.",
             "Current comparison.score_comparison reproduced both original field/missing metrics, completion and stored schema aggregates. The separate field-counting helper also matched both arms. Metric parity on these artifacts does not establish code identity. Current and run-bound code hashes are recorded in source_code_hash_inventory.json.", "",
             "Field scoring uses Python exact equality for each frozen required field, including null golds. An omitted field is read as None; nested context/control fields are each one composite field. Missing detection uses set intersections/differences, micro-aggregated TP/FP/FN; F1=2TP/(2TP+FP+FN). PARTIAL credit is not used in this exact-match metric.", "",
             "Gemini field and missing scores use original processed records, never the offline replay. Gemini schema figures reproduce stored raw-parsed/processed validity flags; they are not new checks of original HTTP bytes. Codex schema is validated on the unchanged saved JSON objects with the frozen JSON Schema and current raw contract; no sanitization or Workbench draft processing was performed. Codex processed-draft schema is N/A.", "",
             "## Field-level mismatches", "", "| Branch | Case | Field | Output value | Frozen reference value |", "|---|---|---|---|---|"]
    for branch, cases in details.items():
        for case in cases:
            for err in case["field_errors"]:
                vals=[branch,case["case_id"],err["field"],json.dumps(err["output_value"],ensure_ascii=False),json.dumps(err["frozen_reference_value"],ensure_ascii=False)]
                lines.append(cells([v.replace("|","\\|").replace("\n"," ") for v in vals]))
    lines += ["", "Codex case 003 preserves sex and the literal not-specified feeding_state note; frozen reference contains sex only. This yields one context exact-match mismatch. Neither output nor gold was changed after scoring; this is not a conclusion that the note is a known biological state.", "",
              "## Diagnostics and applicability", "", "Case 012 is the separate lexical no-hit diagnostic, not one of the 11 extraction cases. Original Gemini no-retrieval called the provider; original RAG abstained without a provider call. Codex has no diagnostic answer.",
              "Codex Recall@5, retrieval Precision@5 and citation precision are N/A: this arm performed no retrieval/citation task. Generation time, human completion time and cost are NOT_MEASURED. Missing observations are not zero-valued metrics.", "",
              "## Limits and preserved state", "", "Synthetic fixtures, 11 extraction cases. Fields are dependent within cases, not independent statistical samples; no significance test or field-level confidence interval is used. Codex has reference exposure, a different generator/model and a different output-generation workflow. It is neither manual nor a rule-based baseline; these results do not establish RAG/Codex superiority or understanding of biological protocols.",
              "Previous owner A/B claim-support review applies only to the two Gemini arms. Codex claim-support is NOT_REVIEWED; no labels were transferred. Manual remains PENDING/NOT_RUN, original comparison_complete remains false, and owner review is not marked complete. No provider calls, held-out reads, simulation, frozen changes, commits or pushes occurred."]
    return "\n".join(lines)+"\n"


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--input-dir",type=Path,required=True)
    parser.add_argument("--run-dir",type=Path,required=True)
    parser.add_argument("--frozen-dir",type=Path,required=True)
    parser.add_argument("--output-dir",type=Path,required=True)
    args=parser.parse_args()
    args.output_dir=comparison.safe_path(args.output_dir)
    if args.output_dir.exists():
        raise ValueError("output directory already exists; use a new version")
    frozen=comparison.safe_path(args.frozen_dir)
    freeze=read(frozen/"freeze_inventory.json")
    for name,h in freeze["artifact_sha256"].items():
        path=comparison.safe_path(frozen/name)
        if not path.is_relative_to(frozen) or sha(path)!=h:
            raise ValueError(f"frozen hash mismatch: {name}")
    inputs=comparison.prepare_inputs(frozen/"protocol_development_corpus_draft.jsonl",frozen/"reference_owner_reviewed.json",frozen/"corpus.manifest.json",generation=False)
    inputs["frozen_dir"]=str(frozen)
    codex,schemas=load_codex(args.input_dir,inputs)
    config,records,h=comparison.verify_run(args.run_dir,inputs)
    original=read(args.run_dir/"metrics.json")
    passed,parity,details=metric_parity(inputs,records,config,h,original)
    if not passed:
        raise ValueError("metric parity failed; no joint table created: "+json.dumps(parity))
    codex_metrics,details[CODEX]=score_content(inputs["rubric"]["cases"],codex)
    schema_count=sum(s["frozen_json_schema_valid"] and s["comparison_raw_contract_valid"] for s in schemas)
    codex_metrics.update(system_id=CODEX,label=LABEL,generator="Codex",claim_support="NOT_REVIEWED",
                         schema_validity={"count":schema_count,"denominator":11,"rate":schema_count/11,"checks":schemas,
                                          "processed_draft":task_na("no post-processing or Workbench draft created")},
                         recall_at_5=task_na("no retrieval task"),retrieval_precision_at_5=task_na("no retrieval task"),
                         citation_precision=task_na("no citation task"),generation_time="NOT_MEASURED",human_completion_time="NOT_MEASURED",cost="NOT_MEASURED")
    systems=[]
    for branch in ("llm_no_retrieval","llm_rag"):
        s=next(x for x in original["systems"] if x["system_id"]==branch)
        systems.append({"system_id":branch,"source":"ORIGINAL_RUN_PROCESSED_FIELDS",
                        "field_exact":s["field_exact"],"missing_fields":s["missing_fields"],
                        "raw_model_missing_declaration":s["raw_missing_declaration"],
                        "completion":{"count":s["status_counts"].get("COMPLETED",0),"denominator":11,"rate":s["completion_rate"]},
                        "schema_validity":{"count":s["schema_validity"]["raw_output_schema"]["valid_count"],"denominator":11,"rate":s["schema_validity"]["raw_output_schema"]["valid_rate_per_case"],"original_raw_parsed_and_processed":s["schema_validity"]}})
    systems.append(codex_metrics)
    commit=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()
    dirty=subprocess.check_output(["git","status","--porcelain=v1","--untracked-files=normal"],cwd=ROOT,text=True)
    code=[]
    for module in list(sys.modules.values()):
        p=getattr(module,"__file__",None)
        if p and getattr(module,"__name__","").startswith("drosophila_pd") and Path(p).resolve().is_relative_to(ROOT):
            code.append({"path":Path(p).resolve().relative_to(ROOT).as_posix(),"sha256":sha(p)})
    code.append({"path":Path(__file__).relative_to(ROOT).as_posix(),"sha256":sha(__file__)})
    identity={"commit":commit,"dirty":bool(dirty.strip()),"porcelain_status":dirty.splitlines(),
              "python":sys.version,"jsonschema_version":version("jsonschema"),"scorer":"score_content + comparison.score_comparison (parity)",
              "run_bound_code_sha256":config.get("code_sha256"),"current_loaded_repo_code_sha256":code}
    metrics={"schema_version":"ai-assisted-offline-comparison-1","created_at":datetime.now(timezone(timedelta(hours=7))).isoformat(),
             "status":"OFFLINE_SYNTHETIC_COMPARISON_PARITY_PASS","case_count":11,"synthetic_fixture":True,
             "scoring_identity":identity,"parity":parity,"systems":systems,
             "corpus_sha256":inputs["corpus_sha256"],"rubric_sha256":inputs["rubric_sha256"],
             "original_comparison_complete":original["comparison_complete"],"manual_baseline":"PENDING_NOT_RUN",
             "owner_review_complete_changed":False,"independent_review_claim":False,
             "diagnostic_case_012":{"original":original["lexical_no_hit_diagnostics"],"codex_answer":"NOT_GENERATED"},
             "heldout_status":"LOCKED_NOT_RUN","provider_called_this_step":False}
    if original["comparison_complete"] or any(r["status"]!="NOT_RUN" for r in records if r["system_id"]=="manual_template"):
        raise ValueError("unexpected manual/original completion state")
    source_paths=list(args.input_dir.iterdir())+list(frozen.iterdir())+list(args.run_dir.iterdir())
    source_hashes=[{"path":p.resolve().relative_to(ROOT).as_posix(),"sha256":sha(p)} for p in source_paths if p.is_file()]
    args.output_dir.mkdir(parents=True,exist_ok=False)
    def write(name,value):
        with (args.output_dir/name).open("x",encoding="utf-8",newline="\n") as handle:
            handle.write(value if isinstance(value,str) else json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+"\n")
    write("metrics.json",metrics)
    write("case_level_reconciliation.json",details)
    write("report.md",render(metrics,details))
    verify_entries(source_hashes)
    write("source_code_hash_inventory.json",{"sources":source_hashes,"scoring_identity":identity,
        "result_artifacts":[{"path":p.resolve().relative_to(ROOT).as_posix(),"sha256":sha(p)} for p in sorted(args.output_dir.iterdir())],
        "inventory_self_hash_excluded":True,"source_preservation_verified":True})
    print(json.dumps({"status":metrics["status"],"result_dir":str(args.output_dir),"codex_field_exact":codex_metrics["field_exact"],
                      "codex_missing_fields":codex_metrics["missing_fields"],"codex_schema_valid_count":schema_count},indent=2))


if __name__=="__main__":
    main()
