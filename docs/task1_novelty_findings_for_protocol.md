# Task 1 novelty findings for later protocol work

**This is a recommendation record only. Task 1 does not approve or edit the final evaluation protocol, score lock, split, k=5, comparator set, approval state, or executor.**

## Findings to carry forward

1. The development report says both evidence and capability gates pass for all 106 registered cases. The active ranking benchmark therefore cannot estimate the incremental ranking value of those gates.
2. Frozen development results do not show full Workbench beating effect-only: AP 0.6259 vs 0.6592, and P@5 0.80 vs 0.80. Any final evaluation must retain this result as context rather than imply a known uplift.
3. Connectome-informed intervention/circuit prioritization is prior art (Pospisil et al. 2024); the paper should evaluate the frozen ranking as a bounded application, not claim ranking itself as a novel algorithm.
4. Proposed comparator scope is still an owner decision in the existing protocol. This Task 1 does not choose or approve comparators.
5. The independent second-operator reproduction and external scientific case review remain separate gates. Owner-assisted reproduction is not independent reproduction.

## Recommendations for the future authorized protocol task

- Preserve the score formula, k=5, split membership, frozen artifacts, and held-out lock unless a separately authorized protocol revision is explicitly approved before outcome access.
- Do not use the 32 held-out cases to improve novelty, tune weights, resolve feature choices, or select comparators. Keep `HELDOUT_STATUS = LOCKED_NOT_RUN` until all independent reproduction, scientific review, protocol approval, and execution gates are satisfied.
- If the goal is to evaluate gate utility, design a separate prospective or development-only set with genuine supported, review-required, and out-of-scope variation; do not retrofit labels or claims into the locked benchmark.
- Report the common assessable denominator, coverage, unassessable reasons, all predeclared baseline results, and uncertainty; do not suppress weak/non-superior results.
- Treat a held-out ranking result as retrospective prioritization evidence only. It cannot support behavioral, disease, causal biological, wet-lab, or clinical claims by itself.

No protocol/evaluator changes or held-out actions were performed for this record.
