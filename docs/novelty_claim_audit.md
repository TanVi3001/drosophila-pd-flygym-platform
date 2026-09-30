# Novelty claim audit

**As of 2026-09-30 · Narrative, targeted review; not systematic.** This audit separates software functionality from evidence that the functionality improves science.

## A. Not novel alone

| Candidate claim | Prior art | Audit |
|---|---|---|
| “We simulate a Drosophila brain/connectome.” | Shiu et al.; Neurokernel; FlyBrainLab | Not novel. The repository uses an existing LIF/model ecosystem; it does not introduce a new whole-brain model. |
| “We enable virtual neural experiments and capture an experiment specification.” | Mozaik; Lancet; FlyBrainLab | Not novel alone. Experiment/stimulation specifications and automated neural experiment workflows are established. |
| “We record workflow provenance and checksums.” | AiiDA; Snakemake; DataJoint | Not novel alone. Hashes and manifests are engineering/reproducibility controls. Their correct implementation can still be valuable. |
| “We rank candidates / prioritize perturbations using a connectome.” | Pospisil et al. 2024 and earlier circuit analysis | Not novel alone. Pospisil et al. explicitly use connectome-informed causal estimation and propose dominant circuits/testable hypotheses. |
| “We include a human review step.” | Common workflow and scientific governance practice; FlyBrainLab supports interactive exploration | Not novel alone absent a precise, evaluated decision method. |
| “We run neural simulations through a web/API workbench.” | FlyBrainLab, Mozaik, Neurokernel and other platforms | Not novel alone. |

## B. Possibly novel integration — narrow and not yet established

### Candidate claim

> A Drosophila connectome-based research workflow that binds explicit evidence and simulator-support assessments to a hash-identified study configuration and human approval, preserves supported / review-required / out-of-scope and run-failure states through provenance/QC, and exposes the resulting computational comparisons as a bounded human-reviewed shortlist.

This is the strongest candidate because its unit of contribution is the operational contract across stages, not an individual score, simulation engine, checksum, or ranking algorithm. It is distinct in *emphasis* from FlyBrainLab's exploratory executable-circuit platform, Mozaik's neural simulation workflow, and Pospisil et al.'s causal effect estimator. But this review does **not** prove no prior system has the same contract. PRAXIS-VirtualCell's recent preprint overlaps strongly at the architecture level (evidence-aware execution, abstention, traceable virtual experiments), reducing the scope of any “first” claim. It is cross-domain and not peer reviewed, which is relevant context, not a reason to omit it.

### Repository implementation and evidence boundary

- `src/drosophila_pd/workbench/support.py` represents sourced `MappingRecord`s, checks dataset/namespace/context, model readiness, assay/intervention compatibility, and returns supported, review-required, mapping-required, or out-of-scope assessments. It explicitly says computational support does not establish biological validity.
- `src/drosophila_pd/workbench/models.py` provides `StudySpec` and configuration hashing; `src/drosophila_pd/workbench/service.py` ties approval to the assessment and study hashes and blocks a support-gated execution/selection if the approval is missing or stale.
- The Workbench has simulation adapters, job states, manifests, artifact handling, QC/analysis, ranking/selection and reproduction/handoff modules. These are implemented software paths; not every legacy/demo entry point is necessarily gated, so manuscript wording must stay scoped to the support-gated research-study path.
- Frozen development evidence covers 74 cases. Full Workbench AP is 0.6259 vs effect-only 0.6592; P@5 is 0.80 for both. Random AP is 0.2477, P@5 0.40. All registered cases passed both evidence and capability gates, so the benchmark cannot identify their incremental ranking contribution. Do not claim gates improve ranking or discovery from these data.
- Owner-side reproducibility checks do not establish independent second-operator reproduction. Held-out results are unavailable and must stay locked.

### What would establish this contribution more convincingly

1. External reviewers validate mappings, assay comparability, and the support/abstention semantics.
2. Independent operator reproduces a supported success and explicit failure/QC path from a clean installation.
3. A predeclared evaluation demonstrates useful behavior on cases where gates *actually vary*, with a fair denominator and without changing the frozen score after observing outcomes.
4. A user study or prospective workflow study measures whether the contract catches unsupported studies, improves protocol completeness, or changes expert decisions; computational ranking metrics alone cannot establish this.
5. A versioned direct feature comparison with FlyBrainLab, Mozaik and effectome methods documents which functions overlap and tests whether the integration is useful beyond a wrapper.

## C. Unsupported novelty or impact claims

The current repository/evidence does not support claims that Workbench:

- is the first or only trustworthy/evidence-aware virtual experiment system;
- improves biological discovery, causal inference, or experiment success;
- outperforms effect-only ranking in development data or generalizes to held-out cases;
- predicts fly behavior or converts MN9 firing into organism-level locomotion;
- models Parkinson disease, human disease, treatment response, or clinical outcomes;
- selects validated intervention targets or replaces expert judgment;
- reduces wet-lab time/cost or increases experimental hit rate;
- has completed independent second-operator validation, or biological/wet-lab validation.

## Mandatory closest-prior comparison

| Question | Assessment |
|---|---|
| Closest Drosophila system? | **FlyBrainLab**: executable circuit construction and interactive functional exploration grounded in Drosophila anatomy/data/models. |
| Closest prioritization method? | **Pospisil et al. (2024)**: connectome-informed causal effects and selection of dominant circuits/testable perturbation hypotheses. |
| Closest broad architecture? | **PRAXIS-VirtualCell (2026 preprint)**: evidence-aware, auditable virtual experiment organization with abstention, but different biological domain and agentic orchestration. |
| What can both FlyBrainLab and Workbench do? | Work with Drosophila neural data/models and support computational circuit/question exploration. |
| What does FlyBrainLab clearly contribute beyond this Workbench? | A mature, interactive platform for connectome/anatomy exploration and executable circuit construction; this Workbench should not claim parity in those capabilities. |
| What does Workbench currently implement that the cited FlyBrainLab paper does not explicitly report? | A specific evidence/mapping + backend-capability assessment, configuration-hash-bound researcher approval, explicit support/out-of-scope states, run manifests/QC and frozen ranking/reproduction contracts. “Not reported in the paper” is not proof the current FlyBrainLab software lacks it. |
| Scientifically meaningful difference? | Potentially, if it reliably prevents unsupported mappings/runs and makes failure/reproduction auditable. This is plausible workflow utility, not yet shown as improved biological inference or experimental decisions. |
| Experimentally evaluated? | No. The development benchmark's two gates pass every registered case and do not vary; full Workbench does not outperform effect-only in AP. No prospective user or biological evaluation. |
| Likely reviewer label today? | **Engineering/system integration with a potentially useful methods contract**, not a new neural method. With external validation and demonstrated decision utility, it may support a methods/software contribution. |

## Decision

**NOVELTY_RISK = HIGH**
**PAPER_NOVELTY_GO_WITH_REFRAME**

The paper may proceed as a narrowly framed software/methods manuscript, not as a novelty claim about connectome simulation, candidate ranking, or biological discovery. Do not use “first” absent a broader, reproducible systematic review and a direct software-level comparison.
