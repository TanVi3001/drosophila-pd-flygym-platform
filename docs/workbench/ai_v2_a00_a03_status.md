# AI V2 A00–A05 implementation status

Status is evaluated as of 2026-10-06. Percentages below measure completion of
each task's **software and test deliverables**, not scientific validation,
operational adoption, or paper readiness. They are engineering estimates, not
benchmark metrics.

| Task | Estimated completion | Verified in this checkout | Remaining before task can be called fully validated |
| --- | ---: | --- | --- |
| A00 — isolation/runtime bootstrap | 90% | V2 opt-in; external path validation; V1 defaults retained; separate draft runtime; backup helpers and fixture tests | Configure and exercise the team's actual external runtime; live provider/data-retention review; confirm operator launch procedure |
| A01 — approved evidence/retrieval | 75% | Strict corpus/hash contract; offline deterministic retrieval; source/chunk citations; API and tests; no crawling or outcome fields | Project team curates and approves its real source/chunk corpus; run retrieval on that corpus; quantify relevance and check leakage before product demo |
| A02 — guarded StudySpec draft | 75% | Prompt assembly; optional pretrained provider contract; schema/citation checks; exact reviewed-mapping lookup; fixture/API tests | After corpus approval, run a provider smoke test; evaluate drafts against a project-curated development reference set; finish researcher-controlled draft promotion route |
| A03 — workflow automation/reporting | 80% | Fixed tool routes; support/mapping and human-approval gates; 100-job bound; zero automatic retries; timeout/cancel; explicit resume; status/progress; chained audit; artifact report; synthetic success/failure tests | Tuấn's runtime integration; team-run end-to-end and backend timeout/resume checks; decide how reviewed A02 drafts become executable StudySpecs |
| A04 — internal AI artifact evaluation | 80% | Offline evaluator for Precision/Recall@k, MRR, abstention, selective risk, forbidden evidence, categorical fields/citations, bootstrap intervals, non-executable invariants; split firewall; CLI and synthetic regression tests | Project team prepares an approved development-only retrieval/draft reference set; evaluate the approved corpus and provider; report semantic-quality limits without using held-out |
| A05 — development-only AI evaluation | PREPARED / NOT RUN | Metric plan aligned to Notion; A04 evaluator extended with Precision@k, Recall@k, MRR, categorical field match, citation-reference proxy, coverage/selective-risk and report hashes; synthetic tests | No approved real corpus or frozen internal question/reference bundle is configured in this environment; provider/model and retention review; run and analyze real development artifacts |

These estimates do not imply the end-to-end AI pipeline is ready for research
use. A01 has no real approved corpus shipped/configured in this environment,
A02 has not had a live provider and quality evaluation, and A03 has not been
exercised by the team on the external runtime. A05 is prepared but has no real
AI quality measurements yet. The present A03 workflow operates on an already
researcher-authored, support-gated StudySpec; it does not automatically convert
an AI draft into a study.

## Claim and evaluation boundary

- Software contracts can be described as implemented only where tests pass.
- Fixture-provider and synthetic-backend tests demonstrate interface behavior,
  not model quality or biological correctness.
- Mapping remains a human-reviewed project input; software checks its declared
  provenance and capability compatibility.
- Reports surface existing Workbench metrics and QC; AI does not compute or
  override them.
- This work does not establish a biological effect, a Parkinson mechanism, or
  wet-lab benefit.
- `HELDOUT_STATUS = LOCKED_NOT_RUN`.

After targeted tests pass, the current best short summary is: **A00–A04 are
substantially implemented as guarded software scaffolding; the real approved
evidence corpus, live-provider evaluation, operational rehearsal, and scientific
quality evaluation are still needed before claiming a validated AI Workbench.
A05 is planned and instrumented, but its real development-only run is not yet
available.**
