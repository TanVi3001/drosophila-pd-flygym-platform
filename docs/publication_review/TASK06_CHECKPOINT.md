# TASK06 checkpoint

Status: COMPLETE — four design deliverables prepared. DRAFT_FOR_REVIEW — NOT_FROZEN — NOT_EXECUTED.
Date: 2026-10-19, Asia/Saigon (UTC+07:00).
Root: `E:\research-\.workbench\ai-v2-dev`.
Branch: `feature/evidence-audit-review`; HEAD: `03b91b598eb63a72840cacd9dd7bb5fed7ebd4b1`.

## Phase 1 — Task05 reconciliation

Read root AGENTS and checked ancestor/docs/publication_review instructions.
Read Task05 fix/integration reports, fix verification summary, three JUnit receipts,
relevant decision_package/tests and EvidenceBundle writer/service export source.
Read Task01 scope audit and relevant Task02/04 reconstruction findings. Current
working tree retains the existing tracked service.py change and untracked
publication_review, decision_package/tests, master context and verification script.

Verified without executing source/tests: JUnit final 43/0/0/0, split 24 package,
13 service integration, 6 regression tests. One extra duplicate-path regression
explains Windows 43 versus archive 42; the NaN regression was strengthened, not
counted twice. Baseline 34/0, regressions-before 6 with 5 failures. All three JUnit
hashes match the retained summary. Exit codes 0/1/0 are recorded in that summary;
no standalone exit.txt exists for these runs. Current three changed-source/test
hashes match it; models/support/service match original packet source hashes.
Oracle remains f75cb973b5c577f1bc230c44c05e9f02958b2e0ebdc810a348c2ddf2d99eb034.
Evidence is retained local verification, not independent review or new observations.

Initial design choice: tool-only paired complete-system pilot of isolated pure
support reconstruction; no human/operator study. Compare existing v2, opt-in
sidecar and a fully specified manual snapshot recipe if feasible. S01–S06 are
development calibration only. Realistic workflow provenance remains unverified.

Unknowns: eligible existing development workflows, reference review, final case
inventory, baseline recipe/tooling feasibility and prior-method comparison.

Deliverables so far: this checkpoint only. No experiment, feature implementation,
provider/backend/benchmark call, subagent, held-out/sealed read, commit/push.

Exact next step: finish bounded provenance/source inspection and primary-method
comparison; author protocol, candidate TSV and output-blind reviewer worksheet;
then check document consistency, hashes and four-file-only mutation scope.

## Phase 2 — feasibility and comparator decisions

Read Task03 support requirements/minimum closure sections; pure support context,
mapping, status and reason semantics; existing Task04 synthetic fixture builder;
docs/workbench/evidence_gated_prioritization.md, examples/README.md and the scope
section of docs/ai_v2/review_gated_demo.md. docs/workbench.md does not exist; used
the actual docs/workbench/ guide. No database, registry/mapping CSV or raw workflow
payload was opened. The limited inspection establishes engineered service fixtures
only, not an eligible provenance-complete realistic workflow. Public mapping
documentation describes a mixed upstream set and pending review; it is not a
permitted source for this experiment. No whole-repository absence claim.

Prior-method checks: AiiDA 1.0 primary paper/author abstract, Workflow Run RO-Crate
primary paper abstract and section 3.1, ReproZip TaPP13 author abstract at USENIX.
These already cover provenance/dependency packaging and some re-execution; no
first/novel/superior claim is justified. Nature's later direct request redirected
to an inaccessible cookie endpoint; the first indexed paper extract and author
arXiv abstract support the limited AiiDA description.

Design: three paired tool-only arms, A existing v2, B v2+sidecar, C v2+documented
manual snapshot recipe (harness-prepared, not a measured human baseline).
Primary success counts correct independent-reference reconstruction on intact
source instances, including correctly recomputed deny decisions. Deliberately
damaged instances have separate rejection/wrong-acceptance denominators.
Complete-system intervention includes capture and validation, so this is not a
causal component ablation. Workspace is unavailable for all main comparisons.
Recipe feasibility, candidate materialization and reviewer derivations remain
pending; prospective cases are developer-authored challenges, not unseen claims.

Exact next step: write the three remaining deliverables, including a concrete
recipe and per-candidate review form; validate counts/TSV/document references
without running project source, tests or any comparative experiment.

## Phase 3 — completed design and document checks

Created only the four permitted deliverables:

1. TASK06_COMPARATIVE_PROTOCOL.md: primary recovery RQ and cost RQ; three paired
   complete-system arms; intact recovery endpoint separate from corruption
   detection/disagreement; one attempt, 30-second stage limits, no replacement
   retry; descriptive paired/source-family reporting; reference and freeze gates.
2. TASK06_CASE_PLAN.tsv: 18 columns, 22 unique inventory/placeholder rows: six
   exposed calibration definitions; 12 prospective engineered conditions (six
   intact, five rejection diagnostics, one disagreement diagnostic); three
   unsupported/authenticity boundary specifications; one non-enrolled realistic
   curation placeholder. These are not completed cases or independent sample n.
3. TASK06_ORACLE_REVIEW_WORKSHEET.md: input-only reviewer panel, independent
   derivation fields, author proposals to reveal later, adjudication history,
   and fixed harness-prepared manual snapshot recipe; reviewer names/times and
   decisions remain empty. Actual inputs/references are not yet materialized.
4. This checkpoint, retaining phase history and actual evidence limitations.

Evidence identities rechecked during Task06 (exact current bytes):

| Source | SHA-256 |
|---|---|
| decision_package.py | 802bc837143bdacc2aa3ffa880632845430a652830eac744c1135c4b23f481cd |
| models.py | 4fab58d39bb74c01999e853eb4eff5316654f37cdcda9330546e9d6b404e57ff |
| support.py | aa025fa48823091062747b755bff3da73c443447484ec59d3340afc3509131b0 |
| service.py | 7db359327ca7dc28b2d710486433384c002d8bc79024a1b28e2e29cf3f6163e7 |
| test_workbench_support_package_integration.py | a2413ab887bbd759c4f7f6d364e7d7676a0fb5f2a394230c807f45730d0411fc |
| test_workbench_decision_package_review.py | cedd0a02e21b134c8a5e5b4d839e0d8fd8194a0f41a9f887647b06904831b195 |
| review-fix-windows-v1/final.xml | 6b907a47f3cdf9b040dc17d8218288d64150b66f971133840e5c5c874e3aca42 |
| original task05_review_packet.zip | 2811759c30c4afc3778f662ca8e541b2dedd5bde7c69a975a60ca746c4e15aed |

The current source identity matches retained local verification as described in
Phase 1; this is not a clean-install re-execution or an authenticity proof.
Exit codes are summary-recorded evidence; JUnit contents/hashes were independently
re-read. No separate exit.txt was found at the retained fix-run root. No new tests
were run because receipts were sufficient and only documentation was changed.

Document checks performed at 2026-10-19T21:04:55+07:00: PASS. Protocol is 1,753
whitespace-delimited words, below the approximately 2,200-word limit. TSV has
consistent 18-field rows, 22 unique IDs and valid parent/group references; all
15 P/B candidate specifications have worksheet proposal rows. Encoding and
trailing-whitespace checks passed on all four deliverables. Source/test hashes,
original oracle and packet remain unchanged; models/support/service/handoff and
the original 24-test file also match historical packet hashes. git diff --check
exited 0. These are document/integrity checks, not comparative measurements.

Remaining review decisions: three-arm information/cost parity; P03/P04 context
semantics; final materialized candidate inventory and exact independent references;
unsupported-boundary scoring; source eligibility if realistic records later emerge;
runner/recipe/evaluator implementation and calibration; final identity freeze and
separate execution authorization. No realistic workflow or reviewer is fabricated.

Exact next step: review these four documents. After actual decisions, separately
authorize preparation/calibration of the harness and input/reference package;
this draft itself authorizes no experiment or production feature. Task07 has not
started. **DỪNG CHỜ REVIEW — chưa thực hiện Task07.**
