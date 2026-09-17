# Q1-facing manuscript protocol (working draft)

This document defines the evidence required for a methods paper. It is not a
promise of journal acceptance or quartile status; the target venue and its
current author and reviewer criteria must be checked again at submission.

## Central claim to test

The paper should test whether an auditable, scope-aware Workbench procedure can
prioritize computational candidates more usefully than simple effect-only or
random ordering within a declared Drosophila study. The claim is about the
procedure and its reproducibility, not universal biological truth.

The primary endpoint must be selected before the held-out benchmark is opened.
For public-data profile v2 it is precision@5 on the common assessable
held-out denominator. Average precision, precision@10, recall, false negatives,
coverage, class balance, and the full confusion matrix are secondary outputs.
The v2 registry contains 106 source rows (14 response-present and 92
response-absent), with 74 development and 32 held-out rows. These labels are
published aggregate response-presence labels, not biological significance or
causal-effect labels. If a denominator is too small or lacks a class, the
metric is reported as insufficient evidence.

## Evaluation design

1. Freeze public case inclusion, row locators, checksum, label policy, target
   grouping, and development/held-out split.
2. Tune thresholds and ranking policy only on development data or prespecified
   simulation calibration data.
3. Evaluate original-model reproduction, Workbench, random, effect-only,
   direct-connectivity heuristic, majority-class reference, and a declared
   degree-preserving directed-rewire null on the same held-out case IDs.
4. Repeat the computational screening with the declared 10 seeds, then run
   the three selected candidates (or the available bounded candidate set) with
   30 fresh seeds and a declared parameter sensitivity panel.
5. Reproduce a frozen subset from a clean environment. Record this as
   computational reproduction unless a genuinely separate human operator is
   explicitly identified; the verifier must never infer that role.
6. Report every unassessable case and QC failure separately. Do not move it to
   the bottom of the ranking or relabel it as a negative outcome.

The primary table must use the intersection of assessable held-out cases across
Workbench and every baseline. A partial intersection is reported as a scope
limitation and cannot support the main comparative claim.

Seeds are computational repeats. They are not fly counts, do not estimate
biological variation, and do not repair missing mechanisms in the simulator.

## Ablations and reviewer-facing stress tests

The paper should include ablations for at least:

- effect magnitude without stability/QC;
- stability without effect magnitude;
- the full scope-aware policy;
- removal of provenance compatibility checks;
- parameter sensitivity for the confirmation candidates;
- matched-input temporal control for the pulsed versus sustained E2 protocol;
- degree-preserving rewiring with explicit degree/weight/stratum invariants;
- an orientation/NaN/unknown-ID failure injection test.

The expected result is not that every ablation fails. The manuscript should
show where each component changes a decision and where the framework cannot
make a decision.

## Figures and tables

- Figure 1: study -> capability validation -> run -> QC -> compare -> handoff.
- Figure 2: software architecture and separate neural/platform interpreters.
- Figure 3: held-out benchmark performance with class balance and coverage.
- Figure 4: seed stability and parameter sensitivity for the bounded MN9 case.
- Figure 5: example evidence bundle and a blocked/non-assessable result.
- Table 1: backend capabilities, supported interventions, and known omissions.
- Table 2: benchmark protocol, split, label provenance, and failure counts.
- Table 3: candidate-level effects, uncertainty, stability, and decision group.
- Supplement: manifests, hashes, raw summary tables, environment lock, and
  independent reproduction log.

## Claim lock

Allowed wording is “reproducible, scope-bounded computational prioritization
procedure evaluated against a retrospective public-data benchmark” or
“scope-bounded methods artifact” until prospective wet-lab data are obtained.
The paper must not claim disease simulation, universal Drosophila validity,
equivalence to a real fly, driver-line specificity, causal MN9 inference, or
wet-lab cost savings from this retrospective computational evidence.

## Evidence sources

- Shiu et al. (2024), Nature: https://www.nature.com/articles/s41586-024-07763-9
- NeuronBridge: https://www.janelia.org/node/69264
- NC3Rs experimental design guidance: https://eda.nc3rs.org.uk/experimental-design
- CODECHECK reproducible computational research: https://codecheck.org.uk/
