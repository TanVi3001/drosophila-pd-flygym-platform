# AI V2 A03 — Guarded workflow automation and artifact reporting

## Scope and current stage

A03 adds an opt-in workflow controller around the existing support-gated
Workbench service. It coordinates assessment, named human approval, screening
submission, bounded execution, explicit resume, and a report built from
Workbench-generated run/QC artifacts. It does not give an LLM tools, shell
access, mapping authority, or permission to alter a frozen study.

The initial `StudySpec` can be created through the existing researcher-facing
study route or the [A07 reviewed draft handoff](ai_v2_a07_reviewed_study_handoff.md).
Promotion requires a complete human-supplied design and records draft/mapping
lineage; the draft itself is never executable. A03 can also run with
no model provider and no evidence corpus. The workflow controller does not make
a live LLM request.

`HELDOUT_STATUS = LOCKED_NOT_RUN`

## Fixed API surface

When V2 is enabled with an external runtime root, the server exposes:

| Route | Purpose | Gate |
| --- | --- | --- |
| `GET /v2/workflows/{study_id}` | Current workflow state, job progress, allowed next operations | Read-only |
| `POST /v2/workflows/{study_id}/assess` | Run the existing capability/mapping assessment | Reassessment invalidates old approval |
| `POST /v2/workflows/{study_id}/approve` | Record explicit human approval | Non-empty reviewer required; AI cannot call it autonomously |
| `POST /v2/workflows/{study_id}/screening/submit` | Submit declared candidates and seeds | Frozen support assessment required; max 100 jobs |
| `POST /v2/workflows/{study_id}/screening/run` | Run only jobs in the persisted submission | Frozen support assessment required; timeout 0.01–3600 s |
| `POST /v2/workflows/{study_id}/screening/resume` | Resume explicitly named failed/cancelled jobs | Same study, current approval, explicit job IDs only |
| `GET /v2/workflows/{study_id}/report` | Create a report from checked service artifacts | Does not recompute metrics or QC |

The allowlist is fixed in code. There is no arbitrary tool name, shell command,
Python execution, free-form backend override, or LLM-controlled action plan.
Automatic retry count is always zero. A timeout requests cancellation; if a
worker is still stopping after the bounded cancellation grace period, the
status remains visible for operator recovery. Restarting a failed/cancelled job
requires the explicit resume route. Existing worker stale-job recovery remains
an operator action.

The status endpoint exposes counts for the persisted screening submission, so
an operator can poll progress without asking an LLM to infer process state.
The controller is synchronous and does not provide a live streaming UI.

## Provenance and privacy

Events are stored outside the source checkout at
`<runtime-root>/ai_v2/outputs/automation/workflow_events.jsonl`. Each event is
linked to the previous event by SHA-256 and the chain is checked before append.
Events record workflow transition, study/configuration/assessment/approval
hashes, job counts/statuses, timeout and safe error types. Raw prompts, protocol
text, configuration values, reviewer names, provider secrets, and raw exception
messages are not written to this event log; inputs needed for audit are
represented by hashes or counts.

Reports are immutable new JSON artifacts under
`<runtime-root>/ai_v2/outputs/automation/reports/<study-id>/`. They include the
frozen StudySpec hash, assessment and approval identities, job status, metrics
and QC as returned by the existing Workbench service, hashes of run manifests,
and the audit-chain head. They explicitly state that the workflow did not use
an LLM to execute, retrieve evidence for execution, compute metrics, or decide
QC. Report generation does not assert biological or wet-lab validity.

When the study was promoted through A07, the report also carries the original
draft lineage and corpus/prompt hashes. These identify the drafting input;
execution and metric calculation still use the approved StudySpec and backend.

V2 paths are only constructed by the server when
`FLY_WORKBENCH_V2_ENABLED=1` and the external runtime root is valid. With V2
disabled, the original V1 defaults and routes remain in place.

The API currently has no user authentication. The default server host is
loopback (`127.0.0.1`); do not expose the approval route to a network or treat
the supplied reviewer string as verified identity. A trusted researcher must
make the approval action in the controlled local environment. Authentication,
role-based authorization, and deployment hardening remain future work.

## Verification and limits

Synthetic fixture tests cover the guarded success path, a rejected submission
before approval, stale-approval invalidation, timeout/cancellation, explicit
resume, API opt-in, privacy-minimized audit output, audit-chain tamper
detection, and immutable report creation. These fixtures are software tests;
they are not Drosophila evidence, real model outputs, or a scientific
reproduction.

Still outstanding before calling A03 operationally validated:

- run the V2 server from the team's external runtime on the target machine;
- inspect a real operator workflow and report with a human reviewer;
- exercise cancellation/resume on each supported backend and document any
  backend-specific timeout behavior;
- link a human-approved A01 corpus and, separately, conduct A02 answer-quality
  and citation review;
- rehearse the A07 review/promotion route with the team's real approved inputs.

The existing V1 `/v1/.../screening/run` route remains available for backward
compatibility and is not governed by A03's timeout wrapper. Use the V2 route
when requiring the A03 timeout, event ledger, and resume/report workflow.
