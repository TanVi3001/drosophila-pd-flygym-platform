# Fly Research Workbench — Codex handoff

**Last assembled:** 2026-10-11 (Asia/Saigon)

**Repository:** `E:\research-\.workbench\ai-v2-dev`

**Purpose:** transfer project context to another Codex account. This is a navigation/status document, not an approval, freeze, scientific review, or replacement for source artifacts.

## Start here

1. Read [`AGENTS.md`](AGENTS.md) and keep its scientific/software boundaries.
2. Read [`docs/ai_v2/architecture.md`](docs/ai_v2/architecture.md), [`docs/ai_v2/rag_contract.md`](docs/ai_v2/rag_contract.md), [`docs/ai_v2/protocol_output_schema_v2.md`](docs/ai_v2/protocol_output_schema_v2.md), [`docs/ai_v2/task3b_comparator_measurement_v2.md`](docs/ai_v2/task3b_comparator_measurement_v2.md), and [`docs/ai_v2/evaluation_task_split.md`](docs/ai_v2/evaluation_task_split.md).
3. Treat `.workbench/` as local evidence/artifact storage. Inspect a task-specific artifact before continuing; do not overwrite frozen packages or historical runs.
4. Check `git status` first. At handoff time the repository is substantially dirty with existing project work. Preserve all of it; do not reset, clean, checkout, or commit/push unless explicitly asked.
5. Current requested next work is the STEP 8 development evaluation draft described below—not another run of the synthetic pilot.

## Project goal and boundaries

The team is building an AI-assisted Fly Research Workbench. The user's main focus is the AI evaluation/drafting capability; Tuấn is separately focused on production deployment. The practical aim is a credible internal demo and potentially a paper, without making external wet-lab adoption a prerequisite. External validation would be valuable if available, but is not assumed.

The software can help draft and prioritize; it is not an autonomous scientific authority. Keep separate:

- implemented software behavior;
- synthetic fixture behavior;
- source-supported protocol extraction;
- biological validity and wet-lab observations (not established by the work below).

Never infer biological truth, neuron identity/mapping, or experimental effects from a software test, retrieval result, or simulation artifact. The AI path must remain a draft and preserve human mapping, StudySpec, approval, and execution gates.

## Architecture/status snapshot

### AI V2 modeling path

The documented proposed path composes replaceable interfaces (`EvidenceRetriever`, `StudySpecGenerator`, `GraphEncoder`, `FeatureFusion`, `RankingHead`, `UncertaintyEstimator`, `AIV2ExperimentRunner`). The intended flow combines an approved offline evidence source and draft StudySpec with graph metadata, LIF effect, uncertainty, and QC/provenance features, then produces a ranking prediction and development-fold metrics.

Important limits in [`docs/ai_v2/architecture.md`](docs/ai_v2/architecture.md): development-only; no large graph model, web retrieval, training algorithm, or external evaluation is implemented; synthetic fixtures do not establish biological validity. Do not claim a complete biological AI system from the architecture diagram.

### RAG and protocol drafting

The current documented retriever is deterministic local lexical BM25-style ranking over a loaded corpus snapshot. It has no web search or semantic embedding index and does not train/update the LLM. Provider calls are optional and gated by explicit corpus-text and protocol-text sharing decisions plus exact provider identity/endpoint match. The model returns a proposal; citations are restricted to retrieved source/chunk pairs; no-hit RAG abstains; mapping, approval, and job execution remain separate human gates. See [`docs/ai_v2/rag_contract.md`](docs/ai_v2/rag_contract.md).

Protocol intake required fields are `hypothesis`, `falsifiable_prediction`, `assay`, and `primary_metric`; unsupported required information should be represented as missing, not invented. Output schema proposal and its limits are in [`docs/ai_v2/protocol_output_schema_v2.md`](docs/ai_v2/protocol_output_schema_v2.md).

### Workbench integration and staging

The repository contains staging/Docker support and an evidence-gated workflow. Local staging was previously run by the owner on Windows at `localhost:8000`; the API token is created in the owner's PowerShell session and must never be pasted into chat or committed. Gemini secret is environment-only. If resuming deployment, inspect [`docs/ai_v2/staging_deployment.md`](docs/ai_v2/staging_deployment.md) and [`docs/ai_v2/review_gated_demo.md`](docs/ai_v2/review_gated_demo.md), then inspect the actual current Docker/container state. Do not assume the old service is still running.

The user explicitly accepted a synthetic-only demo flow with mapping `SYNTHETIC_MAPPING_V1`; a previous schema mismatch was fixed and local tests/finalize had been run. That acceptance is for a software fixture only and must not be re-used as approval for a new corpus, scientific mapping, provider data-sharing policy, or evaluation package.

## Verified synthetic pilot results (historical; not the STEP 8 pack)

### Original Gemini paired run

Run directory: `.workbench/ai-v2-comparisons/paired-20261009T131833878Z/`

Report: [`report.md`](.workbench/ai-v2-comparisons/paired-20261009T131833878Z/report.md)

Metrics: [`metrics.json`](.workbench/ai-v2-comparisons/paired-20261009T131833878Z/metrics.json)

- Status: `MEASURED_OWNER_REVIEWED_SYNTHETIC_DEMO_NOT_INDEPENDENT`.
- 11 synthetic extraction cases plus case 012, a separate lexical no-hit diagnostic.
- Gemini model identity recorded: `gemini-3.1-flash-lite`, adapter ID `openai-compatible:gemini-3.1-flash-lite`. Stored results are historical; don't call provider unless a new run is explicitly requested and all current gates are checked.
- Original run: no-retrieval field exact `53/57`; RAG `54/57`; missing-field F1 `0.857` and `0.933`; Recall@5 `0.977`; gold-set Precision@5 `0.473` (26/55 relevant/returned hits). The non-gold chunks are unjudged; these are not semantic-support metrics.
- Manual-template remained `NOT_RUN` for all 11; therefore `comparison_complete=false`. Do not represent this as a completed three-arm comparison.
- Stored parsed-output schema status is not the exact raw HTTP body. Distinguish raw provider JSON, parsed mapping, sanitized Workbench draft, and offline replay.
- Case 012 remains outside the 11-case extraction aggregate. In the original run, RAG abstained with no provider call; no-retrieval called the provider despite zero hits.

### Owner A/B review and summary

- Record: `.workbench/ai-v2-audits/step4-owner-claim-support-review-20261010-v1/owner_review_record.json`.
- Reconciliation: [`reconciliation_owner_ab_20261010.md`](.workbench/ai-v2-audits/step4-owner-claim-support-review-20261010-v1/reconciliation_owner_ab_20261010.md).
- Summary: [`pilot_owner_reviewed_summary.md`](.workbench/ai-v2-audits/pilot-owner-reviewed-summary-20261010-v1/pilot_owner_reviewed_summary.md); machine-readable metrics in `summary_metrics.json`.
- 105 unique claim units; 105 A/B decisions; 102 content INCLUDE, 3 content-denominator EXCLUDE (one missing-value placeholder and two source metadata units), 0 pending. Inventory still retains all 105.
- One reviewer `owner-le-tan-vi`; AI-assisted; `independent_review_claim=false`; classification was post-hoc.
- A, input fidelity on included synthetic content units: no-retrieval 49 supported, 1 partial, 2 unsupported / 52; RAG 49 supported, 1 partial, 0 unsupported / 50. These are dependent units within 11 cases, not independent samples. No p-values/superiority inference.
- B is cited-guide-only support, not citation precision/error or hallucination rate. RAG has 16 partial, 34 unsupported, 3 N/A across all 53 units; attribution is unresolved because citations were response-level.
- Five claim-unit severities and two case-011 omission diagnostic severities remain unresolved. `owner_review_complete=false`; only A/B plus post-hoc classification are reconciled. No critical-error rate.
- Historical offline replay is post-processing only. RAG replay changed exact fields to 55/57 and missing F1 to 1.0; this is not a new Gemini result and does not replace the original run.

### Reference-exposed Codex template score

Directory: `.workbench/ai-v2-comparisons/ai-assisted-template-offline-score-20261010-v1/` (`report.md`, `metrics.json`, `case_level_reconciliation.json`).

- Score: 56/57 exact, missing TP/FP/FN 8/0/0, schema 11/11, completion 11/11.
- This is `Codex AI-assisted template — reference-exposed`, not a manual or rule-based baseline. The owner had already seen references/outputs; generation time, human time, and cost are not measured.
- One mismatch is case 003 context; output preserved the literal `feeding_state` note while frozen reference contains `sex` only. It was not edited after scoring.
- Do not transfer Gemini claim-support labels to this arm; its claim support is not reviewed.
- Manual remains pending, original run unchanged, three-arm comparison incomplete.

## Current STEP 8: new source-derived development set proposal

Pack directory: `.workbench/evidence/protocol_evidence_eval_draft_20261010_v1/`.

Read [`README.md`](.workbench/evidence/protocol_evidence_eval_draft_20261010_v1/README.md), [`readiness.md`](.workbench/evidence/protocol_evidence_eval_draft_20261010_v1/readiness.md), [`evaluation_protocol_draft.md`](.workbench/evidence/protocol_evidence_eval_draft_20261010_v1/evaluation_protocol_draft.md), [`review_checklist.md`](.workbench/evidence/protocol_evidence_eval_draft_20261010_v1/review_checklist.md), and `source_inventory.json` before editing.

Status is `DRAFT_FOR_REVIEW_NOT_FROZEN`. It is a separate proposed source-derived task set—not the synthetic pilot and not raw registered wet-lab protocols from the group. Public PLOS article excerpts were selected from Methods/Introduction; team-authored and adversarial variants are explicitly tagged. The pack is not owner-reviewed, license-reviewed, scientifically validated, frozen, or model-run.

### Actual counts and integrity

Structural audit output was `STRUCTURAL_DRAFT_AUDIT_PASS`:

| Category | Count |
|---|---:|
| Fully specified constructed | 0 |
| Required-field missing | 4 |
| Readout/context ambiguous | 4 |
| Preserve context/control/rationale | 4 |
| Outside-capability/mapping request | 4 |
| Untrusted-instruction perturbation | 4 |
| **Total** | **20** |

The intended target was 24, but 4 fully specified cases were not created: source evidence did not justify selecting a primary metric in those cases, so the builder did not guess. This is the correct honest count until source/reviewer decisions improve coverage.

Draft hashes (`hash_inventory.json`):

- `inputs/cases.jsonl`: `9e7364991a033b8d304a325ab512dfd7b8ef2bd87d498fb2c40fbb8e59ce39c9`
- `corpus/corpus_draft.jsonl`: `dc89bf5e612f308026d153ffb3ab341a74900db5b349a7e33988f3bf8b4e5393`
- `reference/reference_rubric_draft.json`: `2573ad7862b8b3ccffecda4d5257b470ab6a00b8bacbfb43d74c2afa20475863`
- `source_inventory.json`: `c71997b62d279dc428304aad44bbaf5e0d7c6f7c30431001ce1a59b926d6e0dc`
- Draft manifest status: `DRAFT_INTEGRITY_ONLY_NOT_APPROVAL`.
- Source/code snapshot: HEAD `6c70f4c94164e6320836ca1c9ae43348379c33b8`, worktree dirty; see `source_code_hash_inventory.json`.

The audit checks structure/integrity only. It does not establish source rights, source correctness, scientific appropriateness, gold correctness, review, privacy approval, or readiness to call a provider. The 20-case pack was not frozen and no model/provider/comparator was run for it.

### Four model-facing examples (no reference answers)

These are short descriptions, not a substitute for the original case/provenance records. See `inputs/cases.jsonl` for exact text.

1. A source-derived protocol input with a required field absent; task asks for a draft and explicit missing-field handling.
2. A source-derived input mentioning multiple readouts without designating one primary; system should not silently choose.
3. A context/control case where the protocol states information that must be preserved without changing its field meaning.
4. An input requesting a neuron identity/mapping unsupported by provided evidence; the system should identify the capability/evidence boundary rather than invent an ID.

Some of the adversarial/noisy instructions are team-authored perturbations, not instructions or claims from the cited paper. Do not describe all 20 as real wet-lab protocols.

### Draft comparison plan

The proposal is to compare (a) deterministic rule extraction, (b) LLM without retrieval, and (c) the same LLM plus local RAG. A human baseline only exists if a real human completes it; currently none is recorded for this pack. Candidate measures include field accuracy, missing-field detection, completion/error/abstention, evidence support, and claim-to-evidence support. Protocol-input provenance must be separated from citations that only support scientific terminology/rules. Citation support should be annotated per claim, not inferred from response-level citations. Source/protocol families need group-aware splits to avoid near-duplicate leakage.

## Decisions and protections already established

- Owner identity for prior review: `owner-le-tan-vi`; single-reviewer internal demo is not independent.
- Synthetic fixture acceptance applies only to that synthetic software session.
- Manual baseline must contain actual owner answers; AI-generated reference-exposed rows cannot be relabeled as manual.
- Do not silently drop failures, abstentions, missing outputs, or N/A; report denominators and applicability.
- Do not leak gold answers/rubrics into provider inputs.
- No held-out/sealed data or mixed mapping CSVs for this work; held-out status remains `LOCKED_NOT_RUN`.
- No biological/wet-lab validation has been performed or established.
- No external lab review is a prerequisite for internal software progress, but do not claim external validation.

## Recommended next actions (in order)

1. **Review the STEP 8 draft content/source inventory.** Verify each excerpt against the cited paper section, exact locator, license/usage scope, wording, and source grouping. Keep gold/reference separate from model-facing inputs. Resolve any malformed source attribution before changing hashes.
2. **Review the 20 cases and coverage gap.** Decide if the 0 fully-specified category should remain 0, or identify legitimate source passages that explicitly support all required fields without guessing. Do not pad to 24 by relabeling or inventing protocol details. Ensure “abstain” cases do not reveal the answer in their prompt.
3. **Review the reference rubric privately.** Confirm field-level values, accepted paraphrases, missingness, evidence locators, answerability, and which claims are protocol-derived versus literature-rule-derived. Do not send this file to a model.
4. **Define split and freeze gates before any run.** Group by source/protocol/template to prevent family leakage; specify model/prompt/retries/timeouts, k, normalization, metric denominators, provider/privacy decision, and reviewer plan. A single-owner demo must be labeled non-independent; publication claims need stronger review.
5. **Only after explicit owner decisions**, create a new versioned approved package/manifest; do not edit this draft into an approval in place. Verify exact hashes and audit.
6. **Implement/verify required evaluation tooling** listed in `readiness.md`: deterministic rule baseline, adapter/collector for these source-derived cases, structured out-of-capability refusal, claim-to-evidence annotations, and source-cluster-aware reporting. Test with local fixtures/stubs first.
7. **Then run a development-only comparison if authorized.** Preserve every case's status and artifact. Keep the new source-derived evaluation separate from the historical 11-case synthetic pilot and from case 012 diagnostic.
8. Report descriptive results and limitations. Do not state RAG superiority, biological understanding, or external validity from this small, reviewed set.

## Explicitly not done / not authorized by this handoff

- STEP 8 content review, owner approval, freeze, or publication.
- Provider call/model run/comparator run on the new 20-case pack.
- Any completion of the manual baseline using AI outputs.
- Closing pilot severity or claim-to-citation attribution; exporting labels to an evaluator.
- Reading/running the 32 held-out cases, sealed outcomes, or mixed mapping partitions.
- Biological mapping validation, simulation, wet-lab validation, or external laboratory test.
- Commit, push, destructive cleanup, or overwriting the historical pilot/frozen packages.

## Repository hygiene at handoff

The recorded HEAD is `6c70f4c94164e6320836ca1c9ae43348379c33b8`; worktree was dirty, with existing modifications and many untracked implementation/docs/tests. A subset list is available from `git status` in the original worktree; the new handoff file is an additional untracked root-level file. `.workbench/` artifacts are Git-ignored. Do not assume every project artifact is committed or portable with Git; transfer required `.workbench` packs separately if the next account/worktree does not share this disk.

This handoff was prepared by inspecting only the allowed AI V2 docs and development/pilot evidence referenced above. Held-out and sealed materials were not opened.
