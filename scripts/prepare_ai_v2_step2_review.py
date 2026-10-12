"""Build a field-by-field and claim-support review packet from saved dev outputs."""
from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from drosophila_pd.ai_v2 import comparison as c

RUN = ROOT / ".workbench/ai-v2-comparisons/paired-20261009T131833878Z"
PACKAGE = ROOT / ".workbench/evidence/owner_demo_protocol_frozen_v2"
OUT = ROOT / ".workbench/ai-v2-audits/step2-field-claims-review-20261009-v10"
EXPECTED_OUTPUTS = "4383ec743ce99027f6b299bc78be40af7beba19b9da1ee23c17eef255f916b5b"
SYSTEMS = ("llm_no_retrieval", "llm_rag")


def dump(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pretty(value) -> str:
    if value is ABSENT:
        return "<ABSENT>"
    if value is None:
        return "null"
    if value == "":
        return '"" (empty string)'
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


class _Absent:
    pass


ABSENT = _Absent()


def field_value(mapping, key):
    return mapping[key] if isinstance(mapping, dict) and key in mapping else ABSENT


def protocol_locator(case_id: str, text: str) -> str:
    return f"reference_owner_reviewed.json#/cases/{case_id}/protocol_text (line 1-{len(text.splitlines())}); source: protocol_fixture_source.md"


def support_proposal(claim: str, protocol: str, excerpts: list[dict]) -> tuple[str, str]:
    """Literal traceability aid only; owner must assess meaning and truth."""
    norm_claim = " ".join(claim.casefold().split())
    sources = [("protocol input", protocol)] + [(e["corpus_locator"], e["text"]) for e in excerpts]
    matches = [locator for locator, text in sources if norm_claim and norm_claim in " ".join(text.casefold().split())]
    if matches:
        return "PROPOSED_DIRECT_TEXT_SUPPORT", "Exact text occurs in a provided source span: " + "; ".join(matches) + ". Check assertion context; this lexical match does not establish truth or semantic entailment."
    return "PROPOSED_UNVERIFIABLE_OR_PARAPHRASED", "No exact textual span was found in the protocol or retrieved excerpts. This lexical check cannot establish contradiction or semantic support; owner interpretation is needed."


def main():
    if OUT.exists():
        raise FileExistsError(f"Refusing to overwrite review packet: {OUT}")
    OUT.mkdir(parents=True)
    inputs = c.prepare_inputs(PACKAGE / "protocol_development_corpus_draft.jsonl",
                              PACKAGE / "reference_owner_reviewed.json", PACKAGE / "corpus.manifest.json")
    config, records, output_hash = c.verify_run(RUN, inputs)
    assert output_hash == EXPECTED_OUTPUTS, "case_outputs hash differs from Step 1 audit"
    assert config["synthetic_fixture"] is True and config["partition"] == "DEVELOPMENT"
    rubric = inputs["rubric"]
    cases = {x["case_id"]: x for x in rubric["cases"]}
    by_key = {(x["system_id"], x["case_id"]): x for x in records}
    assert len(records) == 36 and len(by_key) == 36
    extraction = [x for x in rubric["cases"] if x.get("category") != "no_lexical_evidence_probe"]
    diagnostic = [x for x in rubric["cases"] if x.get("category") == "no_lexical_evidence_probe"]
    assert len(extraction) == 11 and len(diagnostic) == 1

    corpus_file = PACKAGE / rubric["corpus_file"]
    chunk_lines = {}
    for line_no, line in enumerate(corpus_file.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            chunk = json.loads(line)
            chunk_lines[chunk["chunk_id"]] = {"line": line_no, **chunk}
    source_lines = (PACKAGE / rubric["source_document_file"]).read_text(encoding="utf-8").splitlines()
    source_text = "\n".join(source_lines)
    source_headings = {}
    current_heading = ""
    for line_no, line in enumerate(source_lines, 1):
        if line.startswith("## "):
            current_heading = line[3:].strip()
        source_headings.setdefault(current_heading, []).append({"line": line_no, "text": line})

    def located_evidence(items):
        located = []
        for item in items:
            chunk = chunk_lines.get(item.get("chunk_id"))
            if chunk is None or chunk["source_id"] != item.get("source_id"):
                raise ValueError(f"Retrieved evidence has no frozen corpus locator: {item.get('chunk_id')}")
            heading = item.get("citation", "").split(" — ", 1)[-1]
            if heading not in source_headings:
                raise ValueError(f"Evidence heading does not exist in source document: {heading}")
            if item["text"] not in source_text:
                raise ValueError(f"Evidence excerpt not found verbatim in source document: {item.get('chunk_id')}")
            located.append({**item,
                "corpus_locator": f"protocol_development_corpus_draft.jsonl line {chunk['line']} / chunk_id={chunk['chunk_id']}",
                "source_document_locator": f"protocol_fixture_source.md heading '{heading}'"})
        return located

    field_rows = []
    case_docs = []
    mismatch_by_system = {s: [] for s in SYSTEMS}
    mismatch_sets = {s: set() for s in SYSTEMS}
    postprocess_changes = []
    critical_candidates = []
    for case in extraction:
        cid, protocol = case["case_id"], case["protocol_text"]
        case_row = {"case_id": cid, "category": case.get("category"), "answerability": case.get("answerability"),
                    "protocol_text": protocol, "protocol_locator": protocol_locator(cid, protocol),
                    "gold_review_status": "EXISTING_FROZEN_OWNER_APPROVAL", "review_note": case.get("review_note"), "branches": {}}
        for system in SYSTEMS:
            record = by_key[system, cid]
            raw = record.get("raw_output")
            processed = (record.get("draft") or {}).get("proposed_fields", {})
            scored = record.get("fields", {})
            branch_field_rows = []
            for field in case["required_fields"]:
                gold = field_value(case.get("gold_fields", {}), field)
                raw_value = field_value(raw, field)
                processed_value = field_value(processed, field)
                score_value = field_value(scored, field)
                normalized_score = None if score_value is ABSENT else score_value
                same = normalized_score == (None if gold is ABSENT else gold)
                direct_support = case.get("field_support", {}).get(field)
                missing_why = case.get("missing_field_reasons", {}).get(field)
                if gold is ABSENT and (field not in case.get("gold_missing_fields", []) or not missing_why):
                    gold_review = "GOLD_REVIEW_REQUIRED"
                    gold_review_reason = "Required reference value is absent without an explicit missing-field reason."
                elif cid == "AI_PROTO_DEV_DRAFT_003" and field == "context":
                    gold_review = "OWNER_APPROVED_REFERENCE_HAS_INTERPRETIVE_EDGE"
                    gold_review_reason = "The protocol explicitly names feeding_state but its value says 'not specified beyond the fictional protocol'; the frozen rule says copy only explicit values. Gold retains sex=female and omits feeding_state. Existing owner approval is recorded; this note preserves the edge case for clarity, it does not revoke that decision."
                elif gold is None and (field not in case.get("gold_missing_fields", []) or not case.get("missing_field_reasons", {}).get(field)):
                    gold_review = "GOLD_REVIEW_REQUIRED"
                    gold_review_reason = "Gold is null without a matching missing-field declaration and source-based reason."
                elif gold is not ABSENT and gold is not None and not direct_support:
                    gold_review = "GOLD_REVIEW_REQUIRED"
                    gold_review_reason = "Non-null gold has no field-specific source locator in the frozen reference."
                else:
                    gold_review = "EXISTING_OWNER_APPROVED_SOURCE_TRACEABLE"
                    gold_review_reason = "Frozen rubric includes source support or an explicit missing-field reason; preserve its already recorded owner approval."
                row = {"case_id": cid, "branch": system, "field_name": field,
                       "reference_value": pretty(gold), "raw_parsed_value": pretty(raw_value),
                       "processed_value": pretty(processed_value), "evaluator_value": pretty(score_value),
                       "evaluator_normalized_value": pretty(normalized_score),
                       "scoring_normalization": "Evaluator reads record.fields; an absent key is treated as null for comparison. Values otherwise use exact Python equality; no semantic string normalization.",
                       "match_status": "MATCH" if same else "MISMATCH",
                       "protocol_locator": protocol_locator(cid, protocol),
                       "protocol_support_excerpt": direct_support or "No field-specific support string in frozen reference.",
                       "gold_missing_reason": missing_why,
                       "gold_review_status": gold_review,
                       "gold_review_reason": gold_review_reason,
                       "explanation": "Exact reference comparison only. A mismatch is not automatically a scientific or semantic error; owner should judge protocol support."}
                branch_field_rows.append(row)
                field_rows.append(row)
                if not same:
                    mismatch_by_system[system].append(row)
                    mismatch_sets[system].add((cid, field))
                if raw_value != processed_value:
                    postprocess_changes.append({"case_id": cid, "branch": system, "field_name": field,
                                                "raw_parsed_value": pretty(raw_value), "processed_value": pretty(processed_value),
                                                "evaluator_value": pretty(score_value), "scoring_effect": "Affects this field slot only if the evaluator value differs from reference; see field row."})
                if (field in case.get("gold_missing_fields", []) and score_value is not ABSENT
                        and score_value is not None and score_value != "" and score_value != []):
                    critical_candidates.append({"case_id": cid, "branch": system, "field_name": field,
                                                "candidate": pretty(score_value), "reason": "Runtime output supplies a non-empty value for a field reference marks missing; investigate as a potential unsupported protocol completion.",
                                                "owner_decision": "PENDING"})
                if (cid == "AI_PROTO_DEV_DRAFT_003" and field == "context" and not same
                        and isinstance(score_value, dict) and "specimen_context" in score_value):
                    critical_candidates.append({"case_id": cid, "branch": system, "field_name": "context/specimen_context",
                        "candidate": pretty(score_value["specimen_context"]),
                        "reason": "Protocol labels feeding_state as 'not specified'; output changes the key to specimen_context. Potential context-field substitution can change meaning even though the value words are copied.",
                        "owner_decision": "PENDING"})
            raw_missing = raw.get("missing_fields") if isinstance(raw, dict) else None
            runtime_missing = record.get("missing_fields")
            case_row["branches"][system] = {"status": record["status"], "provider_called": record.get("provider_called"),
                "fields": branch_field_rows, "model_declared_missing_fields": raw_missing,
                "runtime_computed_missing_fields": runtime_missing,
                "raw_vs_runtime_missing": {"model_only": sorted(set(raw_missing or []) - set(runtime_missing or [])),
                                            "runtime_only": sorted(set(runtime_missing or []) - set(raw_missing or [])),
                                            "same_as_sets": set(raw_missing or []) == set(runtime_missing or [])},
                "citation_pairs_model_raw_parsed": (raw or {}).get("citations", []) if isinstance(raw, dict) else None,
                "citations_after_runtime": record.get("citations", []),
                "retrieved_evidence": located_evidence(record.get("retrieved_evidence", [])),
                "raw_object_locator": f"case_outputs.json#/records[system_id={system},case_id={cid}]/raw_output",
                "processed_locator": f"case_outputs.json#/records[system_id={system},case_id={cid}]/draft/proposed_fields",
                "scored_locator": f"case_outputs.json#/records[system_id={system},case_id={cid}]/fields and /missing_fields"}
        case_docs.append(case_row)

    # Construct all scalar claims directly with the evaluator's stable IDs.
    template = c.read_json(RUN / "claim_review_template.json")
    template_by_key = {(x["system_id"], x["case_id"], x["claim_id"]): x for x in template["reviews"]}
    claims = []
    for system in SYSTEMS:
        for case in extraction:
            cid = case["case_id"]
            record = by_key[system, cid]
            units = c.claim_units(record)
            for unit in units:
                key = (system, cid, unit["claim_id"])
                source_review = template_by_key.get(key)
                if source_review is None:
                    raise ValueError(f"Claim missing from existing review template: {key}")
                citations_raw = (record.get("raw_output") or {}).get("citations", [])
                citations_runtime = record.get("citations", [])
                located_hits = located_evidence(record.get("retrieved_evidence", []))
                evidence_by_pair = {(e["source_id"], e["chunk_id"]): e for e in located_hits}
                cited_evidence = []
                for cite in citations_raw if isinstance(citations_raw, list) else []:
                    if isinstance(cite, dict):
                        ev = evidence_by_pair.get((cite.get("source_id"), cite.get("chunk_id")))
                        if ev:
                            cited_evidence.append(ev)
                proposal_a, why_a = support_proposal(unit["text"], case["protocol_text"], located_hits)
                citation_trace = ("RAG raw-parsed output contains source_id/chunk_id pairs; Workbench validates pairs against retrieved hits and adds corpus citation/locator metadata to accepted citations."
                    if system == "llm_rag" else "This no-retrieval output has no retrieved excerpts and an empty raw citation list; citation support is not applicable.")
                if system == "llm_no_retrieval":
                    proposal_b = "N/A_NO_RETRIEVAL"
                    why_b = "This branch supplied no retrieved evidence and raw citations are empty; citation support is not applicable, which is not a factual error label."
                elif not citations_raw:
                    proposal_b = "PROPOSED_UNVERIFIABLE_NO_CITATION"
                    why_b = "No model citation pair accompanies this response-level claim; there is no claim-linked citation to assess."
                elif any(" ".join(unit["text"].casefold().split()) in " ".join(e["text"].casefold().split()) for e in cited_evidence):
                    proposal_b = "PROPOSED_DIRECT_TEXT_MATCH"
                    why_b = "Claim text appears verbatim in at least one cited retrieved excerpt. This lexical match does not itself establish that the excerpt supports the claim in context."
                else:
                    proposal_b = "PROPOSED_REVIEW_REQUIRED"
                    why_b = "Citation pair exists at response level, but no exact claim-text span was found in its cited excerpts; semantic support needs owner judgment."
                claims.append({"claim_id": unit["claim_id"], "case_id": cid, "branch": system,
                    "claim": unit["text"], "field_path": unit["field_path"],
                    "source_locator": f"case_outputs.json#/records[system_id={system},case_id={cid}]/raw_output{unit['field_path']}",
                    "protocol_input": case["protocol_text"], "protocol_locator": protocol_locator(cid, case["protocol_text"]),
                    "response_level_raw_citation_pairs": citations_raw,
                    "runtime_citations": citations_runtime,
                    "citation_trace": citation_trace + " Pair identity comparison is included below.",
                    "raw_pairs_equal_runtime_pairs": sorted((x.get("source_id"), x.get("chunk_id")) for x in citations_raw if isinstance(x, dict)) == sorted((x.get("source_id"), x.get("chunk_id")) for x in citations_runtime if isinstance(x, dict)),
                    "retrieved_excerpts": located_hits,
                    "claim_linked_cited_excerpts": cited_evidence,
                    "proposal_axis_a_protocol_support": {"suggestion": proposal_a, "reason": why_a, "owner_decision": "PENDING"},
                    "proposal_axis_b_citation_support": {"suggestion": proposal_b, "reason": why_b, "owner_decision": "PENDING"},
                    "critical_error_candidate": any(x["case_id"] == cid and x["branch"] == system
                        and (unit["field_path"] == "/context/specimen_context" if x["field_name"] == "context/specimen_context"
                             else (unit["field_path"] == "/" + x["field_name"] or unit["field_path"].startswith("/" + x["field_name"] + "/")))
                        for x in critical_candidates),
                    "existing_review_template_locator": f"claim_review_template.json#/reviews[claim_id={unit['claim_id']}]",
                    "existing_evaluator_review_status": source_review["support_status"],
                    "owner_decision": {"axis_a": "PENDING", "axis_b": "N/A_NO_RETRIEVAL" if system == "llm_no_retrieval" else "PENDING",
                        "reviewer_ids": [], "reason": "No retrieval branch has no citation-support judgment to make." if system == "llm_no_retrieval" else ""}})
    expected_count = {"llm_no_retrieval": 52, "llm_rag": 53}
    counts = Counter(x["branch"] for x in claims)
    assert dict(counts) == expected_count, f"Unexpected claims by arm: {counts}"
    ids = [x["claim_id"] for x in claims]
    assert len(set(ids)) == len(ids) == 105, "claim IDs must be unique"
    assert len(template["reviews"]) == 105 and set(template_by_key) == {(x["branch"], x["case_id"], x["claim_id"]) for x in claims}
    for claim in claims:
        assert claim["existing_evaluator_review_status"] == "PENDING"
        assert claim["owner_decision"]["axis_a"] == "PENDING"
        assert claim["owner_decision"]["axis_b"] == ("N/A_NO_RETRIEVAL" if claim["branch"] == "llm_no_retrieval" else "PENDING")
        for ev in claim["retrieved_excerpts"]:
            assert (ev["source_id"], ev["chunk_id"]) in inputs["corpus_pairs"]
    claim_signature = lambda x: (x["case_id"], x["field_path"], x["claim"])
    claim_sets = {s: {claim_signature(x) for x in claims if x["branch"] == s} for s in SYSTEMS}
    claim_count_reconciliation = {"llm_no_retrieval": len(claim_sets["llm_no_retrieval"]),
        "llm_rag": len(claim_sets["llm_rag"]), "common_units": len(claim_sets["llm_no_retrieval"] & claim_sets["llm_rag"]),
        "no_retrieval_only": [list(x) for x in sorted(claim_sets["llm_no_retrieval"] - claim_sets["llm_rag"])],
        "rag_only": [list(x) for x in sorted(claim_sets["llm_rag"] - claim_sets["llm_no_retrieval"])],
        "explanation": "RAG case 011 adds two scalar strings under nested sources metadata; case 005 has one no-retrieval prediction absent in RAG; case 004 emits different hypothesis strings. claim_units recursively counts every non-empty scalar string, so the count is not independent scientific claims."}

    mismatch_union = mismatch_sets[SYSTEMS[0]] | mismatch_sets[SYSTEMS[1]]
    mismatch_intersection = mismatch_sets[SYSTEMS[0]] & mismatch_sets[SYSTEMS[1]]
    value_shapes = Counter()
    expected_types = {"context": dict, "candidate_suggestions": list, "control_suggestions": list}
    for row in field_rows:
        value = row["raw_parsed_value"]
        if value == "<ABSENT>":
            value_shapes["absent"] += 1
        elif value == "null":
            value_shapes["null"] += 1
        elif value == '"" (empty string)':
            value_shapes["empty_string"] += 1
        else:
            try:
                parsed = json.loads(value)
                expected = expected_types.get(row["field_name"], str)
                value_shapes["wrong_type"] += not isinstance(parsed, expected)
                value_shapes["nonempty_placeholder_missing"] += int(row["reference_value"] == "null" and isinstance(parsed, str) and parsed.casefold() == "missing")
            except (ValueError, TypeError):
                value_shapes["unparseable_display"] += 1
    for key in ("absent", "null", "empty_string", "wrong_type", "nonempty_placeholder_missing", "unparseable_display"):
        value_shapes.setdefault(key, 0)
    missing_diffs = []
    for case in case_docs:
        for system, branch in case["branches"].items():
            delta = branch["raw_vs_runtime_missing"]
            if delta["model_only"] or delta["runtime_only"]:
                missing_diffs.append({"case_id": case["case_id"], "branch": system,
                    "model_declared": branch["model_declared_missing_fields"],
                    "runtime_computed": branch["runtime_computed_missing_fields"], **delta})
    summary = {"status": "READY_FOR_OWNER_REVIEW_AI_ASSISTED", "run": str(RUN), "package": str(PACKAGE),
        "case_outputs_sha256": output_hash, "corpus_sha256": config["corpus_sha256"], "rubric_sha256": config["rubric_sha256"],
        "extraction_case_count": len(extraction), "diagnostic_case_count": len(diagnostic), "claim_count": len(claims),
        "claims_by_branch": dict(counts), "claim_count_reconciliation": claim_count_reconciliation,
        "field_row_count": len(field_rows), "field_mismatch_rows": len(mismatch_by_system[SYSTEMS[0]]) + len(mismatch_by_system[SYSTEMS[1]]),
        "field_mismatch_counts_by_branch": {s: len(mismatch_by_system[s]) for s in SYSTEMS},
        "gold_review_required_rows": sum(x["gold_review_status"] == "GOLD_REVIEW_REQUIRED" for x in field_rows),
        "raw_value_shape_counts": dict(value_shapes), "model_runtime_missing_set_delta_records": len(missing_diffs),
        "model_only_missing_labels": sum(len(x["model_only"]) for x in missing_diffs),
        "runtime_only_missing_labels": sum(len(x["runtime_only"]) for x in missing_diffs),
        "mismatch_unique_case_fields_union": len(mismatch_union), "mismatch_case_fields_both_branches": sorted([list(x) for x in mismatch_intersection]),
        "mismatch_only_no_retrieval": sorted([list(x) for x in mismatch_sets[SYSTEMS[0]] - mismatch_sets[SYSTEMS[1]]]),
        "mismatch_only_rag": sorted([list(x) for x in mismatch_sets[SYSTEMS[1]] - mismatch_sets[SYSTEMS[0]]]),
        "postprocessing_change_count": len(postprocess_changes), "critical_error_candidates": len(critical_candidates),
        "owner_review_complete": False, "provider_called": False, "heldout_status": "LOCKED_NOT_READ",
        "notes": ["Reference was AI-authored synthetic fixture and is not independent biological ground truth.",
                  "Field exact equality does not establish semantic correctness.",
                  "Response-level citations are not aligned to individual claims by the original output schema.",
                  "Original provider response text was not stored; raw-parsed values are already decoded mappings."]}
    packet = {"schema_version": "ai-v2-claim-support-review-packet-draft-1", "status": "AI_ASSISTED_PROPOSALS_OWNER_DECISIONS_PENDING",
        "claim_scope": "SYNTHETIC_SOFTWARE_ONLY", "independent_review_claim": False,
        "taxonomy_note": "The existing bound evaluator schema accepts SUPPORTED/UNSUPPORTED/UNCERTAIN/PENDING. This packet keeps owner decisions PENDING and stores separate proposal labels that do not mutate that schema.",
        "proposal_labels_are_human_decisions": False, "run_identity": {"run_dir": str(RUN), "case_outputs_sha256": output_hash,
            "corpus_sha256": config["corpus_sha256"], "rubric_sha256": config["rubric_sha256"],
            "manifest_sha256": config["manifest_sha256"],
            "model_configured_id": config["configured_model_id"], "prompt_version": config["prompt_version"], "partition": config["partition"]},
        "field_analysis": {"row_count": len(field_rows), "rows": field_rows,
            "existing_owner_reference_approval": {"status": rubric.get("status"), "reviewer_ids": rubric.get("reviewer_ids"),
                "reviewed_at": rubric.get("reviewed_at"), "rubric_sha256": inputs["rubric_sha256"],
                "note": "This is prior frozen package metadata. Step 2 does not create or change an owner decision."},
            "missing_field_comparison": missing_diffs, "raw_value_shape_counts": dict(value_shapes),
            "gold_review_required_rows": summary["gold_review_required_rows"],
            "postprocessing_changes": postprocess_changes, "critical_error_candidates": critical_candidates,
            "mismatch_counts_by_branch": {s: len(mismatch_by_system[s]) for s in SYSTEMS},
            "mismatches_both_branches": sorted([list(x) for x in mismatch_intersection]),
            "mismatches_only_no_retrieval": sorted([list(x) for x in mismatch_sets[SYSTEMS[0]] - mismatch_sets[SYSTEMS[1]]]),
            "mismatches_only_rag": sorted([list(x) for x in mismatch_sets[SYSTEMS[1]] - mismatch_sets[SYSTEMS[0]]])},
        "extraction_cases": case_docs, "claims": claims, "claim_count_reconciliation": claim_count_reconciliation,
        "diagnostic_case_012": {"case_id": diagnostic[0]["case_id"], "category": diagnostic[0]["category"],
            "protocol_text": diagnostic[0]["protocol_text"], "not_in_extraction_aggregate": True,
            "branches": [{"branch": s, "status": by_key[s, diagnostic[0]["case_id"]]["status"],
                "provider_called": by_key[s, diagnostic[0]["case_id"]]["provider_called"],
                "retrieved_hit_count": len(by_key[s, diagnostic[0]["case_id"]].get("retrieved_evidence", [])),
                "raw_output": by_key[s, diagnostic[0]["case_id"]].get("raw_output"),
                "runtime_missing_fields": by_key[s, diagnostic[0]["case_id"]].get("missing_fields")} for s in ("manual_template", *SYSTEMS)]},
        "owner_decision_state": "PENDING", "reviewer_ids": [], "reviewed_at": None}

    dump(OUT / "field_error_analysis.json", packet["field_analysis"] | {"run_identity": packet["run_identity"], "extraction_cases": case_docs,
         "case_012_diagnostic": packet["diagnostic_case_012"]})
    dump(OUT / "claim_support_review_packet.json", packet)
    dump(OUT / "step2_summary.json", summary)
    write_markdown(OUT, packet, summary, source_lines, source_headings)
    inventory = {}
    for path in sorted(OUT.iterdir()):
        if path.is_file() and path.name != "sha256_inventory.json":
            inventory[path.name] = sha(path)
    dump(OUT / "sha256_inventory.json", {"algorithm": "SHA-256", "files": inventory,
         "inventory_self_hash": "not included; a file cannot include its own stable digest"})
    # Verify generated deliverables, all claims/cases and source-chunk locators.
    for name in ("field_error_analysis.json", "claim_support_review_packet.json", "step2_summary.json"):
        json.loads((OUT / name).read_text(encoding="utf-8"))
    assert len(packet["extraction_cases"]) == 11 and len(packet["claims"]) == 105
    assert packet["diagnostic_case_012"]["not_in_extraction_aggregate"] is True
    print(json.dumps({"status": summary["status"], "output_dir": str(OUT), "cases": len(extraction),
        "field_rows": len(field_rows), "mismatches_by_branch": summary["mismatch_counts_by_branch"] if "mismatch_counts_by_branch" in summary else {s: len(mismatch_by_system[s]) for s in SYSTEMS},
        "claims": counts, "postprocessing_changes": len(postprocess_changes), "critical_error_candidates": len(critical_candidates),
        "provider_called": False}, ensure_ascii=False))


def write_markdown(out: Path, packet: dict, summary: dict, source_lines: list[str], source_headings: dict) -> None:
    analysis = packet["field_analysis"]
    prior_owner = analysis["existing_owner_reference_approval"]
    lines = ["# Step 2 — Field errors and claim support review", "",
        "**AI-assisted proposals — owner decisions PENDING.** This packet analyzes a saved synthetic software fixture. It is not a biological review or independent gold standard.", "",
        f"Run `paired-20261009T131833878Z`; outputs SHA-256 `{packet['run_identity']['case_outputs_sha256']}`.",
        f"Frozen corpus `{packet['run_identity']['partition']}`; 11 extraction cases. Case 012 is separate.", "",
        "## Review first: potential critical issues", ""]
    critical = analysis["critical_error_candidates"]
    if not critical:
        lines.append("No field mismatch met the packet's mechanical candidate rule (nonempty runtime value where the frozen reference declares a field missing). Review the mismatch table below; this does not mean there are no consequential errors.")
    else:
        for item in critical:
            lines.append(f"- **Candidate, owner decision PENDING — {item['case_id']} / {item['branch']} / `{item['field_name']}`:** output {item['candidate']}. {item['reason']}")
    lines += ["", "Other exact-match errors are listed by case below. They are candidates for owner adjudication, not automatic semantic-error labels.", "",
        "## Aggregate field comparison", "",
        f"- Raw field rows: {len(analysis['rows'])}; mismatches: no-retrieval {len([r for r in analysis['rows'] if r['branch']=='llm_no_retrieval' and r['match_status']=='MISMATCH'])}, RAG {len([r for r in analysis['rows'] if r['branch']=='llm_rag' and r['match_status']=='MISMATCH'])}.",
        f"- Same case-field mismatched in both: {len(analysis['mismatches_both_branches'])}; only no-retrieval: {len(analysis['mismatches_only_no_retrieval'])}; only RAG: {len(analysis['mismatches_only_rag'])}.",
        "- Scored value is `record.fields`; evaluator treats absent as null then applies exact equality. Strings are not semantically normalized.",
        "- `raw_parsed_value` is a decoded object. Original provider response text was not retained.", ""]
    for case in packet["extraction_cases"]:
        lines += [f"## {case['case_id']} — {case['category']}", "", "**Protocol input**", "", "```text", case["protocol_text"], "```",
                  f"Locator: `{case['protocol_locator']}`", "", f"Frozen reference: existing status `{prior_owner.get('status')}`, reviewer `{', '.join(prior_owner.get('reviewer_ids', []))}`, timestamp `{prior_owner.get('reviewed_at')}`. Step 2 preserves this decision. Earlier package note (preserved): {case.get('review_note') or ''} It is draft-time wording; current metadata records the later approval above.", ""]
        for branch, detail in case["branches"].items():
            lines += [f"### {branch}", "", f"Status: `{detail['status']}`; provider_called={detail['provider_called']}.", "",
                "| Field | Reference | Raw parsed | Processed | Scored | Result | Gold/source check | Support excerpt |", "|---|---|---|---|---|---|---|---|"]
            for row in detail["fields"]:
                support = row["protocol_support_excerpt"].replace("|", "\\|")
                gold_check = f"{row['gold_review_status']}: {row['gold_review_reason']}".replace("|", "\\|")
                lines.append(f"| `{row['field_name']}` | {row['reference_value']} | {row['raw_parsed_value']} | {row['processed_value']} | {row['evaluator_value']} | **{row['match_status']}** | {gold_check} | {support} |")
            lines += ["", f"Model-declared missing_fields: `{json.dumps(detail['model_declared_missing_fields'], ensure_ascii=False)}`; runtime-computed: `{json.dumps(detail['runtime_computed_missing_fields'], ensure_ascii=False)}`.",
                f"Set differences: model-only `{detail['raw_vs_runtime_missing']['model_only']}`; runtime-only `{detail['raw_vs_runtime_missing']['runtime_only']}`.",
                f"Citation pair trace: raw model pairs `{json.dumps(detail['citation_pairs_model_raw_parsed'], ensure_ascii=False)}`; runtime citations `{json.dumps(detail['citations_after_runtime'], ensure_ascii=False)}`.",
                f"Retrieved excerpts (each locator is corpus JSONL line + chunk ID): {len(detail['retrieved_evidence'])}.", ""]
            for e in detail["retrieved_evidence"]:
                chunk = e.get("chunk_id", "")
                # Store actual line number looked up from the input corpus in the packet excerpt record.
                lines.append(f"- `{e.get('source_id')}` / `{chunk}` — `{e.get('corpus_locator')}`; {e.get('source_document_locator')}: {e.get('text')}")
            if not detail["retrieved_evidence"]:
                lines.append("- No retrieved evidence for this arm.")
            lines.append("")
    lines += ["## Claim-support packet", "", "Every saved scalar claim is included in the JSON packet and below, in run order. Claims are statements extracted from raw-parsed model fields; a response-level citation list is not claim-level attribution.", "",
              "Axis A asks whether protocol/evidence supports the claim. Axis B asks whether a paired citation excerpt supports that claim. No-retrieval citation support is N/A. Suggestions use literal comparison heuristics only; owner decisions remain PENDING.", ""]
    diff = packet["claim_count_reconciliation"]
    lines += [f"Claim-unit reconciliation: no-retrieval {diff['llm_no_retrieval']}, RAG {diff['llm_rag']}, common content units {diff['common_units']}. RAG-only/no-retrieval-only content is listed in JSON. The extractor recursively counts non-empty scalar strings, including nested source metadata; these are not independent scientific claims.", ""]
    for claim in packet["claims"]:
        lines += [f"### {claim['branch']} / {claim['case_id']} / `{claim['claim_id']}`", "", f"Claim ({claim['field_path']}): **{claim['claim']}**",
            f"Source: `{claim['source_locator']}`", "", "Protocol input:", "", "> " + claim["protocol_input"].replace("\n", "\n> "), "",
            f"Axis A proposal: `{claim['proposal_axis_a_protocol_support']['suggestion']}` — {claim['proposal_axis_a_protocol_support']['reason']}",
            "Owner axis A: **PENDING**.", f"Axis B proposal: `{claim['proposal_axis_b_citation_support']['suggestion']}` — {claim['proposal_axis_b_citation_support']['reason']}",
            f"Owner axis B: **{claim['owner_decision']['axis_b']}**.", f"Response-level raw citation pairs: `{json.dumps(claim['response_level_raw_citation_pairs'], ensure_ascii=False)}`.",
            f"Runtime citations: `{json.dumps(claim['runtime_citations'], ensure_ascii=False)}`; raw pair identities equal: `{claim['raw_pairs_equal_runtime_pairs']}`.",
            f"Critical-error candidate: `{claim['critical_error_candidate']}`. Existing review-template support status: `{claim['existing_evaluator_review_status']}`.", "Relevant retrieved evidence:"]
        if claim["claim_linked_cited_excerpts"]:
            for e in claim["claim_linked_cited_excerpts"]:
                lines.append(f"- `{e['source_id']}` / `{e['chunk_id']}` — `{e.get('corpus_locator')}`; {e.get('source_document_locator')}: {e['text']}")
        elif claim["retrieved_excerpts"]:
            lines.append("- No exact claim-linked cited excerpt identified; retrieved excerpts for this case:")
            for e in claim["retrieved_excerpts"]:
                lines.append(f"  - `{e['source_id']}` / `{e['chunk_id']}` — {e['citation']}: {e['text']}")
        else:
            lines.append("- None (retrieval is not applicable on no-retrieval arm).")
        lines += ["", "Owner decision: **PENDING**", ""]
    d = packet["diagnostic_case_012"]
    lines += ["## Case 012 — separate lexical no-hit diagnostic", "", f"Synthetic nonce protocol: `{d['protocol_text']}`. Not included in the 11-case extraction aggregate.", ""]
    for b in d["branches"]:
        lines.append(f"- {b['branch']}: status `{b['status']}`, provider_called={b['provider_called']}, retrieval_hits={b['retrieved_hit_count']}, raw output `{json.dumps(b['raw_output'], ensure_ascii=False)}`.")
    lines += ["", "## Scope and decisions requested", "", "- Confirm whether exact-string field mismatches are genuinely unsupported, semantically equivalent, or caused by reference wording.",
        "- Review case 003 context carefully: protocol names `feeding_state` but its value says ‘not specified’; output substitutes `specimen_context`. Decide whether gold context sex-only is correct and whether this mismatch is consequential.",
        "- Review raw model missing_fields separately from the runtime computed list. The evaluator's main missing-field F1 uses the runtime list; it can conceal model declaration differences.",
        "- Decide each claim on axis A and axis B independently. AI suggestions are not owner labels.",
        "- Reference text itself is synthetic and AI-authored; adjudicating its consistency does not establish biological validity.", ""]
    (out / "field_error_analysis.md").write_text("\n".join(lines), encoding="utf-8")
    claim_md = ["# Claim support review packet", "", "**AI-assisted proposals — owner decisions PENDING.** Claim units below are all 105 saved claims. Owner labels remain blank/PENDING.", ""]
    for claim in packet["claims"]:
        claim_md += [f"## {claim['branch']} / {claim['case_id']} / `{claim['claim_id']}`", "",
            f"- Claim: {claim['claim']}", f"- Field path and source: `{claim['field_path']}`; `{claim['source_locator']}`",
            f"- Protocol: {claim['protocol_input']}", f"- Axis A proposal: `{claim['proposal_axis_a_protocol_support']['suggestion']}` — {claim['proposal_axis_a_protocol_support']['reason']}",
            f"- Axis B proposal: `{claim['proposal_axis_b_citation_support']['suggestion']}` — {claim['proposal_axis_b_citation_support']['reason']}",
            f"- Response raw citation pairs: `{json.dumps(claim['response_level_raw_citation_pairs'], ensure_ascii=False)}`",
            f"- Citation/runtime trace: {claim['citation_trace']} Raw/runtime pair equal: `{claim['raw_pairs_equal_runtime_pairs']}`.",
            f"- Owner axis A: **PENDING**; axis B: **{claim['owner_decision']['axis_b']}**; critical-error candidate: `{claim['critical_error_candidate']}`.", "Evidence:"]
        evidence = claim["claim_linked_cited_excerpts"] or claim["retrieved_excerpts"]
        if not evidence:
            claim_md.append("- None; citation evaluation N/A on no-retrieval branch.")
        for e in evidence:
            claim_md.append(f"- `{e['source_id']}` / `{e['chunk_id']}` — `{e.get('corpus_locator')}`; {e.get('source_document_locator')}: {e['text']}")
        claim_md.append("")
    (out / "claim_support_review_packet.md").write_text("\n".join(claim_md), encoding="utf-8")
    post = ["# Post-processing impact", "", "The original provider response text was not stored. `raw_parsed_value` below means the mapping after JSON parsing, before Workbench sanitization. No claim is made about duplicate keys in the original JSON text.", "",
        "## What runtime changes", "", "For RAG, runtime filters citations to source/chunk pairs among retrieved hits, drops nested unverified citation metadata, and enriches accepted pairs with corpus citation/locator metadata. For both LLM branches it sanitizes permitted fields/context/suggestions and recomputes `missing_fields` from required fields absent from the processed draft. The evaluator scores `record.fields` and runtime `record.missing_fields`; it does not score the model-declared missing list as its main F1.", "",
        "## Measured impact", ""]
    for system in SYSTEMS:
        source = next(s for s in c.read_json(RUN / "metrics.json")["systems"] if s["system_id"] == system)
        rawf = source["raw_missing_declaration"]
        proc = source["missing_fields"]
        post += [f"### {system}", "", f"- Field exact remains {source['field_exact']['correct']}/{source['field_exact']['denominator']} = {source['field_exact']['accuracy']:.6f}; evaluator value is sanitized field output.",
            f"- Main runtime missing_fields: TP/FP/FN={proc['tp']}/{proc['fp']}/{proc['fn']}, F1={proc['f1']:.6f}.",
            f"- Raw model-declared missing_fields: TP/FP/FN={rawf['tp']}/{rawf['fp']}/{rawf['fn']}, F1={rawf['f1']:.6f}; {rawf['attempted_cases']} provider attempts.", ""]
    post += ["Case 003's `context` raw value contains `sex=female` plus a `specimen_context` string carrying ‘not specified’; the frozen gold contains sex only. That exact field slot is a mismatch in both branches. Runtime retains the allowed specimen_context string, so sanitization does not repair this mismatch.",
        "Case 004 is a material post-processing/scoring edge: both models declare `hypothesis` missing, but raw-parsed outputs contain either a complete speculative sentence or the nonempty placeholder string `missing`. Runtime only checks whether a nonempty string exists, so it removes `hypothesis` from its computed missing_fields in both branches. This changes the main missing-field F1: RAG raw declaration 1.000 to workflow 0.933; no-retrieval remains 0.857 overall because case 006 runtime detects an omitted assay that the model failed to declare. Neither numeric equality for no-retrieval proves the per-case labels agree.",
        "Case 011 post-processing strips nested `sources` from control_suggestions in both arms. The exact field remains mismatched after processing because the required rationale is absent; this sanitizer change did not change the field exact score for that slot.",
        "Shape counts for all 114 required-field raw-parsed values are in `field_error_analysis.json`; the literal `missing` placeholder is a nonempty string, not null/empty/absent.",
        "For missing fields, inspect every difference in `field_error_analysis.json`. Runtime-added/removed labels alter the main missing-fields metric only when the resulting set differs from the reference; raw declaration F1 is a separate descriptive metric.",
        "Case 012 is a distinct diagnostic: no-retrieval called the provider with no retrieved evidence; RAG abstained before provider call. It is not part of extraction aggregates.", ""]
    (out / "postprocessing_impact.md").write_text("\n".join(post), encoding="utf-8")
    summary_md = ["# Step 2 summary", "", "Status: **READY_FOR_OWNER_REVIEW_AI_ASSISTED**", "",
        f"- Extraction cases: 11; diagnostic case 012 separate.", f"- Saved claims: {summary['claims_by_branch']['llm_no_retrieval']} no-retrieval + {summary['claims_by_branch']['llm_rag']} RAG = {summary['claim_count']} unique IDs.",
        f"- Field rows: {summary['field_row_count']}; mismatches: no-retrieval {len(analysis['mismatch_counts_by_branch']) if False else len([x for x in analysis['rows'] if x['branch']=='llm_no_retrieval' and x['match_status']=='MISMATCH'])}, RAG {len([x for x in analysis['rows'] if x['branch']=='llm_rag' and x['match_status']=='MISMATCH'])}.",
        f"- Raw-parsed value shapes over 114 required-field slots: {summary['raw_value_shape_counts']}; missing declaration/runtime differences: {summary['model_runtime_missing_set_delta_records']} case-arm rows.",
        f"- `GOLD_REVIEW_REQUIRED` flags: {summary['gold_review_required_rows']}; case 003 context is separately marked as an already owner-approved interpretive edge.",
        f"- Mismatched field identities: shared {len(analysis['mismatches_both_branches'])}, only no-retrieval {len(analysis['mismatches_only_no_retrieval'])}, only RAG {len(analysis['mismatches_only_rag'])}.",
        f"- Raw-to-processed changed field slots: {len(analysis['postprocessing_changes'])}; critical candidates: {len(critical)}.",
        "- Claim-support decisions remain **PENDING**. The frozen rubric already carries an owner approval; Step 2 preserves that metadata and flags only any source-trace concern.",
        "- All claim IDs link to actual outputs and existing template rows; retrieval excerpt pairs were checked against the frozen corpus.",
        "- Case 012 is excluded from field and claim extraction aggregates.",
        f"- The 52 vs 53 claim-unit count follows the content differences explained in `claim_count_reconciliation`; it is not a count of independent scientific claims.",
        "- Case 012 behavior: no-retrieval called provider with zero hits; RAG abstained before provider call.",
        "- No provider call, held-out read, simulation, or source/frozen package mutation.", "",
        "## Owner review questions", "",
        "1. For every exact mismatch, is the frozen reference supported by the protocol, is output semantically equivalent, or should it be judged incorrect?",
        "2. In case 003, should `feeding_state: not specified...` be treated as missing while retaining `sex=female`, and is `specimen_context` an unsupported substitution?",
        "3. For each claim, decide protocol support and citation support separately. Where no-retrieval has no citation, axis B is N/A.",
        "4. Confirm whether flagged potential critical errors are consequential. These are candidates, not final labels.", ""]
    (out / "step2_summary.md").write_text("\n".join(summary_md), encoding="utf-8")


if __name__ == "__main__":
    main()
