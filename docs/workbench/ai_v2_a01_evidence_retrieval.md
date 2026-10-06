# AI V2 A01 — Approved evidence corpus and offline retrieval

## What this task provides

A01 adds a standard-library-only, deterministic lexical retriever for an
explicitly approved evidence corpus. It does not crawl websites, read Notion,
index every paper, or access benchmark outcome files. Retrieval is available at
`POST /v2/evidence/retrieve`; the separate A02 draft endpoint consumes the same
retriever. The corpus is loaded only when V2 is explicitly enabled and its
configured SHA-256 matches.

`HELDOUT_STATUS = LOCKED_NOT_RUN`

## Corpus contract

The one configured file must be named `corpus.json` and live inside
`<runtime-root>/ai_v2/corpus/`. A reviewer must approve each source and review
each chunk for blind-evaluation leakage before loading. The exact JSON schema is
enforced by `ApprovedEvidenceCorpus.load` (unknown and missing fields fail
closed):

```json
{
  "schema_version": "fly-workbench-approved-evidence-1",
  "corpus_id": "reviewed-corpus-identifier",
  "corpus_version": "1",
  "sources": [{
    "source_id": "opaque-source-id",
    "citation": "Full bibliographic citation",
    "source_uri": "https://doi.org/...",
    "dataset_version": "dataset/model version or explicit not-applicable note",
    "evidence_tier": "PRIMARY",
    "source_sha256": "64-character digest of the reviewed original source file",
    "review_status": "APPROVED",
    "reviewer": "Named source reviewer",
    "reviewed_at": "2026-10-06T10:00:00Z",
    "approval_record_id": "opaque-review-record-id",
    "blind_use": "ELIGIBLE",
    "chunks": [{
      "chunk_id": "opaque-chunk-id",
      "locator": "Methods, section 2, paragraph 3",
      "evidence_scope": "methods",
      "text": "Only the approved excerpt, without benchmark outcome labels.",
      "text_sha256": "64-character digest of exact UTF-8 chunk text",
      "access_class": "PUBLIC_UNLABELED",
      "blind_review_status": "PASS",
      "blind_reviewer": "Named leakage reviewer",
      "blind_reviewed_at": "2026-10-06T10:00:00Z"
    }]
  }]
}
```

Allowed evidence scopes are `assay_definition`, `dataset_identity`,
`mapping_context`, `methods`, and `model_capability`. Outcome, response, phenotype,
expected-direction and benchmark-label fields are not part of the schema. A
source with `blind_use=NOT_FOR_BLIND_EVALUATION` is excluded entirely; this runtime
has no per-query blind-use filter. Every chunk must be `PUBLIC_UNLABELED`, hash-correct,
and explicitly pass its blind-use review. Outcome-like identifiers are rejected.
This is an access-control and
metadata contract; software cannot prove that human-authored prose contains no
subtle biological leakage. The named reviewer attestation remains necessary.

Notion remains a catalog and review-decision store. A “source checked” or “paper
read” status is not an A01 corpus approval. Until a source has an explicit
approval record and chunk-level leakage review, it must not be copied into the
active corpus. This repository intentionally does not ship an approved corpus
or promote current Notion rows into one.

## Retrieval and audit behavior

- Normalizes Unicode/case, tokenizes terms, and scores the fraction of unique
  query terms present in chunk text/citation/locator.
- Returns positive-overlap chunks only, ordered by descending score then
  opaque chunk ID; this is a baseline retriever, not semantic search.
- Returns `NO_APPROVED_EVIDENCE` with an empty evidence list when nothing
  matches; A02 then skips the model call and reports required fields as missing.
- Logs UTC time, query SHA-256 (not the question), corpus SHA-256, top-k,
  source/chunk IDs, citation/locator, evidence hashes and retrieval scores to
  `<runtime-root>/ai_v2/outputs/retrieval_audit.jsonl`.
- Rejects relative/out-of-root corpus paths, wrong file names, digest mismatch,
  unapproved sources, unsupported scopes, hash mismatch and non-approved access
  classes.

The audit log deliberately contains no raw question, protocol, prompt, or chunk
text. The retrieved API response includes approved chunk text for the caller.

## Configure on Windows PowerShell

First get a human-reviewed corpus from the project reviewers and put it at the
external runtime path; do not hand-edit it after computing its hash.

```powershell
$env:FLY_WORKBENCH_V2_ENABLED = "1"
$env:FLY_WORKBENCH_V2_RUNTIME_ROOT = "E:\fly-research-runtime"
$env:FLY_WORKBENCH_V2_CORPUS_PATH = "E:\fly-research-runtime\ai_v2\corpus\corpus.json"
$env:FLY_WORKBENCH_V2_CORPUS_SHA256 = "<SHA-256 of exact corpus.json bytes>"
```

The corpus path and digest must be supplied together. Startup rejects invalid
corpus data. If no corpus is configured, `/v2/evidence/retrieve` and the A02
draft endpoint return service unavailable; V1 remains unchanged.

Example request:

```json
{"question":"Which approved source specifies the MN9 readout?","top_k":5}
```

## Verification and limits

Automated fixture tests cover exact schema, source/chunk hashes, approval and
access-class rejection, path containment, deterministic retrieval, no-evidence
behavior, and audit redaction. Fixture approval values are synthetic test data;
they do not constitute scientific review or a production corpus. No live paper
corpus, embedding model, LLM provider, held-out data, or biological outcome was
used in these tests.
