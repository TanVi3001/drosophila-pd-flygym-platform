# TASK06 — Comparative support reconstruction protocol

**DRAFT_FOR_REVIEW — NOT_FROZEN — NOT_EXECUTED.** 2026-10-19, Asia/Saigon.
Repository: `E:\research-\.workbench\ai-v2-dev`; branch
`feature/evidence-audit-review`; HEAD `03b91b598eb63a72840cacd9dd7bb5fed7ebd4b1`.
Existing modified `service.py` and untracked project work are preserved.

## 1. Scope and Task05 reconciliation

Study pure support-assessment reconstruction within the existing engineering-only,
no-job profile. Backend preflight is recorded input; approval evidence is inert.
Selection, scientific correctness, live execution and human performance are outside
the study. Contract compliance (A) has engineered verification; reconstruction
utility (B) needs comparison; biological correctness (C) remains unevaluated.

Retained Windows JUnit reports **43 tests: 24** in
`test_workbench_decision_package.py`, **13** in
`test_workbench_support_package_integration.py` and **6** in
`test_workbench_decision_package_review.py`. They cover six isolated fixture
slices, six service/store/export slices, closure/binding corruptions, legacy/no-overwrite,
authority isolation, loader bytecode/cache and export-validation regressions.
The Linux review packet had 42; Windows added a duplicate-path rejection test.
Its NaN test was also corrected to reach serialization, without adding another test.

`task05_artifacts/review-fix-windows-v1/verification-summary.json` matches all three
JUnit hashes/counts: baseline 34 passed, before-fix regressions 5 failed/1 passed,
final 43 passed. Summary records exits 0/1/0; no separate exit file exists.
Current changed-source/test hashes match that summary; models/support/service
match the historical packet. Full identities are in the checkpoint. Ledger hash
remains `f75cb973b5c577f1bc230c44c05e9f02958b2e0ebdc810a348c2ddf2d99eb034`.
These are retained verification receipts, not new research observations or
independent oracle review. No tests were rerun for Task06.

## 2. Questions and claim ceiling

**Primary RQ:** With the original workspace unavailable, under which predeclared
support-input conditions does the opt-in package recover the independently
specified original decision more successfully than existing v2 or an equally
informed snapshot recipe?

**Secondary RQ:** What additional stored bytes and automated preparation/export/
recompute time accompany that recovery?

Target claim: bounded reconstruction utility and failure transparency on the
specified challenge inventory. Equal performance to the recipe, frequent intact
rejections, wrong accepted reconstructions or excessive measured overhead weaken
added-value claims. No improvement over v2 weakens the proposed completeness benefit.
If differences merely reflect missing v2 inputs, report a packaging/completeness
result. No conclusion about general decision reliability, expert effort savings,
biological meaning, workflow superiority, novelty priority or publication acceptance.

## 3. Design and comparators

Choose a **paired, tool-only complete-system descriptive pilot**, not a component
ablation or operator study. For each source instance, capture one immutable
assessment transaction and materialize three arms before applying declared faults.

| Arm | Information available after workspace removal | Tools and preparation |
|---|---|---|
| A: existing EvidenceBundle v2 | All default exported files, including incidental metadata actually present | Existing writer; read-only baseline adapter may recover any complete, unambiguous inputs. Never test A only by calling the sidecar importer. |
| B: opt-in package | Same v2 plus actual `decision-recompute-1` attachments | Existing exporter, closure validator and `recompute` |
| C: v2 + documented snapshot recipe | Same transaction snapshots and identity metadata as B, flat role-named JSON files plus checksum inventory | Harness executes the fixed recipe in the reviewer worksheet; no sidecar exporter/importer. This is a proposed recipe comparator, not measured human work. |

V2 is designed for human evidence review; absence of a promised recomputation
contract is not a baseline defect. Log record readability separately. A receives
no fabricated defaults or extra snapshots. B and C receive equal source information;
their capture/validation mechanisms are intentional system differences. The recipe
checks bindings and directly invokes the same trusted pure support function.
If its implementation needs clarification, resolve it before freeze, rather than
silently dropping this stronger comparator after results are seen.

All arms share source instances, reference, trusted models/support code, Python/
platform, input normalization, network prohibition, working directory isolation,
timeout and scoring. Installed trusted code is supplied out of band, never executed
from attachments. Workspace files/database are inaccessible in all primary runs.
Record tool versions and one-time per-arm setup separately; count source capture,
snapshot preparation and export costs, plus cold-process recomputation. No ongoing
manual recovery, live registry fallback or evaluator access to original state.
No causal claim separating snapshot capture from validation is possible here.

## 4. Cases, sampling and exposure

`TASK06_CASE_PLAN.tsv` lists proposed conditions, parents, dependencies and boundaries;
rows are specifications, not completed cases or independent sample counts.
S01–S06 are calibration only: already exposed during implementation. Proposed P01–P12
are prospective engineered definitions; their payloads have not been materialized.
Developer knowledge of the code/failures prevents an unseen confirmatory claim.

Coverage follows distinct requirements: complete allow/deny snapshots, required
dependency loss versus explicit empty state, input/policy disagreement, context
defaults/overrides, workspace loss, duplicate-content and relocation boundaries.
Each fault is applied once per nominated parent/logical role, with identical content
mutation across arms where that role exists; missing-by-design roles are logged
as pre-existing absence, not credited as successful detection. No variants selected
after observing a favorable result. Candidate boundaries include changed runtime,
wholesale internally consistent replacement and unsupported FAILED preflight;
these expose current limitations rather than guarantee wins.

Bounded inspection of Task04/05 metadata, the Workbench guide and synthetic-demo
scope found engineered fixtures, but no provenance-complete eligible realistic
workflow. No database or mixed registry was opened. This is not a repository-wide
absence claim. Genuine workflows require a curator-supplied development-only,
permission-cleared inventory, exact consumed-input lineage and profile eligibility.
Never relabel a real study `engineering_only` to make B accept it. Such workflows
remain a deferred external-evidence stratum, not part of this pilot denominator.

Sampling unit is one frozen source support instance under one declared condition;
arms are paired. Derivatives share source/template groups. If all sources come from
one generator, report one generator lineage; condition count is not effective n.
Do not fill arbitrary quotas. Freeze the finite rule-coverage inventory before
execution. Power calculation needs independent-group availability, discordant-pair
rates and a meaningful effect threshold; none is established. Use descriptive
paired outcomes without case/claim bootstrap, confidence intervals or p-values.

## 5. Endpoints and analysis

**Primary endpoint: correct isolated reconstruction on intact eligible instances.**
For arm a, numerator = instances returning a computed original pure support
decision matching the independent reference, with no forbidden dependency or
authority use. Denominator = every pre-frozen, reference-resolved intact instance,
including exporter failures, errors, timeouts and information abstentions. An
intact condition means no injected corruption; A's missing-by-design inputs do
not remove that paired source from the denominator. An
original decision denying support is still a successful reconstruction if correctly
computed. Repeating a saved decision without recomputation earns no credit.
Correctness requires reviewed study/candidate statuses, run/priority flags and
reason sets for every candidate; `original_agreement` alone is insufficient.
The primary decision vector includes study/candidate identities and study
configuration hash. Other report metadata are checked for saved-report agreement
and binding separately; the primary endpoint does not certify every explanatory
or biological annotation in the report.

Report each arm's numerator/denominator and paired B–A/B–C success counts and
differences on the same inventory. Separate allow/deny and family strata; do not
pool across calibration, diagnostics or unsupported profiles. Reject-all scores
zero on this endpoint. Exact source-reference disagreement is reported separately
from agreement with a saved output.

Secondary safety endpoints on deliberately corrupted instances: correct identified
non-reconstructability / all reference-resolved reject-required conditions; and
wrong or unqualified reconstruction accepted / that same denominator. A typed
missing/integrity/binding/version rejection must match the frozen reason category.
Crashes/timeouts are failed detection, not correct rejection. Successful rejection
never increases reconstruction success. Fresh-but-internally-valid context changes
have a separate disagreement diagnostic; checksum validity is not original-input
authentication. Whole-package rewriting is outside the authenticity guarantee.

Also report native-profile valid-package rejection / all valid packages under
that arm's declared profile; distinguish A's information unavailability from a
failure of native v2 validity. Report observed output coverage / all scheduled
instances, export failures, status counts and reason-level
disagreements. Reference-unresolved rows are declared before execution, withheld
equally from scored denominators and retained as pending; no post-output exclusion.

Costs: total uncompressed bytes, extra bytes relative to the paired v2, capture/
recipe/export/recompute wall times, and setup records. No human effort/time endpoint.
Use one retained cold attempt per arm/condition, 30 seconds for preparation/export
and 30 for recomputation, no automatic retries. Start external monotonic timers
before process launch; include reads/validation/startup and failed-attempt durations.
Timeouts remain censored failures, never silently removed from latency summaries.
Cycle arm order ABC/BCA/CAB by frozen case index; disclose filesystem cache effects.
Infrastructure aborts retain attempt history; reruns require a documented amendment
and cannot replace the original result. Runtime repeats never increase case n.

Normalize only reason-list order and JSON object-key order; preserve list order,
values, missing versus null versus empty and context keys. Exclude only documented
`backend_preflight`/`assessment_hash` from pure projection, while validating the
intact saved assessment hash. Categorical comparisons have zero tolerance; no
floating decision endpoint. Preserve original bytes/hashes before normalization.

## 6. Reference and reviewer process

The worksheet separates input-only independent derivation, author proposals and
adjudication. A real engineering reviewer other than the case/implementation author
first derives expectations from normative requirements and complete input snapshots,
without seeing code outputs or author labels. Release author proposals only after
that record is saved. Resolve disagreements by documented reasoning and versioned
requirements; unresolved cases remain pending before freeze. Reviewing author labels
alone must be reported as such, not independent derivation. Names/times remain blank
until performed. One independent derivation plus author reconciliation is proposed;
it does not establish inter-reviewer reliability or scientific validity.

## 7. Prior methods and contribution boundary

[AiiDA 1.0](https://arxiv.org/abs/2003.12476), author abstract, already provides
automated workflows, provenance and error handling. Our adapter integration is not
new evidence for those ideas.
[Workflow Run RO-Crate](https://doi.org/10.1371/journal.pone.0309210), abstract and
§3.1, packages workflow entities; Runcrate can re-execute applicable CWL computations.
[ReproZip](https://www.usenix.org/conference/tapp13/technical-sessions/presentation/chirigati),
author abstract, captures dependencies/configuration for packaged reruns. These were
checked on 2026-10-19; this is a focused comparison, not a systematic novelty review.

Candidate added value is the explicit study/mapping/capability/assessment binding
and failure semantics around a support decision. The experiment can distinguish
recovery/completeness and cost relative to an equally informed recipe; it cannot
establish superiority over those external systems, which are not experimental arms.
Novelty remains weak without realistic source diversity and evidence that validated
decision bindings add value beyond standard packaging. Strengthen that empirical
comparison and review the mechanism against existing provenance profiles before
adding features.

## 8. Execution-readiness checklist

- [ ] Review the claim ceiling, primary denominator and three-arm information parity.
- [ ] Materialize/hash case inputs, parents, source permissions and exact inclusion inventory.
- [ ] Independently derive/adjudicate references; freeze normalization/reason categories.
- [ ] Specify and test harness-only A/C adapters and common evaluator on calibration.
- [ ] Pin actual dirty-source hashes, environment, runner, recipe and setup/measurement rules.
- [ ] Review boundary treatment and any infrastructure amendment procedure.
- [ ] Obtain separate authorization for the frozen comparative run.

No feature, comparative experiment, human measurement or approval was performed.
All checklist items are pending; reviewer identity is not needed to finish this draft.
**DỪNG CHỜ REVIEW — chưa thực hiện Task07.**
