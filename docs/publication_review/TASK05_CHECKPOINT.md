# Task05 checkpoint

Status: COMPLETE — bounded engineering review/integration; independent review PENDING.
Root: E:\research-\.workbench\ai-v2-dev
Branch: feature/evidence-audit-review
HEAD: 03b91b598eb63a72840cacd9dd7bb5fed7ebd4b1
Startup: no tracked modifications; pre-existing untracked publication_review,
decision_package.py/test, master-context and verification script preserved.

Read: root AGENTS (no applicable ancestor/nested instructions found), pyproject,
Task03 specification/decisions, Task04 report/checkpoint/ledger, decision_package
and tests; production service assess/export/report, support, store, handoff,
adapter/import dependencies and existing support-service fixture tests.
No root/tests conftest found. Broad package initializers import unrelated stacks;
targeted tests will load actual service in a private namespace, not stub its logic.

Findings: T05-F01 MAJOR missing service integration; T05-F02 MAJOR capability
snapshot unbound to assessment; T05-F03 MINOR loader cached by path while identity
hashes disk bytes; T05-F04 MINOR READY synthetic preflight not actual denied service
NOT_RUN. Fixes in service.py/decision_package.py in progress. No support rules changed.
Oracle: task04-support-oracle-1 unchanged; provisional; independent reviewer PENDING.
Tests: none run for Task05 yet. No Task04 artifacts overwritten.
Resume: add production-path tests with real temp SQLite store, explicit offline
adapter; run targeted scope with controlled imports/plugins, retain each run.

Phase B: service seam implemented at assess_support(decision_package_target=...),
using same captured mappings/capability/context and existing v2 exporter. Default
unchanged; only fresh no-job engineering directory; FAILED preflight rejected.
Added tests/test_workbench_support_package_integration.py. No oracle changes/new
decision cases: integration selects existing S01/S02/S05 expected tuples.
Run-1: 29 pass/3 fail, all original-directory deletion blocked by SQLite file lock.
Root cause: production store transaction context does not explicitly close SQLite
connection; fixture subclass now closes connections, no store production change.
Run-1 retained. Resume: run-2 targeted verification; review/report/packet pending.

Phase C: run-2 33 pass; added historical-approval store side-effect test; run-3
34 pass, 0 failures/errors/skips, exit 0; git diff --check exit 0. Three integrated
slices S01/S02/S05: oracle 3/3, original agreement 3/3, closure 3/3, original state
deleted. Six original harness slices also pass, not independent validation.
T05-F05 MINOR records production SQLite connection lifecycle limitation; fixture
closes connections explicitly. Task04 JUnit receipts read (24/6 then 24/0);
ledger/inventory hashes match reported values. Task04 artifacts unchanged.
Report: TASK05_REVIEW_INTEGRATION_REPORT.md. Explicit packet builder/manifest and
verification summary in task05_artifacts; packet task05_review_packet.zip.
No full-suite/API/UI/default-package initialization or live adapter regression.
Oracle unchanged; reviewer remains PENDING_INDEPENDENT_ENGINEERING_REVIEW.
Remaining work: human independent engineering review, production completeness
and broader compatibility only under new authorization.
Exact resume step: read report/manifest and review retained runs; do not start
Task06 or re-execute automatically. DỪNG CHỜ REVIEW — chưa thực hiện Task06.

## Phase D — review-fix follow-up, 2026-10-19 (Asia/Saigon)

Owner requested applying task05_review_fix.zip to this repository. Verified all
11 inventory hashes/sizes and matching before hashes for both existing target
files. Fixed loader source/bytecode mismatch, failed-import cache cleanup,
attachment path collisions and validation/serialization before sidecar creation.
Integration now covers S01–S06. Strengthened the archive's NaN regression to
avoid an unrelated bundle mismatch and added duplicate-path rejection coverage.

Windows CPython 3.12.10 / pytest 9.1.1: baseline 34 passed; new regressions before
fix 5 failed/1 passed as expected; final 43 passed, no errors/skips, exit 0.
Six saved integration results show VALID closure and original agreement, with
operational_authority=false. git diff --check passed. Source/test trailing
whitespace scans passed. Backup, JUnit, results and source-hash summary are in
task05_artifacts/review-fix-windows-v1/. Full report: TASK05_REVIEW_FIX_REPORT.md.

Task04 ledger, original Task05 packet and historical receipts preserved. Code
identity changed; do not modify old packages to bypass CODE_MISMATCH. Current
build_packet.py remains the historical 34-test packet builder; it was not rerun.
Independent engineering review remains PENDING; fixture-only SQLite connection
handling, full-suite/API/UI/live backend and scientific validation limitations
remain. No provider, simulator, held-out read, commit/push or Task06 execution.
