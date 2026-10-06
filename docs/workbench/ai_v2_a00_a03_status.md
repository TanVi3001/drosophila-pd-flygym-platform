# AI V2 A00–A06 implementation status

Status checked on 2026-10-06. Percentages are transparent engineering estimates
for implementation/test deliverables—not scientific validity, real-world
readiness, or paper acceptance probabilities.

| Task | Estimated completion | Verified here | Still missing for broader validation |
| --- | ---: | --- | --- |
| A00 — isolation/runtime bootstrap | 90% | V2 opt-in, external-path checks, V1 defaults, isolated draft paths and fixtures | Team's actual external runtime rehearsal; provider/data-retention decision |
| A01 — approved evidence/retrieval | 75% | Strict corpus/hash contract, deterministic offline retrieval, citation provenance and safety tests | Team-approved real corpus; relevance/leakage evaluation on that corpus |
| A02 — guarded StudySpec draft | 75% | Prompt/provider contract, citations/schema/capability checks, exact reviewed-mapping lookup, non-executable result; uncertainties now have a separate output field | Live provider smoke test after corpus/privacy approval; draft quality evaluation; researcher promotion workflow |
| A03 — workflow automation/reporting | 80% | Fixed tools, support/mapping/human gates, bounded jobs, timeout/cancel, explicit resume, audit chain, reports and synthetic success/failure tests | Team rehearsal against Tuấn's target runtime; timeout/resume operational checks; explicit human promotion handoff from A02 |
| A04 — internal AI artifact evaluation | 80% | Offline evaluator, metric denominators, development/synthetic split firewall, deterministic intervals, CLI and regression tests | Validate evaluation annotations and interpretation on team-approved artifacts; semantic support still needs human review |
| A05 — development-only AI evaluation | **50%** | Metric plan aligned with project Metrics page; evaluator/CLI and synthetic checks prepared; no held-out access | Approved real corpus and frozen development question/reference bundle; provider/privacy decision; run, inspect errors and report real measurements. **Real AI quality result: 0% measured** |
| A06 — offline integration qualification | **100% of scoped synthetic task** | A01 retrieval → A02 fixture draft → A04 evaluation; no-evidence abstention/no-call; non-executable draft invariants. Found and fixed the A02/A04 `uncertainties` schema mismatch. | This does not replace real-provider evaluation or a rehearsal on the team's external runtime; complete those under A05/A00/A03 when prerequisites exist |

## Interpreting the percentages

A05 is about halfway prepared, but its central scientific/quality result has
not been measured: the 50% reflects evaluation design, implementation and
synthetic regression coverage—not a claim that the AI is "50% accurate".
A06 reaches 100% only for the narrowly defined **offline synthetic integration
contract**. Across A00–A06, the unweighted mean of these rough estimates is
about 79%; this is a planning indicator, not a validated project-completion
score. The team should not present that mean as evidence of AI quality.

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
