# Development AI output collector

## What is implemented

`scripts/collect_ai_v2_outputs.py` runs cases sequentially against the existing
Workbench API and preserves output immediately for every case. It is a
collector, not a scorer, model judge, simulation runner or approval utility.
The existing evaluator is unchanged.

| Mode | Accepted input | Requests |
| --- | --- | --- |
| `retrieval-only` (default) | Software-policy questions or protocol text, DEVELOPMENT only | RAG status + retrieval; never draft/provider |
| `rag-draft` | Reviewed protocol-extraction snapshot with explicit data policy and matching runtime manifest | Status + retrieval + draft; no StudySpec, approval or job endpoint |

Policy questions cannot use `rag-draft`: the protocol endpoint does not emit
their policy-answer fields. Original corpus, rubric, approved manifests,
Docker configuration, reviewer records and sharing flags are never edited.

Each run must have a **new** output directory. An existing directory is refused
before any API request; there is no overwrite or resume flag. Output must also
be outside corpus/reference/manifest package directories. Case IDs are checked
for Windows reserved names and case-insensitive filename collisions. No automatic retry
is made: a draft request can have persisted an artifact or called the provider
before a timeout reaches the client.

## Run the existing 12 software-policy questions

Use the same PowerShell session that holds the staging token. Do not print the
token, paste it into chat or put it in an argument/config file. These commands
do not enable a provider and need no Docker rebuild for the collector itself.

```powershell
Set-Location 'E:\research-\.workbench\ai-v2-dev'
$taskPython = 'E:\research-\.venvs\ai-v2-staging-312\Scripts\python.exe'

# Checks input hashes/types/k only; no network requests or output files.
& $taskPython scripts/collect_ai_v2_outputs.py `
  --corpus .workbench/evidence/rag_development_corpus_draft.jsonl `
  --rubric .workbench/evidence/ai_v2_development_questions_rubric_draft.json `
  --mode retrieval-only --dry-run

# True means the current shell still has a token; its value is never printed.
(-not [string]::IsNullOrWhiteSpace($env:WORKBENCH_API_TOKEN))

$taskRunDir = Join-Path '.workbench/ai-v2-collections' `
  ('retrieval-' + [DateTimeOffset]::UtcNow.ToString('yyyyMMddTHHmmssfffZ'))
& $taskPython scripts/collect_ai_v2_outputs.py `
  --corpus .workbench/evidence/rag_development_corpus_draft.jsonl `
  --rubric .workbench/evidence/ai_v2_development_questions_rubric_draft.json `
  --output-dir $taskRunDir --mode retrieval-only `
  --base-url http://127.0.0.1:8000

Get-Content -Encoding UTF8 -LiteralPath (Join-Path $taskRunDir 'run_manifest.json')
```

Before batch requests, `/v1/ai/rag/status` must report readiness and a corpus hash
matching the reference. The runtime manifest identity observed at preflight is
pinned for the entire run. Supply `--manifest path/to/existing-manifest.json` or
`--expected-manifest-sha256 <known-hash>` to pin an independently known manifest
as well. A corpus mismatch is BLOCKED, never bypassed by editing expected hashes.

If the token is absent or stale, restore it through the staging setup procedure;
401 is an authentication failure, not a failed AI answer. The token environment
name defaults to `WORKBENCH_API_TOKEN` and can be changed with `--api-token-env`.

## New protocol pack

Local dry-run of the new synthetic pack is available now:

```powershell
& $taskPython scripts/collect_ai_v2_outputs.py `
  --corpus .workbench/evidence/protocol_draft_development_v1/protocol_development_corpus_draft.jsonl `
  --rubric .workbench/evidence/protocol_draft_development_v1/protocol_development_rubric_draft.json `
  --mode retrieval-only --dry-run
```

The running software-doc corpus is different from this six-chunk corpus. A live
batch against the wrong mounted corpus must fail identity preflight. Do not
change Docker mounts or construct an approval merely to make this check pass.

`rag-draft` activation is deliberately separate. It requires:

1. A **new** reviewed reference snapshot (`ai-v2-assistant-reference-reviewed-1`,
   `status=APPROVED`, named reviewer IDs), preserving protocol cases and frozen
   references. One owner is sufficient for internal collection; this records no
   independent review claim. Keep the original draft unchanged.
2. Its `privacy_decision.status=APPROVED`, both corpus/protocol sharing flags true,
   and the exact reviewed provider ID and endpoint. These attestations are human
   decisions; copying metadata does not perform a review or grant data rights.
3. `--manifest` pointing to the actual reviewed runtime manifest. The existing
   loader verifies it, and corpus/hash/provider/endpoint/sharing approvals must
   match the reference. The loader is not called to approve or create anything.
4. Explicit `--allow-provider-calls` and a runtime reporting `provider_ready=true`.
   Credentials for the model remain server-side, not in collector arguments.

After those decisions, the command shape is:

```powershell
# Placeholders below are not existing approvals; use actual reviewed files.
& $taskPython scripts/collect_ai_v2_outputs.py `
  --corpus '<reviewed-corpus.jsonl>' `
  --rubric '<new-reviewed-protocol-reference.json>' `
  --manifest '<matching-reviewed-runtime-manifest.json>' `
  --output-dir '<new-local-run-directory>' `
  --mode rag-draft --allow-provider-calls
```

A new reference is not approved by this implementation task. Never change the
original `DRAFT_NOT_APPROVED` or clear `synthetic_fixture` to bypass gates.
Synthetic protocol results stay synthetic even when a real model produces them.

## Artifacts and interpretation

```text
new-run/
  run_config.json          initial configuration; IN_PROGRESS
  runtime_status.json     readiness snapshot, if received
  cases/CASE_ID.json       one record per case, including errors/not-run cases
  case_outputs.json       aggregate raw records
  run_manifest.json        final status, counts, timestamps and artifact hashes
```

Each case retains input SHA-256, retrieved evidence, the returned draft,
citations, missing fields, errors, stage/total elapsed seconds, UTC timestamps,
corpus/manifest/rubric hashes and observed provider/model/prompt identities.
Retrieval-only records have no draft, no generation identities and no evaluator
projection. They do not claim the software-policy answer has been generated.
The draft's own retrieved evidence is authoritative for generation; the earlier
retrieval response is retained separately because the draft endpoint retrieves
again. Actual draft latency includes that second retrieval and server work.

`run_manifest.json` pins collector source bytes and hashes all preceding artifact
files. It does not hash itself. Missing final manifest means the run did not
finalize (for example interruption/disk failure); existing records remain for
diagnosis and must not be treated as a completed run.

| Case status | Meaning |
| --- | --- |
| `RETRIEVED` | Retrieval returned evidence; semantic answerability not established |
| `NO_MATCH` | Retrieval-only response had no hits |
| `DRAFT_COLLECTED` | Supported runtime draft envelope captured; human review still needed |
| `ABSTAINED_NO_EVIDENCE` | Actual draft endpoint returned the no-evidence branch |
| `ERROR` | Attempt failed, timed out, drifted or violated the draft contract |
| `NOT_RUN` | Preflight blocked or a prior fatal drift/auth failure stopped later requests |

`provider_called` is false before a draft request, true when successful draft
provenance confirms generation, and unknown (`null`) when a draft attempt failed
without reliable confirmation. A timeout must not become `ABSTAINED` or count
as a confirmed absence of provider work. Status counts always include all cases.
Model/prompt/provider identity changes between successful cases stop later
requests and are recorded as version drift.

The optional `evaluator_projection` maps successful drafts to `COMPLETED` and
runtime no-evidence abstentions to `ABSTAINED`, preserving fields/evidence/
citations/missing fields. It does **not** manufacture human `claim_reviews`, gold
answers or comparator outputs. Failed cases have no projection. Do not drop them
from the denominator or convert them to abstentions to satisfy the existing
scorer; a final evaluation needs an explicit failure-scoring policy and all
required comparator outputs. No automatic scoring occurs here.

CLI exit codes: 0 = complete collection or valid dry-run; 1 = recorded blocked
or partial run; 2 = input/config/storage error. HTTP failure bodies and auth
headers are not persisted; known tokens, credential keys and common token
patterns are redacted. This is not a comprehensive sensitive-data detector.
Artifacts contain development excerpts/drafts and stay local/Git-ignored.

Remote Workbench calls are disabled by default. `--allow-remote-workbench` permits
an explicitly selected HTTPS origin, not arbitrary tool endpoints. Redirects are
disabled, responses capped at 8 MiB and request timeout at 60 seconds maximum
(30 seconds default). The allowed routes never include approval or jobs.

## Verification and remaining work

Tests cover input/approval/privacy/identity gates, safe paths, retrieval-only
behavior, errors versus abstentions, drift, redaction, transport bounds and a
12-case batch through the actual Workbench API with an in-process **stub**
provider. No hosted provider or production deployment is validated by those
tests. The existing evaluator/benchmarks are not changed.

For memory-constrained Windows test runs, use `OPENBLAS_NUM_THREADS=1` in the
test process: existing package imports initialize NumPy even for structural
audits. The standalone collector defaults its own client process to one BLAS
thread when the operator has not set that variable. It does not reconfigure the
running API server, LLM provider or simulator.

See [real provider setup](real_provider_setup.md) for the proposed Gemini
configuration, exact outbound-data scope and the pending owner decisions.
It does not activate a provider or approve the new synthetic pack.

The [three-arm protocol experiment](protocol_comparison.md) now implements
manual import, paired same-provider generation and failure-aware reporting in
a separate in-process harness. It does not activate staging or manufacture
manual answers/human support annotations. No real-provider comparison is
established by those implementation tests.

Next: actual owner reference/data-policy decisions and matching runtime setup;
then retain real outputs, fill the manual comparator, and supply bound human
claim annotations for support metrics. No biological or wet-lab validity
follows from collector success.

`HELDOUT_STATUS = LOCKED_NOT_RUN`.
