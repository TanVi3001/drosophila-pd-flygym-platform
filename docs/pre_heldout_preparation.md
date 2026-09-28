# PRE-HELDOUT preparation — Fly Research Workbench

**Recorded:** 2026-09-28

**Working branch:** `feature/workbench-state4-review`

**Final evaluation:** `HELDOUT_STATUS = LOCKED_NOT_RUN`

This is the working guide for tasks that can proceed while the independent
operator run is pending. The authoritative scientific scope and score remain
[`active_manuscript_scope.yaml`](../configs/workbench/active_manuscript_scope.yaml)
and [`shiu_workbench_score_v1.json`](../configs/workbench/shiu_workbench_score_v1.json).
This document is not a gate approval or a substitute for run artifacts.

## Current evidence

- The public Shiu Table 3 registry contains 106 source-row cases, split into
  74 development and 32 held-out cases. Registry integrity and protocol freeze
  are recorded as passing in the active scope. No held-out labels were used in
  preparing this document.
- The degree-preserving-rewire LIF batch has a frozen score for 106 cases. Its
  98 zero scores represent silent computational readouts under the declared
  protocol, not biological negative findings.
- The 74-case development ablation is complete. Average precision is 0.659
  for rewire effect-only, 0.626 for the locked full Workbench score, and 0.248
  for the seeded random reference. Precision@5 is 0.800, 0.800, and 0.400,
  respectively. These are development results only. Evidence and capability
  gates do not vary in this dataset, so their incremental ranking benefit is
  not identified here.
- The owner reported exact development-output reproduction plus `PASS` for a
  technical success/failure subset. The verifier recorded `same_operator` and
  `independent_operator_claim_eligible=False`. An independent artifact review
  remains a separate gate.
- The current active scope records independent second-operator reproduction
  as pending and the final held-out comparison as ready but not run.

The dated [Methods/Results draft](workbench_state4_methods_results_draft_20260924.md)
contains the development analysis. The [status checklist](pre_heldout_status.md)
distinguishes owner-reported evidence from evidence inspected in this update.

## Work allowed while Tuấn prepares the independent run

1. Improve the user guide, architecture, Methods, failure-state reporting,
   provenance explanation, and manuscript figures generated from development
   or synthetic data.
2. Run synthetic unit/contract tests for score construction, freeze logic,
   reproduction, and artifact integrity. Fix demonstrated software defects
   without altering scientific constants or frozen inputs.
3. Prepare a portable handoff with exact source commits, two Python 3.12
   lockfiles, frozen public-input locators, SHA-256 checksums, commands, and
   expected validation fields. Verify that the commits are reachable on the
   review branch before giving the package to the operator.
4. Draft future Parkinson-related case-study questions and assay criteria in
   a separate planning document. This is prospective planning, not an active
   benchmark result or disease-model validation.
5. Improve reports that display job status, source revision, input/artifact
   hashes, QC decisions, paired metrics, uncertainty, exclusions, and human
   review state. Keep report generation independent of held-out labels.

The current research-study workflow is documented in
[`workbench/evidence_gated_prioritization.md`](workbench/evidence_gated_prioritization.md).
The paper-facing flow and the distinct validation claims are in
[`pre_heldout_methods.md`](pre_heldout_methods.md).

## Second-operator handoff and acceptance

Tuấn's task is a fresh checkout and clean Python 3.12 reproduction of the
74-case development analysis and a technical subset containing both a success
case and a controlled failure/QC case. The handoff must supply frozen inputs
and hashes; it must not rely on the owner's virtual environment. The
[`reproduction protocol`](workbench_reproduction_protocol.md) and
[`reproduction kit`](workbench_reproduction_kit_20260924.md) are starting
points, but their dated commit references must be refreshed against the
actual pushed review-branch commits before use.

The owner reviews the returned environment record, checkout status, input
hashes, manifests, provenance, metrics, explicit failure state, verifier
output, and discrepancies. A `PASS` string alone is insufficient. The gate
remains pending until an actual separate human run is reviewed and accepted.

## Condition for opening final held-out evaluation

The final 32-case evaluation may be considered only after the independent
operator gate is accepted, the protocol/score/evaluator and comparison systems
are frozen, required scientific case review is resolved for the intended
claim, and an explicit owner decision authorizes the final run. The final
evaluation is one planned run with the locked score and common assessable
denominator. Any later change requires a separately declared study; the same
32 cases cannot be reused as a fresh held-out set after tuning.

## Prohibited before the gate

- Running final held-out evaluation or inspecting held-out labels/case outcomes.
- Changing the held-out split, locked score formula, `k=5`, thresholds or
  weights based on held-out information.
- Editing frozen benchmark artifacts to make a test pass.
- Converting model silence or an unassessable case into a biological negative.
- Claiming biological, Parkinson, wet-lab, or prospective validation from the
  current computational evidence.

## Safe test command

Run from the FlyGym repository in **PowerShell** with a Python 3.12
environment. Use a fresh temporary directory on drive E. These four test
modules create synthetic fixtures; they do not load the real held-out registry.

```powershell
$Python = 'E:\research-\.venvs\baseline-2024-312\Scripts\python.exe'
$TempRoot = 'E:\research-\.tmp'
New-Item -ItemType Directory -Path $TempRoot -Force | Out-Null
$TestTemp = Join-Path $TempRoot ('pre_heldout_' + [guid]::NewGuid().ToString('N'))
& $Python -m pytest -q -rs -p no:cacheprovider --basetemp $TestTemp `
  tests/test_workbench_score_lock.py `
  tests/test_freeze_shiu_v2_rewired_lif_batch.py `
  tests/test_workbench_reproduction.py `
  tests/test_workbench_reproduction_artifact_integrity.py
```

The command verifies software contracts, not a new simulation, independent
operator run, or scientific result.
