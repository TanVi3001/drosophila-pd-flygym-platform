# TASK06 — Input-first engineering reference review worksheet

**DRAFT_FOR_REVIEW — NOT_FROZEN — NOT_EXECUTED.** 2026-10-19, Asia/Saigon.
No reviewer has completed this worksheet. Empty identity/time/decision fields are intentional.
No evaluation outputs are included. Task04's provisional ledger remains unchanged.

## 1. Roles and sequence

Proposed minimum: one real engineering reviewer, distinct from implementation/case
authors, independently derives expectations, then reconciles with the author.
This provides an independent derivation if performed as described; it does not
measure inter-rater reliability or scientific correctness. No participants are
recruited and no operator-performance study is planned.

1. Materialize candidate inputs from the case plan; save exact bytes, hashes,
   requirement versions, grouping and admission decisions. This is future work.
2. Give the reviewer **only the normative requirements and filled Section 2 input
   panels**. Do not initially distribute the author expectation table below,
   implementation/tests, Task04 outputs or evaluation receipts. Copying the entire
   worksheet to the reviewer would expose proposals; disclose that if it occurs.
3. Reviewer fills Section 3 independently, with derivation and ambiguity notes;
   save the record and its actual timestamp before revealing author proposals.
4. Reveal Section 4, compare derivations and resolve disagreements in Section 5.
   Requirement ambiguity needs an explicit versioned decision, not a function call
   used as an oracle. Unresolved cases remain pending before experiment freeze.
5. Freeze a new study-reference inventory. Do not edit Task04's ledger. Record
   whether the work was independent derivation, review of exposed expectations or
   adjudication; these are different evidence levels.

## 2. Input-only panel — duplicate for each materialized candidate

| Field | Fill before reference review |
|---|---|
| Candidate ID / family / condition | |
| Parent case / source workflow / generator lineage | |
| Stratum: intact, reject-required, disagreement, boundary | |
| Requirement file + section + version/hash | |
| Permissions and DEVELOPMENT-only provenance attestation | |
| Source snapshot inventory + SHA-256 per member | |
| Study/candidates, declared capability and mapping pins | |
| Mapping registry content: distinguish `[]` from absent | |
| Exact `required_context` call value and StudySpec metadata context | |
| Supplied preflight scope and no-job engineering eligibility | |
| Original workspace availability | |
| Fault/relocation transformation; bytes changed; digests intentionally refreshed? | |
| Available information/tools for A / B / C; missing-by-design roles | |
| Assumptions and unresolved normative choices | |

All proposed P/B cases are currently unmaterialized. A case ID alone does not
supply sufficient inputs to derive a resolved exact outcome. No exact reviewed
reference may be recorded until the input panel is complete.

## 3. Reviewer derivation — keep hidden from author until saved

| Field | Reviewer entry |
|---|---|
| Reviewer identity | |
| Role / relevant engineering expertise | |
| Relationship to implementation and case author | |
| Materials exposed, including any author labels/code/outputs | |
| Review mode actually performed | |
| Time record saved, with timezone (not inferred reading start) | |
| Case ID and exact input hash set | |
| Admitted supported profile? rationale | |
| Expected study/candidate IDs and study configuration hash | |
| Expected original study status and `run_allowed` | |
| For every candidate/control: status, run flag, priority flag, exact reasons | |
| Original evidence/reference versus saved decision: distinct checks | |
| Expected arm-level reconstructability from accessible information | |
| Required rejection category, or allowable disagreement behavior | |
| Derivation from each normative requirement | |
| Ambiguity / alternative outcomes / additional source needed | |
| Reviewer decision: resolved / change required / unresolved | |

Rules: an expected support denial is still a computed decision; package rejection
is not a reconstruction. Do not use original implementation agreement as the
reference. A no-sidecar v2 is not automatically a failed v2 contract. Describe
missing information accurately without claiming the baseline promised L2 recovery.

## 4. Author proposals — reveal only after independent derivation

These are AI-assisted design proposals, not owner decisions or reviewer labels.
Exact categorical outcomes are intentionally pending materialized inputs and
normative review; the original S01–S06 ledger is calibration, not new reference.

| Candidate | Requirement source | Planned inputs / assumptions | Proposed expectation and derivation | Reviewer decision |
|---|---|---|---|---|
| P01 | Task03 §2 support, §6 closure | Control plus two compatible pinned noncontrols; no original workspace | Capture all call inputs, recompute study and each candidate; independent reviewer derives full allow tuple | |
| P02 | Task03 §2 missing mapping, §6 explicit absence | Complete empty registry and null approval | Empty registry is a declared input; reconstruct the support denial rather than treating it as a missing file | |
| P03 | Task03 §2 context; rule clarification needed | Metadata mode A, mapping A, explicit empty call context | Determine whether empty inherits metadata before deciding exact outcome; current code behavior is not the normative oracle | |
| P04 | Task03 §2 context; rule clarification needed | Metadata A, mapping B, explicit call context B | Decide explicit precedence and derive exact original outcome; preserve both metadata and call context | |
| P05 | Task03 §6 required consumed input | P01 with registry attachment deleted | Information is lost; absence must not become an invented empty registry | |
| P06 | Task03 §6 consumed call context | P04 with override snapshot deleted | Metadata A does not establish original override B; original decision unavailable without additional evidence | |
| P07 | Task03 §6 exact attachment bytes | P01 capability changed; old checksum retained | Reject integrity conflict where a checksum was recorded; baseline pre-existing absence is not injected-loss detection | |
| P08 | Task05 capability binding, Task03 §6 | P01 capability changed; digest refreshed; saved assessment unchanged | Detect capability/assessment disagreement despite valid digest | |
| P09 | Task03 §6 version/profile requirement | P01 policy changed to unsupported version; digest refreshed | Refuse unsupported policy; do not use latest silently | |
| P10 | Task05 valid-closure/context diagnostic | P04 override changed B to C; saved decision unchanged | Closure may pass; recomputation can disagree. Do not equate integrity-valid with original-input authenticity | |
| P11 | Task05 review R03 | P02 context JSON equals policy JSON | Equal content in distinct roles is legitimate; recompute original denial | |
| P12 | Task03 §6 root-relative portability | P01 moved to Windows path with spaces/Unicode, same runtime | Root relocation should not require old workspace; preserve original decisions | |
| B01 | Current exact runtime/code identity profile | P01 with incompatible declared environment/code | Explicitly unsupported profile; not a positive cross-runtime recovery claim | |
| B02 | Task03 integrity/authenticity boundary | Consistent replacement of all original objects and digests | Unsigned self-consistent replacement may pass integrity; authenticity is not guaranteed | |
| B03 | Task05 FAILED preflight rejection | Offline engineering validator returns failure | Current opt-in service profile cannot export; record this limit without changing preflight state | |

For S01–S06, reviewer may audit the original ledger separately, but this cannot
convert already exposed development fixtures into unseen comparative observations.
`REAL-POOL` is a curation placeholder with no enrolled case or assigned expectation.

## 5. Disagreement/adjudication panel — one per disagreement

| Field | Entry |
|---|---|
| Case ID / input hashes / original requirement version | |
| Independent initial derivation, saved before author proposal exposure | |
| Author proposal and rationale | |
| Difference and ambiguity | |
| Adjudicator / actual role and relationship | |
| Versioned requirement decision and rationale | |
| Resolution or unresolved status | |
| New reference version/hash; old reference retained | |
| Actual decision timestamp and timezone | |

No adjudication may use future comparative outcomes to select a favorable label.
Any disagreement discovered after execution is an amendment/sensitivity analysis,
with original frozen scoring retained, not a rewritten preregistered reference.

## 6. Strong comparator C — fixed manual snapshot recipe specification

This specifies a feasible harness baseline; it is not implemented by Task06.
The harness automates the documented manual recipe so there is no fabricated
human effort measurement. B and C must use the same immutable capture transaction.

### Capture and export

1. Record exact StudySpec `.as_dict()`, capability returned for that assessment,
   the same complete mapping-registry snapshot passed to B (including any
   unreferenced records), the exact caller context, full saved support
   assessment, saved pure projection, explicit historical approval or null,
   and candidate/no-job inventory. Do not reload a later registry or reassess with
   different state. Source capture is timed and charged once per arm's accounting.
2. Export the same v2 bytes as A/B. Write a `recipe/` directory with fixed filenames
   `study.json`, `capability.json`, `mappings.json`, `context.json`, `support.json`,
   `decision.json`, `approval.json`, `inventory.json`, `policy.json`, `identity.json`.
   Context/approval absence cannot silently become empty/null: capture explicit
   original state. `mappings=[]` is legitimate when that was the input.
3. `policy.json` records the same support profile version B declares.
   `identity.json` pins models/support/decision_package bytes and exact Python,
   implementation, platform and pointer width, matching B's scope. Supply trusted
   code externally to every arm; attachment code is inert.
4. Write a flat JSON index with `id`, relative `path`, byte `size`, `sha256` and
   schema/version for every role and the original `bundle.json`. Use fixed role
   paths, so distinct roles with identical bytes remain separate. Inventory order
   is deterministic. Publish the recipe/adapter version and hash before execution.

### Isolated reconstruction

5. A harness-only recipe reader (planned) checks required role uniqueness, safe
   local relative paths, byte size/hash, supported profile and exact trusted
   environment. It does not call `decision_package._load`, `_validate` or
   `export_sidecar`, and does not reject A merely for lacking this index.
6. Validate study/configuration identity; study/bundle binding; mapping hashes,
   uniqueness and declared pins; candidate inventory; capability round-trip and
   saved-assessment binding; assessment hash and optional inert approval binding;
   saved pure decision binding. Implement this checklist as calibration-tested
   harness logic, rather than adding a production feature. No fallback to live state.
7. Instantiate the same pinned models/support code from trusted installation;
   call `assess_study_support` with captured context and apply the same documented
   pure projection. Return the computed decision and saved-output agreement
   separately. The common evaluator compares computed results with independent
   reference; it cannot supply missing inputs to a recipe reader.

C is deliberately capable of matching B. If a correctly complete recipe performs
equally, report that result and measured costs. The experiment does not isolate
which single internal validation step caused a difference. Unimplemented recipe
reader/A recovery adapter/common evaluator are explicit pre-execution work, not
present completed systems. Their development is not authorized by this document.

## 7. Acceptance worksheet for all arms

| Design question | Proposed answer | Reviewer decision / reasoning |
|---|---|---|
| Are A's native evidence-review functions represented fairly? | Read all actual default export; do not force sidecar-only importer | |
| Are B and C input bytes from the same capture? | Same source transaction, equivalent logical roles, no extra oracle data | |
| Can A exploit any incidental complete metadata? | Yes, using the frozen read-only adapter; unsupported default inference forbidden | |
| Are preparation/setup costs charged? | Automated capture/preparation/export plus one-time setup reported | |
| Are context/empty/missing semantics sufficiently specified? | P03/P04 require normative clarification first | |
| Is the primary denominator fixed and not rewardable by reject-all? | Intact resolved sources; correct rejections score separately | |
| Are faults comparable across arm formats? | Mutate logical roles; document absence by design and no detection credit | |
| Are calibration/exposure/dependence disclosed? | S01–S06 calibration; all derived conditions clustered by source/generator | |
| Are unsupported boundaries kept visible? | B01–B03 separate, specified before outcomes | |
| Are future realistic-workflow permissions/eligibility verified? | Pending; none enrolled | |

Reviewer name: ____________________  Recorded at (timezone): ____________________

Overall decision: ____________________  Unresolved items: ____________________

This empty worksheet records no review, approval, participant measurement or
scientific validation. **DỪNG CHỜ REVIEW — chưa thực hiện Task07.**
