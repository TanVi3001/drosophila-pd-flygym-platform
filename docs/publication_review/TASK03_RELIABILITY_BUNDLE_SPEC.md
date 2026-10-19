# TASK 03 — Reliability evaluation & reconstructable package specification

**COMPLETE design; PROPOSED, not approved/frozen — 2026-10-19.** No Task04 execution. Engineering contract compliance only: no scientific correctness, biological validity, ranking superiority or publication-readiness claim.

Repo `E:\research-\.workbench\ai-v2-dev`; branch `feature/evidence-audit-review`; HEAD `03b91b598eb63a72840cacd9dd7bb5fed7ebd4b1`. Initial tree: no tracked changes; seven untracked pre-existing files preserved. Root AGENTS applies; Task01–02 are audit inputs, not approval.

## 1. Premises and inspected evidence

**F05 confirmed, requirement narrowed:** no established independent reference was found. Task04 requires an independently derived **contract oracle**, not a biological gold standard. Domain reference evaluates scientific correctness; human approval records authorization; biological evidence evaluates biological interpretation. None substitutes for another. No new domain adjudication is needed for the bounded engineering claim; no claim that it already exists.

**F10 confirmed with closure qualification, not categorical information absence:**

| Closure layer | Inspected behavior / conclusion |
|---|---|
| Inline | EvidenceBundle v2 includes study, decision/ranking reports, manifests, review, dossiers and confirmation records. Study/candidate metadata can carry indirect information. |
| Attachments | Writer serializes those objects plus checksums; no dedicated support assessment/approval/selection attachments. |
| Other storage | Service stores support/approval separately and selection_report.json separately; export builder receives none of these. Their presence in the workspace is not export closure. |
| References / versions | Sources, manifest_path, input/artifact hashes and backend revision can identify external objects; some hashes/version pins are optional. A locator alone is mutable/unresolved. |
| Resolver / mutable state | Writer does not copy referenced raw inputs/code/environment or resolve dependency graphs. get_report reads live artifacts and assay logic; manifest loaders skip missing/unreadable records. |
| Remaining unknown | No concrete portable development instance inspected; arbitrary nested metadata may contain additional snapshots. Do not infer all information absent in every instance. |

Task02 unchanged. Source locators: §7; handoff:137–231,264–357,433–464; service:1381–1425,1499–1539,1573–1589,1682–1726.

## 2. Track A — bounded contracts and independent oracle

Use synthetic `engineering-only` identities, one control and candidates a/b; never represent fixture review strings as real authorization. Build fresh temporary state only. Scope: pure support assessment, approval/freeze guard and fixture-adapter submission eligibility, selection over saved paired observations. Backend scientific preflight and raw-assay QC correctness are excluded; QC flags/readout availability are supplied engineering inputs.

| Type / source | Input → expected / rationale | Actual observation; error condition |
|---|---|---|
| Support: support.assess_study_support | Ready capability, compatible declared assay/intervention/dataset/namespace/context and reviewed mapping → run_allowed; controls never priority eligible. Missing/pending/mismatched mapping → no run/priority. | Candidate/study status, booleans and reason sets; wrong status/permission or omitted required reason fails. |
| Approval/invalidation: service.approve_support_assessment, _require_support_freeze; store.set_support_assessment | Current run-allowed assessment + nonblank fixture reviewer permits approval. Missing/stale assessment, blank reviewer or hash mismatch blocks; reassessment deletes approval even if equivalent. | Approval payload, exception category, stored approval absence; stale acceptance fails. |
| Execution eligibility: service.submit_job, _materialize_candidate_config | support-gated-1 plus current binding, matching backend/target pins and fixture validator READY → queued job only. Invalid binding/override/target IDs blocks. | Job count/config or normalized error; any invalid enqueue fails. No worker/backend runs. |
| Selection/abstention: selection.select_candidates; ranking.rank_candidates | Supported scoped candidate, enough unique QC-passing pairs, stable direction and CI strictly excluding zero → eligible; budget selects directional lower bound, ID breaks ties. Otherwise abstain/exclude. | selected IDs/order, evaluation statuses, exclusions, budget; wrong recommendation, missing exclusion or negative-biological relabel fails. |

**Oracle procedure:** before execution, author a case ledger from these normative rules, with case/family/decision IDs, explicit inputs, expected tuple and derivation. A second engineering reviewer checks rules and hand-calculations without actual outputs; record identity, disagreements and unresolved cases. Review is not yet performed. Do not call the function/wrapper under evaluation or recycle historical outputs to generate expected values. New diagnostic comparisons cannot silently rewrite the ledger; changes require versioned rationale and rerun designation. Hashes are checked by independently implemented documented JSON/SHA256 arithmetic, not a decision oracle.

Initial ledger families (expand into named rows before Task04 evaluation):

| Family | Positive / negative / boundary / combined cases |
|---|---|
| S compatibility | Fully matching control+a; missing and pending mapping; unsupported assay; context missing/mismatch; dataset conflict; exact versus changed mapping version/hash; controls-only denies study run; pending+context mismatch blocks with both reasons. |
| A binding | Current approval; absent approval; changed study content; changed assessment hash; blank reviewer; identical reassessment invalidates approval; stale study+missing approval blocks without demanding arbitrary error precedence. |
| E submission | Matching fixture validator enqueues; backend override; wrong target IDs; mapping pin mismatch; validator error; stale approval+wrong target never enqueues. |
| Q/S selection | a has three deltas +1, b +2: budget 1 selects b. Equal +1 ties select a. Two versus three pairs; all zero abstains; duplicate seed, QC false, missing/nonfinite value, wrong scope block. Unsupported b with +2 and eligible a selects a. QC failure+pending support never recommends. |

Selection policy: increase, minimum_pairs=3, budget=1, bootstrap_samples=1000, seed=0, CI=.95, stability=.8, explicit study/control/assay/metric. Constant deltas give analytically degenerate intervals, avoiding bootstrap-generated gold. Policy validation boundaries include budget 0/1, pairs 1/2, samples 49/50, CI 0/1 (invalid endpoints), stability 0/1 (valid endpoints). Invalid schema cases expect typed rejection, not scientific labels. Dependency: mutations share family/template; deterministic repeats never increase n.

## 3. Endpoints (proposal, not existing ranking-protocol replacement)

**Primary:** exact contract-outcome agreement, numerator decision instances matching the predeclared categorical tuple, denominator all pre-enumerated A-track instances with resolved oracle. Unit = (case ID, decision type, declared candidate/study scope); report type/family counts, never an unqualified pooled reliability rate. Oracle-unresolved cases are listed before running and excluded explicitly, not after seeing outputs.

Positive condition = contract permits the declared action; negative = must deny/abstain/reject. Expected invalid-input rejection counts as agreement only with the declared category. Unexpected exceptions, missing output and timeouts (proposed 30 seconds/instance, no retry replacement) fail agreement. Abstention/unassessable succeeds only when expected; positive-case abstention is false rejection. Out-of-scope/malformed fixtures remain in their rejection stratum.

Secondary, separately reported: false acceptance / all deny-required units; false rejection / all allow-required units; valid coverage = accepted allow-required / all allow-required; output coverage = resolved outputs / all units, with expected typed rejections resolved and crashes/timeouts unresolved. Selection actions refer to oracle budget winners, not every eligible nonwinner. Also report abstention, QC/unassessable and invalid-input counts, explanation agreement, missing-dependency detection and B-track reconstruction success. No arbitrary composite, inferential CI, population reliability or biological generalization for this engineered suite. Reject-all fails positive controls; engineering acceptance requires zero categorical mismatches, all positive controls accepted, all required corruption cases detected.

## 4. Track B — isolated recomputation

Levels: **L1 record inspection** reads stored decisions; **L2 decision recomputation** regenerates decisions from exported inputs; **L3 simulation rerun** generates upstream outputs anew; **L4 independent operator/environment reproduction** requires an actual separate operator/environment study. Task04 targets **L2**, same pinned engineering environment, fresh directory/process, no original database/workspace. Not L4 merely because a subprocess runs.

1. Create fixture decisions, including no-job denials and QC/excluded candidates; export the package profile below.
2. Copy to clean temporary root; deny original-root access and network; use fresh empty SQLite only for guard/submission state, populated exclusively from package snapshots in assessment-then-approval order. No automatic reassessment during hydration.
3. Validate graph closure/integrity before recomputing. Resolve only root-relative attachments; never registry/latest/original absolute paths. Pinned installed code/environment must match manifest identities; otherwise UNSUPPORTED_ENVIRONMENT, not fallback.
4. Recompute support, guard/submission and selection against records AND oracle. Slice requires fixture preflight READY; support projection removes only backend_preflight/assessment_hash. Guard uses intact service assessment. Failed/real preflight is outside L2 scope, never claimed reconstructed. Use fixture validator only.
5. Compare categorical IDs/order/status/reason sets exactly; compare constant-fixture numeric values exactly. Other finite diagnostics use declared abs/rel 1e-9; no tolerance may alter a threshold decision. Ignore only generated timestamps, relocation paths and derived hashes affected by those exclusions; verify original object/file hashes before normalization. Explanation template/version and reason sets must agree; presentation whitespace is irrelevant.

Reconstruction numerator = complete packages reproducing every required decision; denominator = all ledger-designated complete packages, including failures. Corrupted packages have a separate detection denominator, not success inflation. Artifact replay is not stochastic simulation rerun; no universal bitwise-output requirement.

## 5. Track C — bounded component trade-off

Propose offline **support-filter ablation**, not manual-standard or whole-workflow comparator: identical observations, policy, ranking/QC/budget/tie logic; full arm applies genuine support eligibility, shadow arm bypasses only that filter. Both receive identical support information; ablation deliberately ignores it and is never allowed to enqueue/recommend operationally. No altered stored assessment or approvals. Implement in test harness, not runtime feature flag.

Paired cases: unsupported high-effect b versus eligible a; both eligible; neither eligible; QC-failed b. Report false acceptance, false rejection/valid coverage, changed winners, unspent budget, evaluation time and exported bytes; oracle review effort/case-authoring minutes separately. No per-arm human intervention during scoring; same prior oracle reviewer. This measures support-filter effects on this fixture inventory only, not usefulness of all gates, expert effort savings, ranking accuracy or superiority. Real manual comparison and operator reconstruction advantage are **deferred**: no measured protocol/comparator exists. F13 remains for broader claims; P@5 is not an endpoint here.

## 6. Minimum package contract

Propose opt-in **decision-recompute-1 sidecar profile** alongside unchanged EvidenceBundle v2. No mandatory v3: legacy reading semantics need not change. The sidecar explicitly defines stronger closure, not a retrofit completeness assertion.

Common rule for every row: object ID+declared schema/logic version; SHA256 exact attachment bytes plus existing semantic hashes where present; manifest maps identity → relative path, size, digest and dependency edges. Import validates, never overwrites/reinterprets original records. R=required; C=conditional; O=optional.

| Object / export attachment | Source of truth; relation / version | Requirement; failure / reconstruction check |
|---|---|---|
| study.json | Exact StudySpec snapshot; configuration_hash and explicit serializer version | R; mismatch fails; recompute configuration identity and support inputs. |
| support.json + capability.json | Stored assessment and exact capability/context/policy snapshot; assessment_hash → study/mappings | R; absent fails, independently recompute pure assessment; service preflight marked excluded, never falsely reproduced. |
| mappings/*.json | Registered MappingRecord snapshots; ID/version/record_hash, sources/review provenance → candidates | C for noncontrols; absent/unpinned fails. Synthetic review provenance visibly engineering-only; no invented real reviews. |
| approval.json or explicit absent state | Stored approval; exact study+assessment binding → captured input-scope dependency manifest | R state; approval object C for permitted execution. Mismatch blocks. Input scope includes mapping/capability identities transitively; do not claim existing approval directly signs code/environment. |
| inputs/config/code/environment.json | Exact decision inputs/config, backend descriptor, module/revision/content digests, Python/dependency versions | R decision environment; backend assets C only if consumed (none in slice). Missing consumed dependency fails; identify but do not execute historical simulation dependencies. |
| observations.json + qc artifacts | Saved observations, unique seeds, control/candidate values and QC/availability flags; source-run IDs/manifests if genuine | R for selection; run artifacts C when used. Synthetic inputs explicitly have no real run. Missing ≠ zero; verify recomputed eligibility. |
| inventory.json | Study candidates plus job/collection states, including no-job/excluded/unassessable | R; orphan/duplicate/omitted identity fails; reconcile all decisions, not selected subset. |
| policy.json | Exact SelectionPolicy plus ranking logic, parameters, thresholds, seed and ID tie rule | R for selection; absent/version mismatch fails, never defaults; recompute policy identity. |
| decisions/*.json | Saved support/guard/selection report and explanation templates/reason sets | R for requested types; absence fails L2 comparison; preserve full report and collection provenance. |
| dependencies.json | Export inventory; root object, required/optional edges, unavailable reasons, resolver version | R; cycles/path escape/duplicate IDs/hash mismatch fail. Resolve local content only; unknown optional objects retained inert. |

Checksums prove integrity, not scientific correctness, reviewer authenticity or protection against wholesale malicious re-signing. Never fill missing approval with inferred approval. Legacy v2 stays L1-readable to existing extent; unknown fields retained. Missing sidecar/required objects yields explicit NOT_RECONSTRUCTABLE plus missing list; incomplete package may be inspected, never scored L2-success. No implicit migration, latest-version resolution or filling old data from current workspace.

## 7. Task04 implementation — maximum three work packages

All file locators below are absolute. New symbols/files are proposals, not existing implementations.

| WP / problem | Minimal files/symbols and acceptance tests | Dependencies / compatibility |
|---|---|---|
| 1 Oracle + fixture harness | Existing `E:\research-\.workbench\ai-v2-dev\tests\test_workbench_support.py`, `E:\research-\.workbench\ai-v2-dev\tests\test_workbench_support_service.py`, `E:\research-\.workbench\ai-v2-dev\tests\test_workbench_selection.py`; new `E:\research-\.workbench\ai-v2-dev\tests\test_workbench_decision_contract.py`: reviewed ledger, analytical cases, fixture validator. Exercise assess_study_support, _require_support_freeze, submit_job, set_support_assessment, select_candidates. Acceptance: fixed denominators, positives, negative/boundary/combined cases; oracle cannot import decision code for expectations. | No backend runs; independent review pending before evaluation interpretation. Production gates unchanged. |
| 2 Closure export/import | Existing `E:\research-\.workbench\ai-v2-dev\src\drosophila_pd\workbench\handoff.py`: EvidenceBundle/_write_bundle_directory; `E:\research-\.workbench\ai-v2-dev\src\drosophila_pd\workbench\service.py`: export_evidence_bundle. New sibling `E:\research-\.workbench\ai-v2-dev\src\drosophila_pd\workbench\decision_package.py`: opt-in snapshot exporter, validator/local resolver, recompute entry point. Test new `E:\research-\.workbench\ai-v2-dev\tests\test_workbench_decision_package.py`: missing/tampered inputs, pins, path traversal, unknown versions, absent approval, no-job cases, legacy L1 behavior. | WP1 ledger; no runtime schema bump/default export change. Strict sidecar may reject formerly inspectable incomplete bundles only for L2. No arbitrary code loading. |
| 3 Vertical slice + shadow comparison | Same new test files: fixture → decision → opt-in export → fresh-root import → recompute; source-root/network access must fail if attempted; subprocess/backend launch sentinel. Harness-only support-filter ablation and count/timing/size report. Acceptance: all complete packages reconstruct, all declared corruptions fail explicitly, coverage retained, no production-state access. | WP1–2. Do not change `E:\research-\.workbench\ai-v2-dev\src\drosophila_pd\workbench\reproduction.py` campaign verifier into an L2 claim. Test/evaluation execution requires Task04 authorization. |

**GO for engineering implementation after explicit Task04 authorization**, not execution now. Reviewer confirms scope/endpoint and assigns independent oracle reviewer before interpreting results; domain/manual/operator claims remain deferred. Routine choices above are defaults, not additional approval gates.

**DỪNG CHỜ REVIEW — chưa thực hiện Task 04.**