# Task 3B — Comparator/evaluator measurement contract

Status: implementation contract and synthetic local-stub tests. This is not an
approval or freeze of the current corpus, rubric, baseline, or provider policy.

## Case partition

Keep all 12 case outputs and provenance records. Aggregate protocol quality only
over the 11 extraction cases (`AI_PROTO_DEV_DRAFT_001`–`011`). The
`AI_PROTO_DEV_DRAFT_012` lexical no-hit probe is retained and reported separately
per arm: run status, provider attempted/called, number of retrieved hits,
abstention without evidence, and raw/processed schema status. Its empty gold
evidence set is N/A, not a zero score, and it does not affect any 11-case quality
aggregate.

## Retrieval metrics

Retrieval metrics apply only to `llm_rag`; other arms report N/A.

- Relevance is **gold-set ID relevance only**. IDs present in the gold set are
  judged relevant; non-gold IDs are unjudged, not assumed irrelevant.
- Recall@5 per assessable case is `|returned top-5 ∩ gold IDs| / |gold IDs|`.
- Precision@5 per assessable case is
  `|returned top-5 ∩ gold IDs| / |actual unique returned hits|`.
- Both are macro-averaged over extraction cases with non-empty gold evidence.
  The metric output reports the assessable-case denominator. Precision also
  reports summed relevant-hit numerator and summed returned-hit denominator.
- If fewer than five hits are returned, use their actual count; do not pad to
  five. Zero returned hits with a non-empty gold set score 0. Empty gold sets
  are excluded (N/A). A retrieval failure/no-hit on an assessable extraction
  case contributes 0; case 012 remains outside the aggregate.

## Protocol and workflow metrics

- Required-field exact accuracy: exact per-field match over all required slots
  in the 11 extraction cases; error, not-run, abstention, and missing output
  receive no correct credit. Report non-null-gold accuracy separately. A wholly
  NOT_RUN arm is NOT_MEASURED.
- Missing-field detection: micro TP/FP/FN/F1 across the runtime-required fields.
  Failure rows stay in the denominator; gold-missing fields with no usable
  output remain false negatives. Report sanitizer-computed missing fields
  separately from the model's raw `missing_fields` declaration.
- Citation identity: separately report raw citation pair existence in the
  corpus and raw pair match to gold, each divided by all raw citations. Malformed
  citations count incorrect; zero citations is N/A. Post-guardrail accepted
  citations are a separate measure. These do not prove claim support.
- Claim support requires human annotations bound to exact output bytes. Report
  supported, unsupported, uncertain, pending, and review coverage. No
  LLM-as-judge; unreviewed unsupported-claim rate is N/A/pending.
- Report `COMPLETED`, `ABSTAINED`, `ERROR`, and `NOT_RUN` counts/rates over all
  11 cases. Runtime success is `(COMPLETED + ABSTAINED) / 11`, separate from
  completed-draft rate. Do not silently remove failures or abstentions.
- Latency: count, mean, median, and p95 (nearest-rank). Provider timing is
  in-process retrieval plus generation and includes failed attempts; manual
  timing is self-reported and is not directly equivalent.

## Independent schema-valid measures

Use the actual intake contracts (`protocol-intake-draft-1` and
`protocol-rag-intake-draft-1`) and keep two stages distinct:

1. **Raw response schema:** validate the exact provider response before intake
   sanitization, including JSON parse/duplicate-key, allowed properties, value
   types, nested field shapes, and citation shape. A wrong but correctly typed
   answer can be schema-valid. A response that sanitizer repairs remains raw
   schema-invalid.
2. **Processed draft schema:** validate the actual Workbench draft after
   sanitizer/guardrails, including schema version, status, required metadata,
   missing-fields consistency, safety flags, retrieval/provenance, and
   citation-to-retrieved-evidence consistency for RAG.

For each stage, report counts by status, valid/observed-response or
valid/produced-draft rate, and valid/all-11-case rate. Raw statuses distinguish
`NO_RESPONSE`, `NOT_CALLED`, `NOT_RUN`, and unobserved/manual-pending states;
processed statuses distinguish `NOT_PRODUCED` and manual N/A. A no-hit RAG
abstention is checked against its explicit abstention contract. Schema-validity
is not answer correctness; field accuracy remains separate.

The standalone evaluator retains `schema_valid` as a backward-compatible alias
for processed-draft validity while also emitting `schema_validity.raw_output`
and `schema_validity.processed_draft`. It accepts explicit `ERROR` and
`NOT_RUN` rows so they remain in status/case denominators.

## Inputs, baseline, and execution gates

Current proposal identities (not approvals):

- Corpus: `d3918d889a4a8769258d5ee1e549b6a573aa318dc03a48e81fa5c5ffee9408b9`.
- Draft rubric: `92efc8e6d75d1c9ffbb7570fdfefe508f022bf7bd012ce9f36b338fa3d0ff4b7`.
- Case-003 proposal rubric: `ae4f781888a1271d2bbedce26dba5468e722485d073114e04a87efb5862c902c`.
- Blank baseline worksheet: `f67d02f145bd683c3fb504c575d211777cb361017f84a0e1943cebe7fc0eeee5`.

The current baseline worksheet stays blank and `PENDING`. The owner has seen
reference material, so any manual answers will be a non-blinded internal
comparator, potentially reference-contaminated; do not call it an independent
or blinded human baseline. The worksheet schema has no separate author field;
do not record the owner as having reviewed/completed a case before an answer is
provided. Only 11 protocol-extraction rows are eligible for a manual answer;
case 012 is a diagnostic and should stay `PENDING` in the manual arm. Any
AI-assisted suggestions must live in a separate artifact, never in the manual
baseline.

Before a real comparator run, the owner must explicitly choose corpus/rubric
versions and resolve remaining case-003/case-012 limits; complete or leave
baseline rows pending; freeze the matching package/policy; and separately
approve a specific provider/model/endpoint and data-sharing/privacy policy.
Gemini is not called by this implementation task. No corpus/rubric/baseline was
frozen, no sharing was authorized, and no held-out data were read or run.

## Verification for this implementation

On 2026-10-07, the specified Python environment ran:
`pytest tests/test_ai_v2_comparison.py tests/test_ai_v2_evaluation.py tests/test_ai_v2_collection.py -q`
Result: **91 passed**, with one Starlette/httpx deprecation warning. Tests use
local synthetic fixtures/stubs; no Gemini/provider request was made.
`git diff --check` exited 0. It printed only existing LF-to-CRLF warnings for
unrelated `rag_contract.md` and `contracts.py`; a whitespace scan of the seven
Task 3B code/test/doc files found no trailing whitespace.

`HELDOUT_STATUS = LOCKED_NOT_RUN`
