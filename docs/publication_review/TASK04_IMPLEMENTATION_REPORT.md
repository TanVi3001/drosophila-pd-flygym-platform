# Task04 — bounded support decision recomputation

**COMPLETE for the declared engineering subset; provisional oracle, not independently validated.**

## Repository and scope

Repository: `E:\research-\.workbench\ai-v2-dev`; branch
`feature/evidence-audit-review`; HEAD
`03b91b598eb63a72840cacd9dd7bb5fed7ebd4b1` unchanged. Fresh Git status at
startup exited 0, recovering the previously uncertain command state. No tracked
changes existed; ten existing untracked files were preserved. No commit, push,
reset, stash or branch change. Root AGENTS applies; checked relevant ancestor and
target parent instruction paths, with no additional instructions found.

Implemented **support assessment only**, using `assess_study_support`. No claim
of selection, operational approval/freeze, submission eligibility, store
invalidation, backend preflight correctness, simulation or domain validation.
Historical approval is inert input evidence, not another evaluated decision type.

## Choices and deviations from Task03

D03-03 narrowed to one pure decision type to avoid service-stack imports and
operational writes. D03-08 ablation explicitly excluded by Task04 authorization.
D03-05/06/09 implemented as a separate explicit opt-in sidecar API rather than
modifying service or v2 export APIs. D03-10 uses exact categorical/reason-set
comparison; no numerical endpoint is in scope. D03-12 domain claims remain
deferred. D03-13 reviewer assignment and independent review remain unresolved;
they do not prevent this bounded engineering completion.

The v2 schema, writer and existing source behavior are untouched. The supplied
fixture emits v2-shaped JSON, not a real-workspace export. Compatibility verified
here means preserving original bundle bytes/default opt-out and accepting legacy
absence explicitly, **not** end-to-end service export compatibility testing.
No real portable production bundle was assessed.

Minimum closure profile is intentionally flat: every listed object is required;
nonempty graph edges (including cycles), duplicate IDs/paths, unknown objects or
schemas are rejected. General dependency graphs, optional extensions, migrations
and historical environment compatibility are unsupported, not silently resolved.

## Files and interfaces

New source: `E:\research-\.workbench\ai-v2-dev\src\drosophila_pd\workbench\decision_package.py`.
Interfaces: `export_sidecar`, `recompute`, `runtime_identity`, `pure_modules`,
`pure_projection`; internal `_load` and `_validate` check portable closure.
No existing source file changed. The module can be loaded directly by trusted
file path; the pure loader uses a private namespace for only existing `models.py`
and `support.py`, avoiding both broad package initializers. It never executes
code supplied inside a bundle.

New tests/fixture harness:
`E:\research-\.workbench\ai-v2-dev\tests\test_workbench_decision_package.py`.
Ledger and receipt:
`E:\research-\.workbench\ai-v2-dev\docs\publication_review\TASK04_ORACLE_LEDGER.json`
and sibling `TASK04_ORACLE_RECEIPT.txt`. Checkpoint is sibling
`TASK04_CHECKPOINT.md`. Task01–03 were not edited.

## Oracle and accounting

Ledger `task04-support-oracle-1`, fixture `task04-engineering-1`, SHA256
`f75cb973b5c577f1bc230c44c05e9f02958b2e0ebdc810a348c2ddf2d99eb034`
was saved before any fixture execution. Expected tuples were hand-derived from
declared contract rules, never copied from implementation output. Common ledger
fields apply to every row. No oracle correction or revision occurred.

Six cases: S01 compatible, S02 missing mapping, S03 pending review, S04 context
mismatch, S05 pending plus context mismatch, S06 controls-only boundary. One
instance per family, one allow and five deny. Total inventory 6; provisionally
oracle-resolved 6/6 (100%); unresolved 0; final executed 6; errors/timeouts/skips
0/0/0. Independent review status:
**PENDING_INDEPENDENT_ENGINEERING_REVIEW**; reviewer unassigned. No invented
review identity or review time.

Run-2 exact oracle tuple agreement 6/6, separately exact original/recomputed pure
report agreement 6/6 and valid closure 6/6. False acceptances/rejections 0/0 for
this fixture inventory only. No population reliability estimate, confidence
interval, added-value claim, or independent-sample interpretation of reruns.

## Sidecar behavior

`export_sidecar(root, snapshots, opt_in=False)` does nothing unless explicitly
enabled. Caller supplies exact snapshot objects, including explicit null when
approval is absent. An existing v2 directory is required; historical bytes and
existing sidecars are not rewritten. Attachments use SHA256-addressed JSON paths,
size and byte digests; `decision-recompute-1/dependencies.json` declares schemas,
resolver and selected decision type.

Snapshots capture study identity/configuration, capability, mapping/version/hash/
review provenance, supplied context, intact support assessment, historical
approval or null, candidate/no-job inventory, saved pure decision, policy and
runtime identities. No run/QC/selection inputs are required because none are
consumed. Mapping absence can itself be an explicit decision input (empty
registry), distinct from a missing required mapping-registry attachment.

Importer validates inventory, study/mapping/assessment semantic hashes, bundle
binding, approval exact study/configuration/assessment binding if present,
policy and code/environment identity. Fixture preflight must be READY. Only
`backend_preflight` and `assessment_hash` are excluded from pure-report equality;
the intact stored assessment hash is independently checked. Preflight is supplied
fixture state, not recomputed. Approved-like fixture strings are explicitly
engineering-only and authenticate nobody.

Legacy absence, missing dependency, byte mismatch, unsupported version/profile,
unsafe path, policy/code/environment mismatch and unsupported preflight return
explicit `NOT_RECONSTRUCTABLE` reasons. No workspace/path/network fallback.
Null approval is never inferred into approval and does not block support-only
recomputation. Every result has `operational_authority: false`; there is no
store/job API, submission or execution in this module.

## Isolation and verification

For each case, create fixture and original decision, export, copy to fresh
temporary root, copy exactly three trusted code dependencies, **delete original
fixture workspace**, and launch Python `-I -B` from the fresh root. No original
database, artifact resolver or workspace is passed. A Python audit hook rejects
reads outside package, declared trusted code and Python runtime; socket,
subprocess and OS launch events are rejected. Private loaded-module inventory
contains only namespace, models and support. This is a trusted-code engineering
guard, not an OS security sandbox against malicious Python/native code.

Negative tests cover missing artifact, altered bytes, policy and sidecar version,
code/environment mismatch, approval binding, traversal/absolute path, original-
workspace-only dependency, failed preflight, cycle, duplicate ID and inventory
omission. Additional tests cover ledger receipt, opt-out/legacy/no overwrite,
explicit absent approval, and valid integrity with original-decision disagreement.

Exact test command, both runs (substitute N=1 or 2):

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:TASK04_ARTIFACTS='E:\research-\.workbench\ai-v2-dev\docs\publication_review\task04_artifacts\run-N'
python -m pytest --noconftest -q -p no:cacheprovider E:\research-\.workbench\ai-v2-dev\tests\test_workbench_decision_package.py --junitxml="$env:TASK04_ARTIFACTS\pytest.xml"
```

Output was captured with `Tee-Object`, and `$LASTEXITCODE` saved in `exit.txt`.
Run-1: exit 1, 18 passed, 6 failed (6.69s), no skips/timeouts. Each isolated
process failed because Windows `platform.system()` indirectly invoked
`socket.gethostname`; guard correctly rejected it. Fixed identity collection to
`sys.platform`/pointer bits, retaining guard and original failure logs. No oracle
change. Run-2: saved test exit 0, **24 passed**, 0 failed/errors/skipped (6.80s).
Tool wrapper inconsistently reported terminal closure/nonzero after printing
exit 0; a separate successful completed command reread exit receipt and JUnit
(24 tests, 0 failures/errors/skips). Git diff-check and status also exited 0.
No full suite or broad imports ran; no existing source behavior was modified.

## Revision identity, artifacts and limitations

Artifacts root:
`E:\research-\.workbench\ai-v2-dev\docs\publication_review\task04_artifacts`.
Run-1 failures retained; run-2 contains six exported packages/results, JUnit/log/
exit receipt, case-accounting JSON, source inventory and verified-source copies.
Package sidecar `decision-recompute-1`; policy `support-pure-ready-fixture-1`;
runtime Python CPython 3.12.10, win32, 64-bit, stdlib only.

Dirty-tree identity: run-2 `source-inventory.json` SHA256
`370ba5c8b46967e01ba34e035f6c9eedde0b0da4ff13d11431c833bc9f981591`.
It hashes the exact source module, existing models/support, test and ledger bytes;
excludes itself, reports/checkpoint, unrelated workspace and artifacts to avoid
self-reference/secrets. It supplements HEAD, not a claim HEAD captures uncommitted
code. Final documentation is outside executable inventory.

Hash checks are not reviewer authenticity or scientific correctness. No hosted
provider, simulator, neural backend, evaluator, held-out/sealed contents, ablation,
scientific labels, real reviews, operational approvals or jobs were accessed or
changed. No independent operator reproduction, ranking superiority, biological
claim or protocol freeze. Outstanding: assign independent engineering reviewer;
review oracle and bounded API/compatibility before broader interpretation.

**DỪNG CHỜ REVIEW — chưa thực hiện Task05.**