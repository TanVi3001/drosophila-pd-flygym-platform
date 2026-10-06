# AI V2 A09 — End-to-end acceptance and regression gate

**Status:** `PASS_SYNTHETIC_API_CONTRACTS`

No formal A09 specification was present in the checked-out roadmap. This
scoped A09 hardens the A08/A07 handoff with HTTP/ASGI-level contract tests and
an explicit reproducible acceptance command. It qualifies software behavior,
not AI quality or biology.

## Automated acceptance path

`tests/test_workbench_v2_review_ui.py` checks that:

- the local UI exposes draft, checksum review, human promotion, support
  assessment, separate run approval, job submission/run, and report actions;
- requesting a draft creates no study;
- the saved snapshot checksum is used for promotion;
- promotion creates no jobs and starts no simulation;
- the support preflight is present after promotion, but job submission is still
  rejected until a separate human run approval is recorded;
- a synthetic fixture can proceed through assessment, approval, submit, run,
  audit-chain verification, and provenance/QC report;
- a held-out promotion request is rejected before a study is created.

The test uses a small test-local ASGI request harness, so it exercises actual
FastAPI routes without adding an undeclared `TestClient` dependency. An initial
attempt to use the framework test client exposed that the installed Starlette
requires `httpx2`, which is not part of this project's declared test/workbench
extras. No runtime dependency was added just for tests.

## Reproduce

From the platform repository root in PowerShell, with the isolated Python 3.12
environment used for the workbench:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
$TestTemp = Join-Path 'E:\research-\external\ai_v2_test_runs' ('a08-a09-' + [guid]::NewGuid().ToString('N'))
& 'E:\research-\.venvs\workbench-repro-owner-312\Scripts\python.exe' -m pytest -q -rs -p no:cacheprovider --basetemp $TestTemp `
  tests/test_workbench_v2_review_ui.py `
  tests/test_workbench_v2_promotion.py `
  tests/test_workbench_v2_automation.py `
  tests/test_workbench_v2_offline_integration.py `
  tests/test_workbench_v2_evidence.py `
  tests/test_workbench_v2_evaluation.py `
  tests/test_workbench_v2_runtime.py `
  tests/test_workbench_api.py
```

Test data and temporary artifacts are directed outside the source tree. The
synthetic end-to-end fixtures are software acceptance cases only. They do not
count as an A05 real-provider run, independent human review, wet-lab validation,
or paper evidence.

## Remaining before calling V2 fully validated

- The owner team must supply an approved real A01 corpus and frozen
  development-only A05 question/reference bundle.
- The group must approve provider privacy/retention and then run/report A05; no
  real-model metrics are measured yet.
- A08 remains a local unauthenticated operator page, not a production UI.
- Rehearse on the eventual target runtime and real supported backend; synthetic
  fixtures do not establish deployment readiness.
- Continue to keep `HELDOUT_STATUS = LOCKED_NOT_RUN`; none of these tests reads or
  runs held-out cases.

**Readiness boundary:** Real A05 model-quality measurements and target-runtime
rehearsal remain pending.
