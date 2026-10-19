# Task05 — support recomputation review and integration

**COMPLETE for bounded engineering subset; independent review PENDING.**

## Scope and repository

Root `E:\research-\.workbench\ai-v2-dev`; branch `feature/evidence-audit-review`;
HEAD `03b91b598eb63a72840cacd9dd7bb5fed7ebd4b1`. Startup had no tracked
modifications; existing untracked documents, Task04 module/tests and unrelated
files preserved. No commit/push/reset/stash/branch switch or subagent.
Root AGENTS applies; no additional applicable instructions found. No scientific
rules, capability policy, evidence, reviews or frozen artifacts changed.

## Call path and fidelity (verified from code)

Paths below are relative to the repository root above.

1. `src/drosophila_pd/workbench/service.py:WorkbenchService.assess_support`
   reads study, adapter capability and store mappings; invokes production
   `support.py:assess_study_support`, then local adapter validation/preflight.
2. Opt-in keyword `decision_package_target` captures **that call's** capability,
   mappings, context, study and assessment, then uses existing
   `WorkbenchService.export_evidence_bundle` → `handoff.build_evidence_bundle`
   → `handoff.write_evidence_bundle`. It attaches
   `decision_package.export_sidecar`. No new top-level API or v2 schema change.
3. `decision_package.recompute` → `_load` (local integrity/identity closure)
   → `_validate` (bindings/profile) → `pure_modules` → the same production
   `support.assess_study_support` source, under a private namespace.

There is **no duplicated decision algorithm**. Adapter code changes representation
only; service preflight remains outside recomputation. Default export is untouched.
Opt-in supports fresh directories, engineering-only studies without jobs, READY
preflight or denied assessments with empty NOT_RUN preflight. FAILED preflight
cannot be represented and is explicitly rejected before bundle creation. Assessment
persistence occurs before this rejection, as on the ordinary service path.

Pure inputs: study/candidates/interventions/metadata/run-plan requirements, full
capability, mappings, explicit context. Production preflight also uses materialized
configs/adapter validation and possibly external inventories: those inputs/code are
**not captured/replayed**. Thus this is pure support fidelity, not full preflight
or backend reproducibility. No workspace fallback. Defaults are reconstructed by
the pinned models, with study configuration and mapping hashes checked. Capability
round-trip now rejects changed normalization. JSON fixtures preserve meaningful
values; exhaustive serialization coverage for arbitrary metadata is not established.

Identity pins bytes of models/support/decision_package plus Python version,
implementation, platform and pointer width; it does not pin service/adapter code
or prove authenticity. Packet hashes cover service source separately. Policy name
`support-pure-ready-fixture-1` is retained for Task04 compatibility; its implemented
profile now also permits the real service's denied NOT_RUN form. No historical
cross-version compatibility claim: exact code identity deliberately rejects it.

## Findings and dispositions

| ID / severity | Source / problem and consequence | Fix, evidence, remaining limitation |
|---|---|---|
| T05-F01 MAJOR | `service.py:assess_support/export_evidence_bundle`: Task04 sidecar was standalone, not production-integrated. | Added opt-in keyword seam at assessment time; S01/S02/S05 exercise actual service/store/v2 writer. HTTP/CLI/UI entry points not wired or tested. Task04 report already disclosed gap; no historical rewrite. |
| T05-F02 MAJOR | `decision_package.py:_validate`: capability input could differ from saved assessment capability with valid checksums. | Added normalization and assessment binding checks; altered capability rejected. Integrity still is not authenticity; wholesale rewritten snapshots are not authenticated. |
| T05-F03 MINOR | `decision_package.py:pure_modules`: path-only cache could run stale modules after disk changes while identity hashes new bytes. | Namespace now includes dependency byte digests; test observes new module after source edit. Concurrent mutation/hostile interpreter monkeypatching not covered. |
| T05-F04 MINOR | `_validate` and Task04 fixture: unconditional READY excluded actual production deny path; Task04 fabricated READY even for deny cases. | Accept exact empty NOT_RUN only for denied saved assessments; S02/S05 production slices pass. FAILED remains unsupported; no scientific semantics changed. |
| T05-F05 MINOR | `store.py:_connect` transaction usage: Windows fixture deletion failed because SQLite connections were not explicitly closed. | Run-1 symptom WinError32 in three slices; fixture-only subclass closes real SQLite connections. Run-2/3 delete original state successfully. Production connection lifecycle remains unchanged/outside this patch. |

## Oracle adequacy (self-review, not independent validation)

Task03 §2 specifies compatible support, missing/pending/mismatched mapping,
control non-priority and exact statuses/reasons; §6 requires closure, not authority.
Original ledger `task04-support-oracle-1` retained byte-for-byte. No corrections,
new decision expectations or revision. New engineering invariants were written
in tests before their first execution, not inferred from observed outputs.

Expected tuple = study status, study run_allowed, candidate-a status,
candidate-a priority_eligible, exact sorted candidate-a reasons:

| Case | Requirement / expected tuple |
|---|---|
| S01 | Compatible reviewed mapping: READY_FOR_COMPUTATIONAL_REVIEW, true, SUPPORTED_COMPUTATIONALLY, true, [] |
| S02 | Missing mapping: MAPPING_REQUIRED, false, MAPPING_REQUIRED, false, [mapping_record_missing] |
| S03 | Pending review: MAPPING_REVIEW_REQUIRED, false, MAPPING_REVIEW_REQUIRED, false, [mapping_review_required] |
| S04 | Context mismatch: OUT_OF_SCOPE, false, OUT_OF_SCOPE, false, [context_mismatch:mode] |
| S05 | Combined precedence/reason preservation: MAPPING_REVIEW_REQUIRED, false, MAPPING_REVIEW_REQUIRED, false, [context_mismatch:mode, mapping_review_required] |
| S06 | Controls-only cannot authorize: MAPPING_REQUIRED, false, null, false, [] |

Each case additionally checks control priority false. No contradiction found in
these inputs; precise precedence/S06 categories are more detailed than Task03's
high-level text, and remain provisional, not independently specified scientific
rules. For **every case**, oracle does not separately check candidate run_allowed,
control status/reasons, mapping provenance/IDs/hash/version, capability, approval
requirement or scientific_scope text. Full original/recomputed projection equality
checks these for consistency, not independently for correctness. Missing families:
backend-not-ready, unsupported assay/intervention, rejected/biological mappings,
version/hash/readout mismatch, metadata conflicts, multiple candidates and richer
context/default/type boundaries. No case-count inflation; no population inference.

## Execution and historical authority

Observed: actual fixture SQLite store and service methods; synthetic adapter's
describe/validate only, run sentinel; spies fail on approval/job creation/submission.
Ordinary assessment persists support (and existing store invalidation semantics),
not approval. Export snapshots approval as null after reassessment. Separate
historical package test imports approval evidence and observes no active store
approval, jobs or added events. Recompute itself has no service/store dependency.
No real database or operational state accessed.

Three integrated slices (S01/S02/S05): production assessment → existing v2 writer
→ sidecar → copy → original fixture directory deleted → Python `-I -B` process
with copied trusted code. Audit hook permits package/code/runtime reads and rejects
network/process events. This is a dependency guard, **not an OS sandbox**.

Results are separate: integrated oracle agreement **3/3**; production/recomputed
full pure-projection agreement **3/3**; closure **3/3**. Re-run Task04 tests also
pass six fixture slices, but are not independent evidence. Targeted corruptions
exercise missing/tampered dependency, policy/code/environment mismatch, paths,
graphs, approval binding and no workspace fallback; modified context with valid
closure produces disagreement, not a false integrity failure.

Command for each run (N=1,2,3), from PowerShell:

```powershell
$r='E:\research-\.workbench\ai-v2-dev'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:TASK05_ARTIFACTS="$r\docs\publication_review\task05_artifacts\run-N"
python -m pytest --noconftest -q -p no:cacheprovider "$r\tests\test_workbench_support_package_integration.py" "$r\tests\test_workbench_decision_package.py" --junitxml="$env:TASK05_ARTIFACTS\pytest.xml"
```

Run-1: 29 passed/3 failed (SQLite locks); run-2: 33 passed; run-3 after adding
historical-authority test: **34 passed, zero failures/errors/skips**, exit 0.
Separate logs/XML/exit receipts retained. `git diff --check` exit 0.
No conftest existed at root/tests; flags prevent ambient fixture/plugin imports;
private namespace bypasses broad package initializers, not actual service methods.
Not full service regression: package initialization, web/API/worker, real adapters,
job lifecycle, live approvals, scientific data and production bundles untested.
Legacy directory/ZIP v2 export, default opt-out, fresh-target/no-overwrite and
failed-preflight rejection are covered at the affected service entry points.

Task04 historical JUnit observed: run-1 24 tests/6 failures, run-2 24/0; ledger and
run-2 inventory hashes match reported values. This verifies retained receipts, not
independent re-execution of historical source. Task04 artifacts untouched.

## Review packet and next step

Explicit allowlist packet includes full relevant source/dependencies/tests,
Task03 spec/log, Task04 report/ledger, Task05 documents, tracked service diff,
machine verification summary and JUnit/exit receipts; no scientific data, DB,
secrets, environment dump or unreviewed logs. Manifest hashes each included file;
archive CRC, names and content hashes checked. It is a **review packet, not an
independent reproduction package**. Assign a human second engineering reviewer;
review provisional oracle and integration limitations before expanding claims.

**DỪNG CHỜ REVIEW — chưa thực hiện Task06.**