# AI V2 A00–A04 implementation status

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
| A04 — internal AI artifact evaluation | 80% | Offline evaluator for retrieval ranking, abstention, forbidden evidence, structured fields/citations, and non-executable invariants; split firewall; CLI and synthetic regression tests | Project team prepares an approved development-only retrieval/draft reference set; evaluate the approved corpus and provider; report semantic-quality limits without using held-out |

These estimates do not imply the end-to-end AI pipeline is ready for research
use. A01 has no real approved corpus shipped/configured, A02 has not had a live
provider and quality evaluation, and A03 has not been exercised by the team on
the external runtime. The present A03 workflow operates on an already
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
quality review are still needed before claiming a validated AI Workbench.**
