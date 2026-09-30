# Fly Research Workbench: canonical PRE-HELDOUT manuscript draft

**Status:** substantial internal draft; not submission-ready. All empirical values below are from the 74-case `DEVELOPMENT` split. `HELDOUT_STATUS = LOCKED_NOT_RUN`.

## Abstract (working)

Connectome data and neural simulators make computational experiments possible, but do not by themselves determine whether a proposed question is supported by available evidence, within a model's capabilities, or reproducible with interpretable failure states. We present Fly Research Workbench, a scope-bounded software workflow that links evidence and capability checks to a hash-bound StudySpec, simulation, provenance/QC, analysis, and human prioritization. We demonstrate the workflow on a retrospective Drosophila MN9 leaky-integrate-and-fire benchmark derived from published Shiu et al. material and a pinned FlyWire-630 connectivity input. The frozen registry contains 106 cases, partitioned into 74 development and 32 locked held-out cases. On development, the full locked score had AP 0.626 and P@5 0.80; effect-only scoring had AP 0.659 and P@5 0.80; a seeded random reference had AP 0.248 and P@5 0.40. Both evidence and capability gates passed every registry case, so their incremental ranking value is not identifiable in this dataset. Owner-side reproduction evidence is available; independent second-operator reproduction and held-out evaluation remain pending. The results support a reproducibility and workflow contribution, not biological validity, behavior prediction, or wet-lab efficacy.

## Introduction

Large connectome resources and computational models create a path from circuit hypotheses to simulation, but the path is not automatic. A wiring diagram is not itself an experiment specification; a simulator's ability to emit a number does not establish that the requested assay or biological mapping is supported. In practice, unsupported mappings, silent outputs, failed jobs, environment drift, and weak provenance can make a result difficult to interpret or reproduce.

FlyWire provides a whole-brain connectome resource [Dorkenwald et al., 2024](https://doi.org/10.1038/s41586-024-07558-y) and companion cell-type annotations [Schlegel et al., 2024](https://doi.org/10.1038/s41586-024-07686-5). Shiu et al. developed a Drosophila computational brain model and reported sensorimotor analyses [2024](https://doi.org/10.1038/s41586-024-07763-9). NeuroMechFly v2 addresses embodied sensorimotor control [Wang-Chen et al., 2024](https://doi.org/10.1038/s41592-024-02497-y). Fly Research Workbench does not replace or claim novelty over these models. Its question is whether a computational workbench can make the decision path around a proposed study explicit: what evidence supports a mapping, whether the configured backend can represent the requested study, what exactly will be run, how run provenance and QC are recorded, and how candidate outputs are handed back to a human decision-maker.

The contribution is a constrained workflow and its validation contract, not a new fly brain, disease model, or biological discovery. The targeted novelty comparison is in [`novelty_matrix.md`](novelty_matrix.md); direct prior-art review of neuroscience candidate-prioritization and virtual-screening systems remains incomplete.

## Methods

### Workflow and safety boundary

The operational path is:

```text
Question → Evidence → Capability → StudySpec → Approval
         → Simulation → RunManifest / Provenance → QC
         → Multi-metric analysis → Prioritization → Human decision
```

Question intake may create a draft but cannot approve mappings or launch a run. Versioned evidence records and reviewer states are checked separately from the backend capability descriptor. The StudySpec carries assay, intervention, readout, context, candidates and declared computational settings; approval binds to the assessed StudySpec. Unsupported, ambiguous, failed, silent and unassessable states remain explicit. A run manifest links source revision, environment, inputs, outputs, hashes and status. A researcher reviews the evidence and ranking before deciding whether to pursue a real experiment. AI assistance does not create biological mappings or approve scientific interpretation.

The explicit research-study path applies support checks; legacy demo pathways are not globally gated and are not evidence for the primary claim. The bounded quantitative case is the MN9 LIF computational readout with public connectivity inputs. An MN9 firing-rate value is a model output—not a probability of behavior, whole-animal behavior, or intervention efficacy.

### Benchmark, labels and split

The active retrospective registry is `shiu_public_benchmark_v2`: 106 source-table cases, 74 development and 32 held-out. The benchmark labels represent published model-versus-experiment response-presence/agreement, not an independently collected biological endpoint, significance test, or causal effect. Development is used for the reported ablation and any development-only calibration. Held-out labels/outcomes have not been inspected for this draft and the held-out evaluation has not been run.

The case-level computational mapping uses the frozen rewire-LIF score and declared left/right MN9 readouts. Mapping records include reviewer and assay-comparability fields; computational validation of IDs does not independently validate cell identity or assay equivalence. Scientific case review remains pending.

### Score and comparators

The score lock is `shiu_workbench_score_v1`, version 1, with `k=5` and higher scores ranked first. It starts from the frozen degree-preserving-rewire score; the uncertainty-adjusted version divides by the mean published MN9 SD at 50 Hz (floor `1e-12`); the full locked score multiplies by evidence and capability gates. The score builder excludes benchmark labels, observed response fractions and shortest-path values. The gate definitions and exact inputs are machine-readable in [`shiu_workbench_score_v1.json`](../configs/workbench/shiu_workbench_score_v1.json).

The completed development ablation compares four systems: rewire effect-only, rewire plus uncertainty, full Workbench locked, and seeded random reference (seed 17092026). The owner approved this comparator set under OPTION_A; `heuristic` and `original_model` are excluded. Protocol state is `OWNER_APPROVED_COMPARATORS_ONLY`, which freezes comparator choice but does not authorize evaluation. The 32-case set is potentially exposed after the documented label-display incident and cannot support a pristine confirmatory claim. No comparator is added or dropped based on held-out results; a new prospective validation design is required for a strong confirmatory claim.

### Ranking metrics and missingness

P@5 is the primary endpoint as specified by the score-lock; AP is a secondary whole-list ranking summary, with coverage and unassessable count/reasons also reported. `k=5` is the project's frozen choice, not a number prescribed by Shiu et al. Scores rank descending; ties break by ascending string case identifier. Zero is a valid score. Missing/non-finite values are unassessable and never converted to negative labels. The final protocol defines the common-assessable denominator and other reporting rules; metric rationale is in [`evaluation_metric_rationale.md`](evaluation_metric_rationale.md).

### Validation levels

| Evidence class | Current state | What it establishes / does not establish |
|---|---|---|
| Software validation | Targeted contracts and regression tests have passed in prior recorded runs; this package runs relevant tests again. | Software behavior on declared fixtures, not successful scientific generalization. |
| Owner computational reproduction | Owner reports byte-identical development ablation and a success/failure subset verifier PASS; operator role is `same_operator`. | Reproducibility by the owner for those artifacts, not independence or biological validity. |
| Independent second-operator reproduction | Pending Tuấn's clean independent execution and verifier artifact. | If passed, cross-operator computational reproduction of tested artifacts only. |
| Held-out evaluation | `LOCKED_NOT_RUN`; protocol approval and execution commit still pending. | No generalization evidence yet. |
| Biological validation | Not completed; scientific case review pending and no wet-lab validation in scope. | Nothing about causal biology, behavior or intervention success. |

## Results — DEVELOPMENT only

The frozen owner development artifact contains 74 assessable development cases. Ranking results are:

| System | AP | P@5 | Coverage |
|---|---:|---:|---:|
| Rewire effect-only | 0.6592 | 0.80 | 1.00 |
| Rewire + uncertainty | 0.6259 | 0.80 | 1.00 |
| Full Workbench locked | 0.6259 | 0.80 | 1.00 |
| Seeded random reference | 0.2477 | 0.40 | 1.00 |

Full Workbench does not outperform effect-only on these data: AP is lower and P@5 is tied. The rewire-based systems exceed the seeded random reference on these development metrics, but this is retrospective development evidence and is not an independent or prospective estimate. Every one of the 106 registered cases passed the evidence and capability gates, so their incremental ranking value cannot be identified. The frozen record and interpretation are detailed in [`development_evidence_summary.md`](development_evidence_summary.md).

Owner-side records report successful reproduction of the development output and both a completed technical subset case and an explicit controlled failure/QC case. These records use the same operator. They are not an independent reproduction. The independent operator handoff is pending completion and owner review.

### Final held-out evaluation — pending locked one-time execution

`HELDOUT_EXPOSURE_STATUS = UNVERIFIABLE`. `HELDOUT_PRISTINE_CLAIM = UNAVAILABLE`. `HELDOUT_STATUS = LOCKED_NOT_RUN`. `HELDOUT_EXECUTION_AUTHORIZED = FALSE`. No held-out metric is reported. Comparator approval is limited to selection and does not unlock this evaluation set. Do not describe it as pristine or strictly confirmatory; a new prospective validation design is required for a strong confirmatory claim.

## Discussion

The development evidence supports a limited methods contribution: the repository provides a structured route from question and support assessment to a reproducible computational run and human-reviewed prioritization, while preserving failure and uncertainty states. The owner-side reproduction records suggest that declared computational artifacts can be reconstructed under the tested conditions. The data do not establish that evidence/capability gates improve ranking: those gates were constant across the registry. Nor do they establish ranking superiority over effect-only scoring.

Important limits are the small retrospective benchmark, labels inherited from a published model-versus-experiment comparison, one bounded MN9 LIF readout, pending expert review of scientific comparability, pending independent operator reproduction, and no wet-lab or direct behavioral validation. A future extension could connect supported neural studies to an embodied FlyGym/NeuroMechFly workflow, but such coupling requires its own validated mappings, protocol and behavioral endpoints. It cannot be inferred from MN9 rates.

The paper should emphasize transparency and auditability if held-out rankings are similar to effect-only; if results are materially weaker or unstable, preserve the negative result and pivot or stop rather than re-tune on the same 32 cases.

## Claims boundary

MN9 firing/activity is a computational neural readout. It is not automatically behavior probability, whole-animal behavior, a Parkinson disease phenotype, clinical relevance, or biological intervention efficacy. The Workbench supports prioritization for human consideration; it does not automatically alter or authorize wet-lab experiments.

## Reproduction pointers

- [PRE-HELDOUT readiness](paper_preheldout_readiness.md)
- [Proposed final evaluation protocol](../configs/workbench/final_evaluation_protocol_v1.json)
- [Second-operator contingency](independent_reproduction_contingency.md)
- [Pre-submission checklist](pre_submission_checklist.md)
