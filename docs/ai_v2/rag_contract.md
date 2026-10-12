# Evidence-grounded RAG runtime contract

**Scope:** local retrieval and optional provider-backed protocol drafting on
owner-approved **development-only** material. This is an engineering/runtime
contract, not evidence of scientific accuracy, biological validity or wet-lab
utility.

## Runtime path

```text
Protocol question
  → local retrieval from frozen JSONL corpus
  → approved evidence excerpts + protocol text (only with explicit sharing approval)
  → provider returns JSON proposal
  → schema/forbidden-field/citation sanitization
  → persisted DRAFT_REQUIRES_RESEARCHER_REVIEW
  → existing human mapping selection, StudySpec, support, approval and run gates
```

Retrieval is deterministic lexical BM25-style ranking over the text in the
loaded corpus snapshot. It is local, has no web/search connector, and uses a
stable `(score desc, source_id, chunk_id)` tie break. This implementation is not
a semantic embedding index and does not update/train the provider model. It
cannot infer that a retrieved source is scientifically true.

## Frozen corpus package

The operator first prepares a UTF-8 JSONL file outside Git. Each row has exactly
these fields:

```json
{"source_id":"TEAM_APPROVED_SOURCE_1","citation":"Citation, section/page","chunk_id":"source:section:chunk-01","text":"Reviewed excerpt","provenance":"Local file checksum/review record","access_class":"DEVELOPMENT_INPUT"}
```

Allowed `access_class` values are `PUBLIC_UNLABELED` and `DEVELOPMENT_INPUT`.
Each source must be in the manifest allowlist and not in the denylist. Chunk
identity `(source_id, chunk_id)` must be unique. Unknown fields, duplicate JSON
keys, malformed rows, held-out partition, hash mismatch, and empty corpora fail
closed.

The strict manifest schema (`approved-evidence-corpus-1`) records:

- corpus ID, relative corpus filename, exact lowercase SHA-256;
- approved and denied source IDs;
- `partition = DEVELOPMENT`;
- explicit `owner_approved = true` and `outcome_free = true` attestations;
- reviewer identifier(s) and timezone-aware review timestamp;
- separate `provider_sharing_approved` and `protocol_text_sharing_approved` flags;
- when both sharing flags are true, the exact approved provider ID and full
  chat-completions endpoint.

Create and validate an immutable manifest (the command refuses to overwrite an
existing freeze):

```powershell
python scripts/create_rag_manifest.py `
  --corpus .workbench/evidence/approved-corpus.jsonl `
  --manifest .workbench/evidence/manifest-v1.json `
  --corpus-id team-approved-dev-corpus-v1 `
  --approved-source-id source-a `
  --denied-source-id sealed-or-outcome-bearing-source `
  --reviewed-by "reviewer-identifier" `
  --owner-approved `
  --outcome-free
```

This first command enables **local retrieval only**. For a remote provider, add
both `--provider-sharing-approved` and
`--protocol-text-sharing-approved`, plus `--approved-provider-id` and
`--approved-provider-endpoint`. The ID format for the bundled adapter is
`openai-compatible:<model>`; the endpoint must exactly match the configured
runtime endpoint. A change of model or endpoint requires a newly reviewed,
versioned manifest. Do not grant these flags until the team has decided which
corpus text and protocol text may leave the machine and under which provider's
retention/privacy terms.

The manifest utility verifies structure, partition, allow/deny lists and exact
hash. It **cannot** detect every outcome-bearing sentence, infer privacy rights,
or decide whether an excerpt is scientifically appropriate. The reviewer
attestations are human decisions, not machine validation. Never put held-out or
sealed external labels into the corpus. `DEVELOPMENT` and `outcome_free` are
required, but no software flag can make an incorrectly curated corpus safe.

## API and behavior

- `GET /v1/ai/rag/status`: reports disabled/retrieval readiness, corpus hash,
  chunk count, provider configuration and sharing-gate state. It does not expose
  a provider secret.
- `POST /v1/ai/rag/retrieve` with `{"query":"...","k":5}`: local search only;
  response includes matched excerpts and states `provider_called: false`.
- `POST /v1/ai/rag/draft` with `protocol_text`, optional `source_uri`, and `k`:
  retrieves first, then requires both sharing flags, a configured provider, and
  an exact provider ID/endpoint match before making a network call.
- A no-hit query returns `ABSTAINED_NO_EVIDENCE` without calling a provider.
- Unsupported model citations are removed; returned citations are reconstructed
  from exact retrieved `(source_id, chunk_id)` pairs, never accepted as arbitrary
  URLs or model-invented references.
- Output remains `DRAFT_REQUIRES_RESEARCHER_REVIEW`; `approved`,
  `study_created`, and `mapping_created` remain false. AI cannot create neuron
  IDs/mappings, choose interventions or backends, approve a study, or run jobs.
- The old ungrounded `/v1/protocol-intake/draft` route is disabled by default.
  A separate explicit `WORKBENCH_ALLOW_UNGROUNDED_INTAKE=true` setting is an
  exceptional compatibility escape hatch and should remain false for the RAG
  workflow.

Retrieval logs record UTC time, query SHA-256 (not the query text), rank,
source/chunk/citation, score and corpus identity. Draft artifacts retain the
retrieved excerpts and sanitized output so reviewers can audit what the model
saw. API keys remain environment-only and are never included in artifacts.
Provider requests use HTTPS except for loopback development endpoints, have a
60-second default timeout, an 8 MiB request cap and a 2 MiB response cap.

## Readiness and claims

The runtime code has synthetic tests for checksum tampering, invalid partition,
allow/deny behavior, access class, deterministic ranking, no-evidence abstention,
sharing consent, provider identity binding, citation filtering, authenticated
API flow and persisted draft behavior. These are software contract tests—not a
human-gold RAG quality evaluation.

No real corpus was supplied or approved in this change, and no hosted provider
was called. Consequently `Recall@K`, `Precision@K`, citation precision, required
field accuracy, unsupported-claim rate, provider reliability and any comparative
AI-quality metric remain **NOT MEASURED**. Those require a frozen development
question set, human reference answers/rubric, privacy decision and retained real
provider outputs. External/biological validation remains separate.

```yaml
AI_RAG_RUNTIME: IMPLEMENTED
REAL_APPROVED_CORPUS: NOT_CONFIGURED
REAL_PROVIDER_CALL: NOT_RUN
AI_QUALITY_METRICS: NOT_MEASURED
HELDOUT_STATUS: LOCKED_NOT_RUN
BIOLOGICAL_VALIDATION: NOT_DONE
```
