# AI V2: two separate development evaluation tasks

## Current scope

The local retrieval demonstration works with the owner's reviewed software-doc
snapshot. This document separates reference preparation from runtime activation
and model evaluation. Neither pack below has recorded model outputs or measured
AI-quality metrics. Do not change or replace the existing approved snapshot,
Docker mount, sharing flags or draft metadata when preparing a new pack.

| Pack | Inputs and purpose | Runtime alignment | Claim boundary |
| --- | --- | --- | --- |
| Software policy / retrieval | Existing 12 questions and 9 internal-document chunks | Questions can be sent to `/v1/ai/rag/retrieve`; policy answer fields need a separate compatible Q&A output adapter | Internal software behavior; no neuron biology |
| Protocol draft extraction | New 12 synthetic cases and 6 synthetic-guide chunks | `protocol_text` targets `/v1/ai/rag/draft`; references match `protocol-rag-intake-draft-1` | Synthetic software fixture; not biological or scientific-literature evaluation |

The draft endpoint proposes `name`, `hypothesis`, `falsifiable_prediction`,
`assay`, `primary_metric`, allowed `context`, suggestions and validated citations.
It does not emit policy-answer fields such as `retrieval_uses_web` or
`auto_approval`. Sending the old questions to it and scoring those policy fields
would measure a task/schema mismatch, not protocol-reading quality.

The legacy reference remains byte-for-byte unchanged. The auditor identifies an
absent `task_type` as `SOFTWARE_POLICY_QA` for backward compatibility. The new
rubric explicitly declares `PROTOCOL_DRAFT_EXTRACTION`.

## Local files

All corpus/reference/review material remains under Git-ignored
`.workbench/evidence/`. The new versioned pack is
`protocol_draft_development_v1/`:

- `protocol_fixture_source.md`: authored synthetic guide with explicit headings;
  not a paper, experiment or independent biological source.
- `protocol_development_corpus_draft.jsonl`: six verbatim guide excerpts in the
  runtime's six-field corpus format.
- `protocol_development_rubric_draft.json`: protocol text, exact reference fields,
  citations, support quotes, missing-field reasons and expected draft envelope.
- `README.md`: per-case description and review instructions.

The sibling `ai_v2_evaluation_split_v1.json` identifies the two packs and their
exact hashes. This is a preparation index, **not** an approved runtime manifest
or evaluation result. It must not be mounted in place of the live RAG manifest.

## What the protocol cases cover

| Case suffix | Purpose |
| --- | --- |
| 001 | Complete response protocol |
| 002 | Complete tracking protocol with reordered fields |
| 003 | Explicit context without inferring defaults |
| 004 | Missing hypothesis |
| 005 | Missing falsifiable prediction |
| 006 | Missing assay; glossary must not choose it |
| 007 | Missing primary metric; glossary must not designate it |
| 008 | Two mentioned metrics with no primary selection |
| 009 | Several missing core fields |
| 010 | Request for an unsupported neuron identity/mapping |
| 011 | Explicit control plus untrusted approval/run/citation instructions |
| 012 | Deliberate lexical no-hit probe |

Fixture assay/metric tokens are fictional extraction inputs. They are not
implemented simulation capabilities and must not be submitted as real
StudySpecs or used to claim Drosophila/MN9 knowledge.

Cases 004–009 have relevant evidence but incomplete protocol information; the
current endpoint returns a human-review draft with missing fields. Case 012
tests the distinct `ABSTAINED_NO_EVIDENCE` branch using a deliberate nonce. A
lexical hit does not establish semantic answerability. The old policy case 012
also remains a semantic unanswerable question, not a guaranteed lexical no-hit.

## Reference and scoring contract

The four runtime-required fields are `hypothesis`, `falsifiable_prediction`,
`assay`, and `primary_metric`. For each case:

1. `gold_fields` are expected values, **not model outputs**. Unknown required
   fields have `null` references and are omitted from
   `expected_output.proposed_fields`.
2. `field_support` quotes the supplied protocol text. Missing fields carry
   reasons; no unspecified metric, assay or identity is inferred from a glossary.
3. `gold_evidence_chunk_ids` and `gold_citations` are AI-assisted draft proposals
   pending owner review. Relevance is not automatically approved by their
   presence in the corpus. Citations must match real retrieved source/chunk pairs.
4. Expected `approved`, `study_created`, and `mapping_created` are always false.
   Mapping and execution requests cannot become proposed fields.
5. A future collector must map `proposed_fields` to evaluator `fields`,
   `DRAFT_REQUIRES_RESEARCHER_REVIEW` to `COMPLETED`, and
   `ABSTAINED_NO_EVIDENCE` to `ABSTAINED`. Compare citation identity pairs rather
   than additional server-generated citation metadata. Compare missing fields
   as sets. Provider/HTTP errors remain explicit failures, never fabricated
   abstentions or successful outputs.

The existing evaluator uses exact field matches. Exact string mismatch can
reflect paraphrasing, not a semantic error; report raw exact-match results and
review such cases separately. Do not silently edit references after viewing
model outputs. Keep the original protocol strings and version any normalization
rule before a measured run. The subsequent
[output collector](output_collection.md) now implements raw development API
collection separately. No real-provider run or scoring is established by
reference preparation or collector implementation.

## Structural checks

From the AI V2 worktree in PowerShell:

```powershell
$taskPython = 'E:\research-\.venvs\ai-v2-staging-312\Scripts\python.exe'
& $taskPython scripts/audit_ai_v2_draft_eval_inputs.py
& $taskPython scripts/audit_ai_v2_draft_eval_inputs.py `
  --corpus .workbench/evidence/protocol_draft_development_v1/protocol_development_corpus_draft.jsonl `
  --rubric .workbench/evidence/protocol_draft_development_v1/protocol_development_rubric_draft.json
```

`STRUCTURE_PASS_DRAFT_ONLY` checks structure, exact source/corpus hashes,
citations and compatibility with runtime field names. It does not establish
gold correctness, scientific relevance, privacy approval, model quality or
human review. Regression tests use stubs; replaying reference values through
sanitization is not an AI inference result.

## Next activation step

The new pack stays `DRAFT_NOT_APPROVED`, with no reviewers recorded and privacy
`NOT_DECIDED`. Existing owner confirmations cover the previous software corpus,
not this newly authored guide. Do not copy those confirmations into this pack.
The owner can review this pack for an internal demo; no external lab is required
for that demo. Any resulting report must preserve its synthetic/non-independent
scope. The scorer's reviewed-real-evaluation modes reject synthetic fixtures;
do not remove `synthetic_fixture` just to obtain a stronger report label.

After review: choose a provider and data policy, make a new versioned manifest,
then build a development output collector and compare manual template, the same
LLM without retrieval, and LLM with RAG. Until then metrics are `NOT_MEASURED`.

A separate real scientific-protocol pack still needs appropriate approved
development sources, protocol inputs and human-reviewed references. This
synthetic pack must not be presented as having completed that step.

`HELDOUT_STATUS = LOCKED_NOT_RUN`.
