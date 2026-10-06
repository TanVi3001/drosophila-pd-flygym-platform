# AI V2 Runtime Isolation — A0 bootstrap (legacy filename)

## Purpose and boundary

A0 establishes a separate, opt-in runtime boundary for AI V2 while preserving
the existing V1 server defaults and intake endpoint. The first V2 operation is
deliberately small: read protocol text through an explicitly configured intake
provider and write a sanitized `DRAFT_REQUIRES_RESEARCHER_REVIEW` artifact.

This legacy intake path does not load a connectome, retrieve from a corpus,
create a biological mapping, create a StudySpec, approve anything, or start a simulation.
The response records `graph_used=false`, `simulation_started=false`, and
`approval_granted=false`. Its retrieval mode is `NOT_USED_BY_LEGACY_INTAKE`.
Offline evidence retrieval and evidence-grounded StudySpec drafting are documented
in `ai_v2_a01_evidence_retrieval.md` and `ai_v2_a02_study_spec_draft.md`.

## Runtime layout

When V2 is enabled, `FLY_WORKBENCH_V2_RUNTIME_ROOT` must be an absolute path
outside and non-overlapping with the source checkout. The current layout is:

```text
<runtime-root>/
  workbench/
    state/workbench.sqlite3
    artifacts/
  backups/workbench_database/
  ai_v2/
    config/
    corpus/
    prompts/
    cache/
    outputs/drafts/
```

The directories are created only after explicit V2 opt-in and server start, or
when the layout's `prepare()` method is called. When V2 is disabled, the
existing relative defaults remain `.workbench/workbench.sqlite3` and
`.workbench/artifacts`. Enabling V2 does not migrate or restore an existing
database; database backup and restore are separate explicit operations.

## Windows PowerShell launch

Run from the platform repository root. Choose an external folder that is not
inside the checkout. The model provider is optional; without its V2-specific
settings the V2 draft route returns a service-unavailable response.

```powershell
$env:PYTHONPATH = "$PWD\src"
$env:FLY_WORKBENCH_V2_ENABLED = "1"
$env:FLY_WORKBENCH_V2_RUNTIME_ROOT = "E:\fly-research-runtime"

python -m drosophila_pd.workbench.server `
  --v2-intake-base-url "https://YOUR-APPROVED-ENDPOINT/v1" `
  --v2-intake-model "YOUR-MODEL"
```

If the provider needs a key, set its environment-variable name with
`--v2-intake-api-key-env`; keep the secret itself in that environment variable,
not in source code or this document. V1 provider settings remain separate under
`--intake-*`.

The V2 endpoint is `POST /v2/protocol-intake/draft`, with JSON such as:

```json
{
  "protocol_text": "Protocol text for an unapproved draft",
  "source_uri": "https://example.org/protocol"
}
```

Draft JSON is written under `<runtime-root>/ai_v2/outputs/drafts/`. The raw
protocol text is sent to the configured provider but is not copied into that
artifact; the artifact stores a SHA-256 source digest and sanitized proposals.
Choose a provider endpoint only after reviewing its data-handling terms.

## Database safety helpers

`drosophila_pd.workbench.runtime_storage.create_sqlite_backup(source, dest)`
uses SQLite's online backup API, checks integrity, computes SHA-256, and refuses
to overwrite an existing destination. `restore_sqlite_backup(backup, dest,
expected_sha256=...)` checks the digest and database integrity before writing to
a new destination; it also refuses to overwrite. These helpers do not run
automatically, do not touch any user's existing database, and do not claim to
recover a database for which no backup exists.

## A0 verification scope and remaining work

The accompanying tests cover opt-in/path validation, unchanged V1 defaults,
the graph-free V2 draft contract, API separation, and backup/restore behavior
using temporary databases and fixture providers. They do not run a model,
benchmark, held-out evaluation, or biological experiment.

```text
HELDOUT_STATUS = LOCKED_NOT_RUN
```

This file is named for the original bootstrap task; it is not the specification
for current A01/A02. A01/A02 now have offline retrieval and guarded draft
infrastructure, but there is no real approved corpus configured in this checkout.
Prompt review UI, LLM quality/safety evaluation against a human rubric, cache
semantics, graph-model integration, multimodal feature fusion, candidate ranking,
and AI V2 comparison against baselines remain later, separate tasks.
