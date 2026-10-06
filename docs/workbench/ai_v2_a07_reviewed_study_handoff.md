# AI V2 A07 — Reviewed draft-to-study handoff

Status on 2026-10-06: `IMPLEMENTED_SYNTHETIC_END_TO_END_VERIFIED`.

## Working pipeline

Question → A01 approved evidence → A02 non-executable draft → researcher review
and complete design → registered mapping selection → support-gated StudySpec
→ capability/mapping/backend preflight → separate run approval → A03 screening
→ manifest/QC → report with draft lineage.

A04/A05 remain the development evaluation track for retrieval and draft
quality. A07 does not run those scientific evaluations or held-out cases.

## Handoff contract

1. `POST /v2/study-spec/draft` creates the isolated A02 draft as before.
2. `GET /v2/study-spec/drafts/{draft_id}` returns the saved draft and SHA-256 of
   the exact stored bytes. It reads only an ID in the configured draft directory;
   caller-supplied file paths and symlink escapes are rejected.
3. The researcher reviews that snapshot and explicitly supplies the **complete
   final study**. Nothing executable is copied automatically from the model.
4. `POST /v2/study-spec/drafts/{draft_id}/promote` checks the snapshot digest,
   current draft schema, evidence-backed status, loaded corpus identity, explicit
   review decision and final design. The declared split must be `development`
   or `synthetic_fixture`.
5. The endpoint creates a support-gated study and performs backend preflight.
   `PROMOTED_REQUIRES_RUN_APPROVAL` means design handoff succeeded.
   `PROMOTED_BLOCKED_BY_SUPPORT_GATE` means a recorded study failed backend
   preflight and cannot be approved/run. The response includes the reasons.
6. Use the existing A03 approval/submission/run/report endpoints to proceed.
   Promotion itself creates no job and starts no simulation.

The promotion request has exactly these keys:

```json
{
  "expected_draft_sha256": "<digest returned by GET>",
  "reviewer": "<person submitting the reviewed design>",
  "review_decision": "APPROVED",
  "evaluation_split": "development",
  "study": {}
}
```

Replace `study` with the complete reviewed StudySpec object. Required keys are
`study_id`, `name`, `hypothesis`, `falsifiable_prediction`, `assay`,
`primary_metric`, `backend`, `candidates`, `controls`, `run_plan`, `metadata`.
Optional root keys are `sources` and `created_at`.

Each candidate has an explicit `intervention.type`. Non-control candidates
must identify an existing reviewed mapping in `metadata.mapping_id`; backend,
target, intervention, dataset, namespace and declared context must agree with
the registry. `controls` explicitly references every candidate with
`intervention.type=none`. Supply the human-confirmed unit in
`metadata.primary_metric_unit`, plus backend requirements and execution settings
in `run_plan`. The existing known Hz identifier check rejects obvious unit
mismatches; it is not a universal biological unit validator.

The caller's reviewer name/decision are recorded as an attestation. This local
API does not authenticate that person's identity or establish independent
review. Production identity/authorization belongs to the deployment work.

## Provenance and revisions

The final study stores `metadata.ai_draft_lineage`: draft ID/hash, question hash,
corpus/prompt/provider identity, original draft citation records, reviewer
attestation, reviewed design hash, edited/completed field names and selected
mapping hashes. Original draft citations remain explicitly identified as draft
citations; they do not prove an edited final claim is supported semantically.
Neither the original draft nor the mapping registry is changed by promotion.

A03 reports now carry this lineage and the drafting corpus/prompt hashes.
Simulation/QC metrics still come from the backend and existing assay code.

Study IDs are immutable. A revised design must use a new `study_id`, be assessed
again and receive its own run approval. Approval for the old unchanged design
does not transfer to the revision. Screening job IDs now include study,
candidate and seed identity so two studies can use the same names/seeds without
colliding. Previously persisted legacy job IDs are reused for the same study;
resubmission remains idempotent.

## Reproducible local demonstration

From the platform repository root, run in PowerShell:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
& 'E:\research-\.venvs\workbench-repro-owner-312\Scripts\python.exe' `
  scripts/run_workbench_v2_review_demo.py `
  --runtime-root 'E:\research-\external\workbench_ai_v2_a07'
```

The interpreter path is specific to this machine; another installation can use
its Python 3.12 environment with the project's test/workbench dependencies.
Each invocation creates a new external `a07-demo-<random-id>` directory with a
separate SQLite database, synthetic corpus, drafts, manifests, event log,
report and `demo_summary.json`. It does not overwrite an existing runtime.
The demo's fake reviewer and generator are explicitly synthetic test fixtures.

The verified demonstration completed 2/2 fixture jobs (control and condition),
2/2 finite-readout QC checks and a valid audit chain. The backend writes chosen
fixture values 0 and 1 to exercise reporting. They are not Drosophila simulation
measurements, real model quality results or biological validation evidence.

## Verification

`tests/test_workbench_v2_promotion.py` covers successful handoff/run/report;
separate approval; missing evidence/reviewer/control/unit/run plan; unknown or
pending mapping; unsupported assay; altered draft/corpus; path rejection;
backend target-ID conflict; frozen-parameter override; revised-study approval;
two-study job isolation; legacy job reuse; failure/QC reporting; API opt-in.

Tests use isolated external fixture runtimes. A05 still requires a real approved
corpus, frozen development questions/references, provider/privacy decision and
an actual internal evaluation run. A07 has API and console integration; a new
visual review interface and rehearsal on the team's production runtime remain
unverified.

On 2026-10-06, the focused V2/service/support/seed/API/store regression suite
passed **105 tests, 0 skipped**, including the **24 A07 tests**, using the
isolated workbench Python 3.12 environment. The first test invocation failed
because the selected external temporary-directory parent did not exist; it was
created and the tests rerun. The two-study test then reproduced a job-ID
collision, which was fixed with study-scoped IDs and legacy reuse before the
passing regression run.

`HELDOUT_STATUS = LOCKED_NOT_RUN`.
