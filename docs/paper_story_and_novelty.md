# Paper story and novelty boundary

**Working title:** *An evidence-aware and reproducible workbench for planning connectome-based computational experiments*

**Status:** focused literature audit complete for Task 1; **NOVELTY_RISK = HIGH**; **PAPER_NOVELTY_GO_WITH_REFRAME**. This does not authorize or report held-out evaluation.

## Research problem and restrained claim

Connectome resources and neural simulators are not, by themselves, a complete operational process for checking whether a declared study is supported by available evidence and a backend, recording an approved study configuration, distinguishing unsupported scope from a failed run, and handing results to a human for review. Fly Research Workbench is a software/methods layer that implements such a process for selected Drosophila computational workflows.

The defendable paper story is **a potentially useful, scope-bounded system integration and its software validation**, not a new brain model, causal estimator, ranking algorithm, biological discovery engine, or proof that ranking improves experiment choices. Prior work already covers executable fly circuits (FlyBrainLab), connectome-informed circuit/perturbation prioritization (Pospisil et al.), neural experiment workflows (Mozaik), and general provenance/workflow systems (AiiDA, Snakemake, DataJoint). A 2026 preprint, PRAXIS-VirtualCell, also describes evidence-aware, abstaining, traceable virtual experiments in other biological domains. The exact operational combination may still be useful, but its uniqueness and practical value are not yet established.

## Primary contributions — limited to three

| Contribution | Prior-art gap (tentative, not proof of absence) | Repository implementation | Current evidence | Remaining evidence needed |
|---|---|---|---|---|
| 1. A scoped support contract that relates source-backed mapping records and declared assay/intervention/context to backend capabilities, emitting explicit supported, review-required, mapping-required or out-of-scope states. | FlyBrainLab supports Drosophila circuit exploration/execution and PRAXIS-VirtualCell proposes evidence-aware contracts, but this repository implements a specific Drosophila study-support data contract; the audit has not established that this exact combination is unprecedented. | `src/drosophila_pd/workbench/support.py`, `models.py`, `service.py`; support assessment and gated research-study path. | Code paths and related contract tests exist. The frozen benchmark's two gates pass all 106 cases, so it does not measure their incremental value. External biological/case review is pending. | Independent scientific review of mappings and assay comparability; adversarial supported/unsupported/review-required test cases; prospective evaluation of whether the contract catches invalid or underspecified plans. |
| 2. Hash-bound study assessment and researcher approval carried into execution, with explicit run/failure/QC and provenance artifacts. | Generic provenance and experiment workflows are established (AiiDA, Snakemake, DataJoint, Mozaik, Lancet). The possible contribution is domain-specific binding of the support assessment, StudySpec, approval and run records, not provenance itself. | `StudySpec` and stable configuration hash; approval binds to study and assessment hashes; adapters/jobs/manifests/artifacts and reproduction tooling. | Software-level tests and owner-side success/failure reproduction are reported. Independent second-operator reproduction remains pending; software tests do not validate biology. | Independent clean-environment reproduction; external software review; clear separation of the support-gated research path from legacy/demo paths; usability evidence. |
| 3. A transparent, frozen retrospective ranking application that separates workflow claims from score-performance claims. | Connectome-based candidate/circuit ranking already exists (notably the effectome study). The potential contribution is a transparent, reproducible application of a frozen ranking within the described support/QC workflow, not a novel ranking method. | Score lock, development ablation artifacts, baseline evaluator, frozen protocol and reporting assets. | On 74 development cases: effect-only AP 0.6592/P@5 0.80; full Workbench AP 0.6259/P@5 0.80; random AP 0.2477/P@5 0.40. Full Workbench does not beat effect-only. Gates are non-discriminative on the registered cases. Independent reproduction pending; held-out is not run. | Complete independent reproduction, scientific review, owner-approved future evaluation protocol/comparators, and the single authorized held-out evaluation if/when every gate is satisfied. Even positive retrospective results would not establish biological utility. |

These are candidate manuscript contributions, not proof of priority over all prior art. Avoid “first” claims unless a broader systematic review and direct software comparison support them.

## Closest prior work and contribution type

There is no single prior system closest on every axis:

- **FlyBrainLab** is closest in Drosophila-specific platform scope: it integrates connectomic/neuroanatomical data with executable circuit models and interactive functional exploration.
- **Pospisil et al. (2024)** is closest to the scientific prioritization objective: connectome-informed causal analysis identifies dominant circuits and testable perturbation hypotheses.
- **PRAXIS-VirtualCell (2026 preprint)** is closest to the broad evidence-aware/abstaining virtual-experiment architecture, but it is cross-domain, agentic, and not peer reviewed as of this review.
- **Mozaik** establishes prior art for experiment specification and automated neural simulation workflows.

Current Workbench is best described as **engineering/system integration with a potentially useful methods contract**. Whether that contract is scientifically meaningful depends on demonstrating that it prevents unsupported runs or improves researcher decisions; neither has yet been established prospectively. See [novelty matrix](novelty_matrix.md), [claim audit](novelty_claim_audit.md), and [reviewer attack](reviewer_novelty_attack.md).

## Current evidence and claim ladder

1. **Now:** report implemented software contracts, frozen development results and owner-assisted computational reproduction separately. The 74-case ablation shows the full score does not outperform effect-only; do not claim it does.
2. **After independent operator:** report computational reproduction only if a genuinely separate operator completes the declared clean setup and the verifier passes.
3. **After required approvals and one-time held-out run:** report retrospective generalization on the declared denominator and approved comparator set only. Current status remains `HELDOUT_STATUS = LOCKED_NOT_RUN`.
4. **Not established by current project evidence:** causal biological accuracy, behavior prediction, Parkinson model validity, wet-lab utility, intervention efficacy, cost reduction or clinical relevance.

## Decision

**NOVELTY_RISK = HIGH.** There is meaningful overlap with FlyBrainLab, effectome-based prioritization, established neural experiment workflows and general provenance platforms; gates are not discriminative in this benchmark; and performance does not show superiority to effect-only. The exact integrated contract remains a plausible software/methods contribution, but its uniqueness and user value are untested. PRAXIS-VirtualCell further weakens broad architecture-first claims.

**PAPER_NOVELTY_GO_WITH_REFRAME.** Proceed only with a narrow workflow/software framing and transparent limitations. If the group requires the primary claim to be a novel prioritization method or demonstrated biological advantage, the current project does not support it; a methodological pivot or new evaluation would be needed. This judgment uses no held-out outcomes.

## Scope boundary

This active paper is not a Parkinson's disease simulator, direct Drosophila behavior predictor, wet-lab replacement, biological validation, or clinical decision-support system. Historical disease-related repository artifacts must not be blended into the active benchmark as biological validation. See [`configs/workbench/active_manuscript_scope.yaml`](../configs/workbench/active_manuscript_scope.yaml).
