# AI V2 Workbench — internal staging deployment

**Profile:** production-like internal test, not public production  
**Held-out:** `LOCKED_NOT_RUN`  
**Provider:** disabled unless deliberately configured

## What this deployment is for

This container packages the existing Workbench API and browser interface with
the AI draft → reviewed mapping → human approval → job/report workflow. SQLite
state and run artifacts persist in a named Docker volume. A bearer token gates
all `/v1/*` routes; `/healthz`, `/readyz`, and the static landing page remain
public so a local operator and the container health check can reach them.

The container is deliberately bound to `127.0.0.1` on the host. It is intended
for the group to exercise the software frame on one machine. It is not hardened
for direct Internet exposure, multi-user identity, or wet-lab use. Simulation
outputs remain computational outputs, not biological validation.

Compose enables a clearly labeled synthetic backend and seeds one synthetic
mapping record. Those entries exist only to let the team click through the
workflow without biological data; their IDs and arbitrary output values must
not be interpreted as FlyWire neurons, MN9 responses, or experimental results.

## Start on Windows PowerShell

Docker Desktop must be running with its Linux container engine enabled. From the
repository root:

```powershell
$bytes = New-Object byte[] 32
$rng = New-Object System.Security.Cryptography.RNGCryptoServiceProvider
try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
$env:WORKBENCH_API_TOKEN = [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+','-').Replace('/','_')
docker compose -f compose.workbench-staging.yml up --build -d
docker compose -f compose.workbench-staging.yml ps
Invoke-RestMethod http://localhost:8000/healthz
Invoke-RestMethod http://localhost:8000/readyz
```

Open `http://localhost:8000`, paste the generated token into **Staging API
connection**, then click **Connect**. Keep the token in the current PowerShell
session; do not put it in Git, a notebook, a screenshot, or a committed `.env`
file. If another port is needed, set `$env:WORKBENCH_PORT` before Compose.

For the no-provider UI smoke test, use the prefilled **AI V2 workflow smoke
test — synthetic only** section: click **Resolve available mapping**, explicitly
choose the offered synthetic record, create the draft, enter a reviewer name,
then click approval, submit, and run as separate actions. The result/report is
tagged synthetic and only demonstrates that the software path works.

To inspect logs and stop the service without deleting persisted state:

```powershell
docker compose -f compose.workbench-staging.yml logs --tail 100 workbench
docker compose -f compose.workbench-staging.yml stop
```

`docker compose down` removes the container/network but keeps the named data
volume. **Do not use `down --volumes`** unless the group intentionally wants to
erase the staging database and artifacts.

## API workflow for an internal smoke test

1. `POST /v1/protocol-intake/draft` asks the configured intake provider for a
   proposal; it never creates an approved study. The provider is absent by
   default, so this call returns a clear not-configured error until the group
   explicitly supplies an endpoint/model and an approved secret source.
2. `POST /v1/ai/mappings/resolve` with an `AIStudySpec` draft and `candidate_id`
   returns exact compatible reviewed options. It never chooses one.
3. `POST /v1/ai/studies/draft` repeats resolution against the current registry,
   checks the human-supplied `mapping_id` + `version` + `record_hash`, binds only
   registry-owned IDs/readouts, and persists a DRAFT. Stale, ambiguous,
   unreviewed, or incompatible choices fail closed.
4. A researcher explicitly calls `POST /v1/ai/studies/{study_id}/approval`.
   Only after that can `POST /v1/ai/studies/{study_id}/jobs` submit a job.
5. `POST /v1/ai/jobs/{job_id}/run` is a separate action. Inspect the workflow,
   QC, report and run manifest through the existing `/v1` study/job endpoints.

Example protected read from PowerShell (the token is not written to disk):

```powershell
$headers = @{ Authorization = "Bearer $env:WORKBENCH_API_TOKEN" }
Invoke-RestMethod -Headers $headers http://localhost:8000/v1/capabilities
```

For all smoke tests, use only the synthetic fixture or clearly labeled
development inputs. Do not use the 32 held-out cases, sealed external labels,
or any result that would change a frozen benchmark. The built-in mapping is
fixture-only and carries no biological approval.

## Frozen RAG corpus and optional provider

The default deployment has no RAG corpus and no provider. Retrieval becomes
available only after the team curates a development-only JSONL corpus outside
Git and creates a checksum manifest with:

```powershell
New-Item -ItemType Directory -Force .workbench/evidence | Out-Null
python scripts/create_rag_manifest.py `
  --corpus .workbench/evidence/approved-corpus.jsonl `
  --manifest .workbench/evidence/manifest-v1.json `
  --corpus-id team-approved-dev-v1 `
  --approved-source-id source-a `
  --denied-source-id sealed-or-outcome-bearing-source `
  --reviewed-by "reviewer-identifier" `
  --owner-approved `
  --outcome-free
```

That enables local, deterministic retrieval only. It does **not** permit sending
the excerpts or a protocol to a provider. For any remote call, the team must
make the data-sharing decision first, then create a new versioned manifest with
both `--provider-sharing-approved` and
`--protocol-text-sharing-approved`, and bind it to the exact model and endpoint
using `--approved-provider-id` and `--approved-provider-endpoint`. See the
[RAG contract](rag_contract.md) for the exact JSONL fields and gate behavior.

To mount this package read-only in the staging container, put the corpus and
manifest in `.workbench/evidence` (or another private directory), then set:

```powershell
$env:WORKBENCH_RAG_HOST_DIR = (Resolve-Path ".workbench/evidence").Path
$env:WORKBENCH_RAG_MANIFEST = "/opt/workbench/evidence/manifest-v1.json"
```

If, and only if, the manifest binds the exact provider and explicitly approves
both data types, configure the provider in the current PowerShell session:

```powershell
$env:WORKBENCH_INTAKE_BASE_URL = "https://approved-provider.example/v1"
$env:WORKBENCH_INTAKE_MODEL = "approved-model"
$env:WORKBENCH_INTAKE_API_KEY_ENV = "WORKBENCH_LLM_KEY"
$env:WORKBENCH_LLM_KEY = "<load securely in your own shell; do not paste into chat>"
```

The manifest endpoint must equal the adapter's full endpoint (the base URL plus
`/chat/completions`, unless already present); provider ID is
`openai-compatible:<model>`. Start/recreate the container after changing
environment settings. `GET /v1/ai/rag/status` shows retrieval/provider readiness
without exposing credentials. The browser offers “Retrieve evidence only” so
the team can inspect matching excerpts without making any provider request.

Do not put protocol text, API keys, corpus files, manifests containing private
metadata, or retrieval artifacts into Git. The old ungrounded intake endpoint
is disabled by default; keep `WORKBENCH_ALLOW_UNGROUNDED_INTAKE=false`. Docker
administrators can inspect staging environment variables, so this is not a
production secret-manager design. Provider output remains an unapproved draft;
it cannot choose mappings, assign IDs, approve a StudySpec, or run a job.

## Before calling anything public production

This staging profile is **not** a public production release. A real production
deployment still needs at least: institution-approved hosting and data policy,
TLS/reverse proxy, individual identity and role-based authorization, secret
manager integration and rotation, backup/restore drills for SQLite and
artifacts, monitoring/alerting, request/rate limits, security review, and a
worker/resource-isolation design for computational jobs. Do not expose port
8000 to a public interface or replace the localhost-only Compose binding with
`0.0.0.0` on the host.

## Current readiness boundary

The staging package tests deployment mechanics and workflow contracts; it does
not finish scientific validation or AI-quality evaluation. The latter still
requires a team-approved development corpus, frozen question/gold/rubric set,
provider/privacy decision and retained model outputs. No held-out case has been
run by this deployment work.
