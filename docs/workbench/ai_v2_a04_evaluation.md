# AI V2 A04 — Internal evaluation harness

## Goal and boundary

A04 adds a deterministic, offline evaluator for saved A01 retrieval and A02
draft artifacts. It makes no model/provider request, does not run a simulation,
does not compute Workbench biological metrics, and does not approve a study.
The evaluator accepts only `development` or `synthetic_fixture` splits;
`held_out` and any other split are rejected. It never searches for or opens
benchmark outcome files.

This is an engineering and structured-output evaluation tool. Citation-ID
alignment means that a field references a project-authored supporting evidence
ID; it does **not** establish semantic entailment or biological truth. Real AI
quality cannot be reported until the team has an approved evidence corpus,
frozen development questions, and reference annotations prepared internally by
the project team. Testing an unfinished product with external labs or
stakeholders is not part of A04.

## Metrics

| Metric | Meaning |
| --- | --- |
| Recall@k | Fraction of reference-relevant evidence IDs found among the top *k*, macro-averaged across answerable cases. |
| Precision@k | Relevant evidence IDs in the top *k* divided by *k*, macro-averaged across answerable cases. |
| MRR | Mean reciprocal rank of the first relevant evidence item. |
| Abstention / false-accept / false-reject | Whether the retrieval-plus-draft path abstains when evidence is insufficient, and rates of accepting/rejecting those cases incorrectly. |
| Answer coverage / selective risk | Fraction of cases with a non-empty draft; case-level reference/guardrail error rate among answered cases. |
| Forbidden evidence hits | Count of explicitly disallowed evidence IDs returned by retrieval; target is zero. |
| Expected-field coverage / precision | Structured draft fields present versus the curated expected field set. This is not scientific correctness. |
| Citation precision / unsupported-claim proxy | Whether a cited field has an ID in its curated support set; this is not semantic entailment. |
| Citation retrieval membership | Fraction of draft citations that were actually returned by the retriever. |
| StudySpec categorical field accuracy | Exact, case-insensitive match for `assay`, `primary_metric`, and `primary_metric_unit` when a gold value is supplied. It is not full semantic StudySpec accuracy. |
| Non-executable invariant pass rate | Fraction of draft artifacts that did not approve/create studies, mappings, jobs, use the graph, or start simulation. |

The evaluator reports `null` when a metric has no eligible cases. It keeps
per-case rows so aggregate denominators can be inspected. nDCG is deliberately
not reported for the current binary relevance labels; use it only if the team
later defines a graded-relevance reference set. These metrics
include deterministic percentile-bootstrap 95% intervals for case-level means;
an interval is omitted when fewer than two eligible cases exist. They do not
measure wet-lab utility, biological validity, user satisfaction, or provider
safety beyond the recorded structural invariants.

## Input and run

The input is one JSON bundle with schema `workbench-v2-ai-evaluation-1`, a
unique evaluation ID, an allowed split, and cases containing only opaque IDs,
field names, retrieval outputs, and structured draft outputs. It must not
contain raw protocols, prompt text, evidence text, outcome labels, or held-out
data. The project team must keep actual reference annotations separate from
sealed outcomes.

Each case has these exact fields: `case_id`, `expected_relevant_evidence_ids`,
`expected_fields`, `expected_categorical_values` (gold values only for assay,
metric, or unit fields), `field_support` (field name to relevant evidence IDs),
`expected_abstention`, `forbidden_evidence_ids`, `retrieval` (`status` and
ordered `evidence_ids`), and `draft` (`status`, `proposed_fields`,
`field_citations`, plus boolean `approved`, `study_created`, `mapping_created`,
`job_created`, `graph_used`, and `simulation_started`). Unknown fields are
rejected. The report records the canonical input-bundle hash, report hash, and
metric denominators for audit.

Run from the platform repository:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
python scripts/evaluate_workbench_v2_ai.py --input E:\path\to\evaluation_bundle.json --k 5
```

To save a report, pass `--output` pointing to a new file in an existing
directory. The command refuses to overwrite an existing report. It is a pure
offline scorer and does not call the configured model provider.

## Current A04 state

- Implemented: input contract, split firewall, retrieval ranking metrics,
  Precision/Recall@k and MRR, abstention/coverage/selective-risk measures,
  forbidden-ID accounting, categorical field and citation-reference proxies,
  non-executable-state checks, deterministic bootstrap intervals, CLI, and
  synthetic regression tests.
- Verified now: synthetic fixture tests only.
- Not evaluated yet: real approved-corpus retrieval, live-provider draft
  quality, semantic citation support, and researcher usefulness.
- `HELDOUT_STATUS = LOCKED_NOT_RUN`.
