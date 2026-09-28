# Methods boundary and workflow — PRE-HELDOUT draft

**Status:** manuscript Methods support, 2026-09-28. The retrospective
development analysis is complete; the final held-out evaluation is not run.
This text describes implemented behavior and separates it from evidence that
still requires human review.

## Research question and substrate

Fly Research Workbench asks whether an evidence-aware, auditable procedure can
help researchers prioritize supported Drosophila experiments under a fixed
candidate budget. The active quantitative case uses the Shiu et al. public
MN9/LIF material and the FlyWire-630 connectivity snapshot. It is a bounded
computational methods study. The historical neural-disease repository is a
separate track and supplies no Parkinson validation to this manuscript.

The public benchmark is frozen at 106 source-row cases, with 74 development
cases and 32 final held-out cases. A source row is the unit; driver lines,
frequencies, hemispheres, and simulation seeds are not treated as independent
biological cases. The published response-presence label is an aggregate
retrospective outcome and is not a significance test. Development is the only
split used for ablation and in-sample calibration at this stage.

## Implemented study workflow

```text
Question -> Evidence -> Capability -> StudySpec -> Approval
         -> Simulation -> RunManifest / Provenance -> QC
         -> Multi-metric analysis -> Prioritization -> Human decision
```

1. **Question.** A researcher declares a hypothesis, assay, primary readout,
   intervention candidates, control, and budget. Optional protocol intake
   creates only a draft; it cannot authorize mappings or start jobs.
2. **Evidence.** Versioned mapping records identify source citations,
   dataset/namespace, target IDs, context, reviewer, and review status.
   [`support.py`](../src/drosophila_pd/workbench/support.py) verifies record
   hashes. The 106-row source-linked registry still needs domain-scientist
   review; computational traceability is not driver-line validation.
3. **Capability.** The backend descriptor and `assess_study_support` check
   assay, intervention, readout, dataset/namespace, and context before a
   research study is approved. Unsupported or unreviewed candidates retain
   explicit states instead of receiving a fabricated score.
4. **StudySpec.** [`models.py`](../src/drosophila_pd/workbench/models.py)
   stores the fixed study configuration and candidate definitions with a
   configuration hash. The explicit `create-research-study` path applies the
   support gate; legacy demo study creation is a separate path.
5. **Approval.** [`service.py`](../src/drosophila_pd/workbench/service.py)
   binds researcher approval to the current StudySpec and support assessment
   hashes. Reassessment invalidates stale approval.
6. **Simulation.** Workbench schedules declared seeds and control/condition
   jobs through backend adapters. The MN9 case runs the pinned LIF backend in
   its own environment. Job failure, cancellation, and retry remain visible.
7. **RunManifest / Provenance.** Each run records study/job configuration,
   source revision and code state, environment, input hashes, artifact hashes,
   status, and error. The campaign and result directory preserve the link
   between a reported number and the exact run that produced it.
8. **QC.** Assay adapters and result checks mark missing, invalid, failed,
   silent, and out-of-scope outcomes explicitly. A silent computational MN9
   readout is a model observation, not a biological negative. Failed jobs are
   not silently imputed.
9. **Multi-metric analysis.** The research-study path pairs computational
   control and condition seeds, estimates effects and intervals, and records
   QC exclusions. The retrospective benchmark separately reports ranking
   metrics, including average precision, precision@5, and assessable coverage.
10. **Prioritization.** [`ranking.py`](../src/drosophila_pd/workbench/ranking.py)
    and [`selection.py`](../src/drosophila_pd/workbench/selection.py) rank
    eligible supported candidates under a declared budget and uncertainty
    rule. Exclusions and unused budget remain in the report.
11. **Human decision.** The researcher reviews the evidence bundle and
    ranking before choosing any real experiment. AI may assist in reading
    protocol text and explaining results; it does not create biological
    mappings, alter experiments, or approve scientific interpretation.

## Frozen benchmark score and analysis

The benchmark score is a separate, locked evaluation object. It uses the
frozen degree-preserving-rewire `score_hz`, a published MN9 uncertainty term
at the declared stimulus, and evidence/capability gates as specified in
[`shiu_workbench_score_v1.json`](../configs/workbench/shiu_workbench_score_v1.json).
[`score_lock.py`](../src/drosophila_pd/workbench/score_lock.py) constructs
scores without reading retrospective labels, observed response fractions, or
the shortest-path heuristic. It requires exact case-ID agreement with the
protocol, mapping and rewire-score inputs.

The development ablation compares rewire effect-only, rewire plus uncertainty,
full locked Workbench, and a seeded random reference. The current development
result is reported in the
[`Methods/Results draft`](workbench_state4_methods_results_draft_20260924.md):
full Workbench has average precision 0.626 and precision@5 0.800; effect-only
has 0.659 and 0.800. Both gates pass for every current case, so their
incremental ranking contribution cannot be estimated from this ablation.
The new support-gated budget-selection workflow is not evaluated by those
four retrospective systems and must not be claimed as a proven improvement.

The final held-out evaluator and the manuscript baseline list must be
reconciled before evaluation. The current score lock lists four ablation
systems; the broader manuscript scope also mentions a heuristic comparator.
Its definition and denominator must be frozen prospectively, without looking
at held-out outcomes.

## Validation levels and allowable interpretation

| Level | What it checks | Present state | What it cannot establish |
|---|---|---|---|
| Software validation | Unit/contract behavior, error paths, score construction and artifact hashing on synthetic fixtures | Targeted tests pass on Python 3.12 | Reproducibility of real runs or biological truth |
| Computational reproduction by owner | Re-run of development output plus a technical success/failure subset | Owner-reported `PASS`; role `same_operator` | Independent human reproduction |
| Independent second operator | Separate human, fresh checkout/environment, same frozen inputs, provenance and declared numerical tolerance, success and failure states | Pending Tuấn artifact and owner review | Biological validation |
| Final held-out evaluation | Once-only ranking comparison on the untouched final split with the frozen score and common denominator | `LOCKED_NOT_RUN` | Upstream-independent or prospective validation |
| Biological validation | Domain review and prospective/wet-lab test of model-to-assay meaning | Outside the current computational release | Cannot be inferred from code tests or LIF rates |

Methods and Results should report unassessable cases, coverage, class balance,
false negatives, silent scores, provenance and uncertainty. Reviewers should
see the distinction between a computational seed, a public source row, and a
biological replicate. Claims about Parkinson disease, gene specificity,
in-vivo behavior, or wet-lab savings require separate evidence.
