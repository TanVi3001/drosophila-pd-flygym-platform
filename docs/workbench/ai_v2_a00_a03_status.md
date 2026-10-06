# AI V2 A00–A07 implementation status

Status checked on 2026-10-06. Percentages are transparent engineering estimates
for implementation/test deliverables—not scientific validity, real-world
readiness, or paper acceptance probabilities.

| Task | Estimated completion | Verified here | Still missing for broader validation |
| --- | ---: | --- | --- |
| A00 — isolation/runtime bootstrap | 90% | V2 opt-in, external-path checks, V1 defaults, isolated draft paths and fixtures | Team's actual external runtime rehearsal; provider/data-retention decision |
| A01 — approved evidence/retrieval | 75% | Strict corpus/hash contract, deterministic offline retrieval, citation provenance and safety tests | Team-approved real corpus; relevance/leakage evaluation on that corpus |
| A02 — guarded StudySpec draft | 85% | Prior draft contracts plus A07 stored-draft retrieval/checksum and explicit human promotion handoff | Live provider smoke test after corpus/privacy approval; real development draft-quality evaluation |
| A03 — workflow automation/reporting | 90% | Prior workflow contracts plus A07 full synthetic handoff/run/QC/report; lineage; separate run approval; study-scoped screening IDs with legacy reuse | Team rehearsal against the target runtime; timeout/resume checks on actual backends; operator UX |
| A04 — internal AI artifact evaluation | 80% | Offline evaluator, metric denominators, development/synthetic split firewall, deterministic intervals, CLI and regression tests | Validate evaluation annotations and interpretation on team-approved artifacts; semantic support still needs human review |
| A05 — development-only AI evaluation | **50%** | Metric plan aligned with project Metrics page; evaluator/CLI and synthetic checks prepared; no held-out access | Approved real corpus and frozen development question/reference bundle; provider/privacy decision; run, inspect errors and report real measurements. **Real AI quality result: 0% measured** |
| A06 — offline integration qualification | **100% of scoped synthetic task** | A01 retrieval → A02 fixture draft → A04 evaluation; no-evidence abstention/no-call; non-executable draft invariants. Found and fixed the A02/A04 `uncertainties` schema mismatch. | This does not replace real-provider evaluation or a rehearsal on the team's external runtime; complete those under A05/A00/A03 when prerequisites exist |
| A07 — reviewed draft-to-study integration | **85%** | Saved draft checksum bound to review, human design/control/registry-mapping validation, gated promotion API, separate run approval, revised-study approval isolation, synthetic console demo and success/failure report lineage | Real approved corpus/provider/development inputs; team runtime rehearsal; visual review UI and production identity integration |

## Interpreting the percentages

A05 is about halfway prepared, but its central scientific/quality result has
not been measured: the 50% reflects evaluation design, implementation and
synthetic regression coverage—not a claim that the AI is "50% accurate".
A06 reaches 100% only for the narrowly defined **offline synthetic integration
contract**. Task scopes differ, so averaging the percentages does not establish
overall scientific readiness. A07 verifies the local API/console integration
with synthetic inputs; real model quality and target-runtime operation remain
unmeasured.

## A07 verification record

The external demo completed 2/2 synthetic jobs, 2/2 fixture QC checks and a valid
audit chain. The fake model/reviewer and chosen numeric readouts are software
fixtures. No genuine human or independent reproduction claim is made. The
[A07 handoff guide](ai_v2_a07_reviewed_study_handoff.md) provides the exact local
command and endpoint contract. The focused regression suite passed **105 tests**
in the isolated Python 3.12 workbench environment, including **24 A07 tests**,
with no skips. This environment has FastAPI, so the API tests previously skipped
in the system Python environment were exercised. Compile and diff checks also
passed. Runtime/test artifacts were directed to the external directory on E:.

## Claim and data boundary

- The A06 fixture uses a deterministic local fake generator; it sends no
  request to a model provider and contains no scientific evaluation cases.
- Automated retrieval/citation checks establish identifier traceability, not
  semantic entailment or biological truth.
- Mapping remains a reviewed human input. AI does not create mappings, approve
  StudySpecs, choose interventions, control QC, or calculate ranking metrics.
- V1 ranking metrics and A05 RAG/draft metrics remain separate.
- No Parkinson mechanism, biological effect, or wet-lab benefit is claimed.
- **`HELDOUT_STATUS = LOCKED_NOT_RUN`**. No held-out cases were inspected or run.

The immediate A05 blockers are an approved real corpus, frozen development-only
questions/references, and an explicit provider/privacy decision. Until those
are supplied, the honest state is `PREPARED_NOT_RUN_REAL_MODEL_EVALUATION`.
