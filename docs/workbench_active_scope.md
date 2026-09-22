# Active manuscript scope: Fly Research Workbench

This file is the human-readable boundary for the current manuscript track. It
does not convert a computational audit into biological sign-off.

## Active track

The active paper is a methods/workbench paper with a retrospective public-data
benchmark and one bounded sensory/MN9 LIF case. Its claim is:

> A reproducible, scope-bounded computational prioritization procedure evaluated
> against a checksum-pinned retrospective public-data benchmark.

The active evidence is limited to capability checking, StudySpec contracts,
provenance, QC, uncertainty, ranking/abstention, held-out discipline, baseline
comparison, and an inspectable MN9 computational case.

## Explicitly separate track

The repository `../drosophila-pd-neural-disease` contains an older and separate
neural-disease validation track. Its Chen/Pozo/Parkin artifacts may be cited as
historical context or negative/limitation evidence, but they must not be merged
with the active Workbench benchmark as if they were one biological validation
dataset.

In particular, the active manuscript must not claim that an organism-level proxy,
driver-defined target, or connectome weight attenuation is a gene-specific
biological model.

## Current evidence state

The v2 public registry has 106 cases: 74 development and 32 held-out, with 14
positive and 92 negative response-presence labels. Integrity and protocol-freeze
checks pass. Human source/mapping review is still pending.

The first partial held-out score preparation is stored in
`reports/workbench/shiu_v2_heldout_evaluation.json`. It has five available
systems, but one heuristic case is unassessable and the required
degree-preserving-rewire score mapping is missing. Therefore it is not a
complete comparative result.

The report also shows that the current published-field Workbench score has the
same summary metrics as effect-only and original-model scores. This is a finding
to investigate, not evidence of Workbench superiority.

## Next human gates

1. Domain reviewers approve or reject section/assay comparability for each case.
2. A real graph-null backend supplies degree-preserving-rewire scores for the
   exact frozen case IDs, or the comparison remains explicitly partial.
3. A second human operator reproduces a frozen subset from a clean install.
4. Both repositories are committed and tagged only after the evidence review.
