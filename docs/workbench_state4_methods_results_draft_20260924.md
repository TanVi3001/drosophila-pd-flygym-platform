# Fly Research Workbench: first Methods/Results draft

Status: internal draft for the State 4 review branch. The results below are a
development-only retrospective ablation and are not a held-out claim.

## Methods

### Study question and scope

Fly Research Workbench is evaluated as a constrained prioritization layer for
Drosophila computational experiments. It is not presented as a new whole-brain
simulator, a disease model, or a replacement for wet-lab validation. The
question in this draft is narrower: does a frozen, auditable score produce a
useful ranking of public Shiu et al. Table 3 cases, and what changes when the
score's uncertainty and review gates are removed?

### Public benchmark and split

We used the frozen `shiu_public_benchmark_v2` registry containing 106 public
cases from the Shiu et al. Drosophila MN9 benchmark. The registry contains 74
development cases and 32 held-out cases. The development split was used for
this ablation and for in-sample threshold calibration only. The held-out split
was not used to select the formula, tune a parameter, or choose a result to
report here.

Each case was mapped to FlyWire-630 input and MN9 readout neuron IDs. The
mapping table records two named reviewer decisions, assay comparability, and
the exact IDs used by the simulation. The two MN9 readouts are
`720575940645521262` and `720575940660219265`.

### Frozen simulation input

The simulation component is the per-case `score_hz` from the completed and
frozen degree-preserving-rewire LIF batch. The score is the arithmetic mean of
the two MN9 readout rates under the condition, with the declared control and
condition provenance retained in the external freeze artifact. A score of zero
means that the declared computational readout was silent under this protocol;
it is not interpreted as biological absence.

### Locked Workbench score

The locked score is defined in
`configs/workbench/shiu_workbench_score_v1.json`:

```text
simulation_effect_hz       = frozen degree_preserving_rewire score_hz
uncertainty_hz             = mean(published MN9 SD at 50 Hz, left and right)
uncertainty_adjusted_score = simulation_effect_hz / max(uncertainty_hz, 1e-12)
full_workbench_score       = uncertainty_adjusted_score
                              * evidence_gate
                              * capability_gate
```

The evidence gate is one only when the mapping is approved and both reviewer
decisions plus the final review decision are approved. The capability gate is
one only when the assay is marked comparable, input IDs exist, and the exact
two declared MN9 readouts are present. The score builder is label-blind: it
does not use `reference_label`, `observed_response_fraction`, or the
`shortest_path` heuristic.

We compared four development-only systems:

1. `rewire_effect_only`: removes the uncertainty penalty and both gates.
2. `rewire_plus_uncertainty`: adds the published uncertainty penalty.
3. `full_workbench_locked`: adds the evidence and capability gates.
4. `random_reference`: a seeded random ranking used only as a negative
   reference.

Thresholds were fitted separately on the 74 development cases by balanced
accuracy. Because this is in-sample calibration, threshold precision/recall
are secondary diagnostics. The primary ablation readouts are ranking metrics:
average precision and precision@5.

## Results

The runner completed all 74 development cases with 100% score coverage. The
results are recorded in the external artifact
`development_ablation_v1/development_ablation.json` and the accompanying
`development_score_table.csv`.

| System | Average precision | Precision@5 | Coverage |
| --- | ---: | ---: | ---: |
| Rewire effect only | 0.659 | 0.800 | 1.000 |
| Rewire + uncertainty | 0.626 | 0.800 | 1.000 |
| Full Workbench locked | 0.626 | 0.800 | 1.000 |
| Random reference | 0.248 | 0.400 | 1.000 |

The rewire-based rankings were above the seeded random reference on both
primary ranking measures. Adding the published uncertainty penalty changed
the ordering enough to reduce average precision from 0.659 to 0.626, while the
top-five precision stayed at 0.800. The full score matched the
uncertainty-adjusted score exactly because all 106 mapped cases passed both
review/capability gates. Therefore this run does not identify an independent
benefit from those gates; it only demonstrates that the gates are enforced and
currently non-discriminating.

The in-sample threshold diagnostics for the full score were balanced accuracy
0.792, precision 0.857, recall 0.600, and four false negatives. These numbers
must not be presented as prospective or held-out performance.

## Interpretation and limitations

This result supports a limited software/methods claim: a frozen, provenance-
tracked rewire-LIF score can rank public cases above a seeded random reference
on the development split, and the score components can be ablated without
changing the frozen benchmark or reading labels during score construction.

It does not yet support the stronger claim that Workbench's evidence/context/
uncertainty policy improves experimental discovery. In this registry, evidence
and capability are constant, so that question is not identifiable. The next
scientifically useful benchmark must contain predeclared variation in mapping
quality, capability, or evidence confidence, or a prospective candidate set
where those factors can legitimately differ before outcomes are known.

Other limitations are one computational run per case, retrospective public
labels, a readout-specific LIF abstraction rather than behavior, and pending
independent second-operator reproduction. The 32 held-out cases remain locked
for the final evaluation after the score and analysis plan are frozen.

## Reproducibility command

From the FlyGym repository root, using the project Python environment:

```powershell
$Python = "E:\research-\.venvs\baseline-2024-312\Scripts\python.exe"
& $Python scripts/run_shiu_workbench_ablation.py `
  --rewire-scores "E:\research-\external\Drosophila_brain_model\results\workbench_benchmark_20260923\frozen_rewire_run02\per_case_scores.csv" `
  --output "E:\research-\external\Drosophila_brain_model\results\workbench_benchmark_20260923\development_ablation_v1\development_ablation.json"
```

The output is intentionally stored outside Git. The score specification,
runner, tests, and this draft are the reviewable source artifacts.

## Manuscript support artifacts

The reproducible figure/table generator is
`scripts/make_workbench_manuscript_figures.py`. It produces a pipeline diagram,
the development ablation comparison, the frozen score/zero-score distribution,
and manuscript-ready CSV/Markdown tables outside Git. The held-out readiness
check is separate in `scripts/audit_shiu_heldout_preflight.py`; it reports
readiness only and deliberately emits no held-out metrics.
