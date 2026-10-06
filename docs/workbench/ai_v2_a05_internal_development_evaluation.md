# AI V2 A05 — Internal development-only evaluation

**Status:** `PREPARED_NOT_RUN_REAL_MODEL_EVALUATION`

## Purpose

A05 evaluates whether the approved-evidence retriever and the evidence-grounded
StudySpec drafting path work on a fixed development-only question set. This is
an internal engineering/scientific evaluation by the project team, not a
request for outside labs or stakeholders to test an unfinished product.

The evaluator and metric contracts are implemented in A04. A05 cannot yet
produce a real AI-quality result: the active environment has no configured
V2 evidence corpus/provider settings, and this checkout does not contain a
project-approved development evaluation bundle. An API credential by itself
does not authorize sending unpublished research questions or protocols to a
provider. No provider request was made and no metric values below are invented.

`HELDOUT_STATUS = LOCKED_NOT_RUN`

## Metrics selected from the project Metrics page

The metric set is deliberately specific to the question being evaluated. Do
not combine these with the V1 candidate-ranking scores into one “AI accuracy”.

| A05 layer | Primary measures | Interpretation and limitation |
| --- | --- | --- |
| Evidence retrieval | Precision@5, Recall@5, MRR with case-bootstrap 95% intervals when eligible | Whether required evidence appears near the top. Denominator is answerable development queries; report query count and relevant-evidence count. |
| Draft fields | Exact categorical field match for assay/metric/unit; required-field coverage and extra-field precision | Exact match only for the discrete fields A02 is allowed to suggest. It is not full semantic StudySpec accuracy; mapping/neuron/intervention fields remain outside A02 authority. |
| Evidence grounding | Citation precision and unsupported-claim rate against the team's field-to-evidence reference IDs; citation retrieval membership | Reference-ID proxies only. They do not prove semantic entailment; results need to be described as automated traceability checks. |
| Abstention | Answer coverage, abstention accuracy, false acceptance, false rejection, selective risk | Whether the system returns a draft when evidence is adequate and stops when it is not. Interpret alongside error counts, not alone. |
| Guardrails/reproducibility | Forbidden-evidence hits, non-executable invariant pass rate, input/report hashes, provenance completeness | Safety and audit measures. Target zero forbidden hits and no autonomous approval/run; passing does not prove biological correctness. |

The project Metrics page also defines AP, P@5, Recall@5 and Coverage for
**candidate ranking**. Those apply to the existing 74-case V1 development
benchmark, not directly to RAG/draft quality. Keep them as a separate context:
the Notion roadmap records Full Workbench AP `0.6259`, effect-only AP `0.6592`,
and P@5 `0.80` for both. These are previously recorded development results,
not new A05 measurements and not evidence that Full Workbench beats
effect-only. Do not rerun or alter the frozen V1 score to dress up A05.

Metric definitions are in the [Notion Metrics page](https://app.notion.com/p/3ebff4b220598165889bf562cc5eeaa7?pvs=204); the
development workflow and guardrails are in the [October roadmap](https://app.notion.com/p/3f0ff4b2205981bd85bdc87c3c66c463?pvs=204).

## Evaluation design to freeze before the run

1. Project team selects and approves source papers/excerpts for an A01 corpus.
   Record source/chunk hashes, citations, locators, evidence scopes and review
   status. Exclude outcomes, benchmark labels and answer-revealing metadata.
2. Project team creates one development-only query/reference bundle. For each
   question, annotate relevant and forbidden evidence IDs, whether abstention
   is expected, required draft fields, categorical assay/metric/unit values,
   and field-specific evidence support. Save the bundle hash before running
   any provider.
3. Freeze the retriever version, prompt version, provider/model ID, decoding
   settings, corpus hash, metric cutoff `k=5`, and comparison procedure. Review
   provider retention/training terms before sending any unpublished content.
4. Run the same frozen questions through the agreed internal conditions. At a
   minimum report A01 retrieval alone and A02 with approved RAG. A template or
   no-retrieval baseline may be added only if it is defined before outputs are
   inspected and receives the same task/questions.
5. Score saved artifacts with `scripts/evaluate_workbench_v2_ai.py`. Report
   every metric denominator, available case-bootstrap intervals,
   missing/unassessable cases, failures, per-case errors and hashes. Do not use
   an LLM judge as the sole gold standard.
6. Summarize only what the automated reference checks establish. Semantic
   evidence support, biological correctness, wet-lab utility and broad user
   benefit remain unestablished by this computational evaluation.

There are no arbitrary pass thresholds in this task. The first run is a
descriptive baseline. If the group later wants go/no-go thresholds, freeze them
before a subsequent development evaluation rather than choosing them after
seeing this run.

## Readiness checklist

- [ ] Approved A01 corpus available at the configured external runtime path.
- [ ] Development questions and reference annotations internally prepared;
      no held-out labels/outcomes or answer-leaking metadata.
- [ ] Corpus, reference bundle, prompt, provider/model and `k=5` frozen and
      checksummed.
- [ ] Provider data-retention review complete before sending private text.
- [ ] A04 automated evaluator tests pass in the target environment.
- [ ] Evaluation run completed and report reviewed by the project team.
- [x] No outside lab or stakeholder is asked to test the unfinished product.
- [x] No held-out case has been read or run for this task.

Until the unchecked prerequisites are met, the truthful result is:

```text
A05_STATUS = PREPARED_NOT_RUN_REAL_MODEL_EVALUATION
RAG_QUALITY_RESULT = NOT_AVAILABLE
HELDOUT_STATUS = LOCKED_NOT_RUN
```
