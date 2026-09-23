# Public benchmark protocol: Shiu retrospective snapshots

The active manuscript track uses the v2 Table 3 registry below. The v1
21-case registry remains a historical computational snapshot and must not be
silently mixed with v2 metrics.

## Active v2 registry

The machine-readable active registry is
`configs/workbench/shiu_public_benchmark_v2.json`. It contains 106 Table 3
source rows, a 74-case development split and a 32-case held-out split. Its
labels are published response-presence labels, not biological significance or
causal-effect labels. Validate it with:

```powershell
python scripts/validate_shiu_benchmark_registry.py `
  --registry configs/workbench/shiu_public_benchmark_v2.json `
  --workbook path/to/41586_2024_7763_MOESM2_ESM.xlsx
```

Scientific mapping and assay-comparability decisions remain pending until two
domain reviewers complete the review packet at
`reports/workbench/shiu_v2_scientific_review_packet.csv`.

## Historical v1 snapshot

The machine-readable registry is
`configs/workbench/shiu_public_benchmark_v1.yaml`. It contains 21 source rows
from Shiu et al. (2024), Supplementary Table 11B, with exact worksheet rows,
FlyWire IDs, section-specific assay context, a public source locator, and a
checksum for the downloaded XLSX.
Run the source validator before evaluating a model:

```powershell
python scripts/validate_shiu_benchmark_registry.py `
  --registry configs/workbench/shiu_public_benchmark_v1.yaml `
  --workbook path/to/41586_2024_7763_MOESM2_ESM.xlsx
```

## What the label means

The source column is `Correct (i.e., aligns with experimental results?)`.
The validator resolves that column from the nearest section header; it must not
assume one Excel column for the whole worksheet. Rows 3--17, 165, 167 and
174--176 use column F, while row 180 uses the JON-silencing column G. `1` is
mapped to the benchmark label `positive` and `0` to `negative`. This is an
author-reported model-versus-experiment agreement label. It is not a positive
or negative biological effect, and it is not an independently collected
wet-lab label. The evaluator must therefore report this as a retrospective
agreement benchmark only.

The rows belong to different source sections and cannot share an implicit
assay contract. Each case records its source section, stimulus, intervention,
readout and header row. The mapping remains `PENDING_SCIENTIFIC_REVIEW` until
a reviewer confirms that a Workbench output is comparable to the source
quantity. Unsupported or ambiguous cases must be reported as unassessable.

The source article identifies the computational modeling results separately
from behavioral data in Supplementary Table 9. The benchmark must not treat
the model's own output as an experimental ground truth.

## Split and leakage controls

The registry has 13 development cases and 8 held-out cases. The split is
deterministic by source row and is frozen in the registry. The selected cases
are unique by exact FlyWire ID; repeated rows are excluded from this v1
snapshot so one target does not appear in both partitions. The held-out set
must not be used for threshold selection, intervention tuning, or debugging
decisions that are then reported as evaluation.

This is a useful first gate, not a final universal benchmark. The source table
has a narrow model and experimental scope, class imbalance (17/4), and labels
that inherit the original authors' comparison procedure. A Q1 submission
should add a second public source or a predeclared multi-table extension after
the v1 evaluator is locked, and should report whether conclusions change.

## Required comparison

For the same held-out case IDs within a reviewer-approved mapping, report at
least:

- Workbench ranking;
- random ranking with a declared seed protocol;
- effect-only ranking;
- one simple heuristic baseline;
- confusion matrix, precision, recall, precision@k, false negatives, class balance, and assessable coverage.

Unassessable model outputs remain visible and are not converted to negative
cases. Confidence intervals must state the resampling unit and must not be
described as biological uncertainty intervals.

The release gate requires a machine-readable comparison with `workbench`,
`random`, `effect_only` and `heuristic` systems, the frozen protocol hash, the
`held_out` split, and complete metrics for every system.

Once the reviewer-approved score mapping exists, prepare that comparison with:

```powershell
python scripts/workbench.py benchmark-prepare-comparison `
  --protocol configs/workbench/shiu_public_benchmark_v1.yaml `
  --scores-by-system path/to/scores_by_system.json `
  --random-seed 17 `
  --output benchmark_comparison.json
```

The score file must contain Workbench, effect-only and heuristic scores for
the declared cases. The command generates the random scores, calibrates every
system on development cases only, and applies the frozen calibration to the
held-out split.

The generated report also contains `matched_evaluation`. A Q1 release requires
`status: COMPLETE` and a common assessable denominator covering every held-out
case. If a backend cannot represent a section, the report must remain partial
with explicit `unassessable_case_ids_by_system`; those results are useful for
scope auditing but are not a matched publication comparison.

The evaluator may be run with `--allow-partial` to preserve available systems
and explicitly record missing score mappings. Missing development scores are
excluded from threshold calibration and remain unassessable; they are never
converted into negative labels. A partial report is not release-ready.

## FlyWire-630 structural-null preparation

The scalable runner `scripts/materialize_connectome_rewire.py` materializes a
new connectivity parquet for one declared directed double-edge-swap null. It
preserves source-local edge attributes, in-degree, out-degree, excitatory
stratum, and the ID-to-index mapping. It writes a sidecar manifest containing
input/output checksums, seed, swap count, attempt count, and invariant results.
The output is only a connectivity input for the separate neural LIF runner;
it does not create the 106-case benchmark score mapping and must not be used
as evidence of biological plausibility. Reviewer-approved source/input and
readout mappings are still required before generating benchmark scores.

The first full-dataset execution declaration is pinned in
`configs/workbench/flywire630_graph_null_v1.yaml`: one replicate, seed
`20260922`, and `1,000,000` swaps against the checksum-pinned connectivity-630
artifact. Its generated parquet and sidecar manifest remain outside Git under
the declared artifact root.

## Shiu v2 mapping and rewired LIF batch gate

`scripts/build_shiu_v2_mapping_template.py` creates the 106-row mapping sheet
at `configs/workbench/shiu_v2_flywire630_mapping.csv`. Reviewers must fill
exact FlyWire-630 input and readout IDs, assay comparability, and two-person
sign-off. The mapping records `reviewer_1_decision` and
`reviewer_2_decision` separately; `review_decision=APPROVED` is valid only
when both are explicitly `APPROVED`. The optional source-grounded prefill uses the upstream
`Drosophila_brain_model/sez_neurons.pickle` mapping and verifies IDs against
the FlyWire-630 completeness inventory; this is computational evidence, not
biological approval. Cell-type names are never converted to IDs by inference.
Reviewer names may be supplied explicitly with `--reviewer-1` and
`--reviewer-2`; naming reviewers does not change the approval gate.

`scripts/run_shiu_v2_rewired_lif_batch.py` validates that sheet and runs only
rows with `mapping_status=APPROVED`, `assay_comparable=YES`, both MN9 left/right
readout IDs, and two reviewer names. It runs a no-input control and the
declared condition with the same seed at the v2 benchmark stimulus of 50 Hz.
The scalar score is the arithmetic mean of the two MN9 rates, and the output
also records each per-readout rate plus the control delta.
Pending, ambiguous, unassessable, or failed rows remain visible and never
become negative scores. Without complete approved mapping, the command emits
`BLOCKED_MAPPING_REQUIRED` or an explicitly `PARTIAL_MAPPING` result.
