# Fly Research Workbench v0.1 - implementation status

**Recorded:** 2026-09-16  
**Scope:** software and public-data computational evidence only. This record
does not certify biological validity or publication readiness.

## Verified release evidence

- Platform full suite: **582 passed, 2 skipped** under the Python 3.12
  FlyGym runtime. The two skips are optional-environment tests.
- Neural full suite: **190 passed** under the separate Python 3.12 Brian2
  runtime.
- Current Workbench/Q1 gate regression subset: **17 passed**; the full
  platform suite below includes the service, store, adapter, web, benchmark,
  and reproduction tests.
- `pip check` passed in both locked runtimes; `compileall` passed in both
  repositories.
- The target environments remain isolated: the Workbench process uses the
  FlyGym interpreter and the LIF subprocess uses the Brian2 interpreter.

## Plan-to-evidence matrix

| Plan area | Current state | Evidence or boundary |
|---|---|---|
| Capability matrix and study contracts | Implemented | `StudySpec`, backend descriptors, assay adapters, candidate intervention validation |
| Trial denominator and silent trials | Implemented | LIF manifest is authoritative; silent readouts remain in the denominator |
| ID, namespace, and dataset checks | Implemented for LIF/bridge paths | Declared completeness inventory plus optional annotation registry; 630 and 783 remain separate |
| NaN/Inf/orientation QC | Implemented | Locomotion and neural assay tests reject invalid readouts |
| Metric semantics | Implemented | Historical displacement speed is retained; path speed has a separate versioned name |
| Intervention semantics | Implemented | Scale zero is preserved; outgoing synapse block is not called neuron death |
| New-config E2E | Implemented for motor and LIF | New processes create spike/metrics or FlyGym artifacts and manifests; no legacy artifact-only pass |
| Worker, resume, failure, and provenance | Implemented | SQLite claims, one-worker lock, stale-job recovery, fixed result paths, checksums, environment, code-state digest |
| CLI/API parity | Implemented and regression-tested | Both call the same `WorkbenchService`; API route registration and CLI tests pass |
| Motor sample | Computational pilot complete | Fresh control/perturbation pair; path-speed comparison is exploratory |
| Sensory/MN9 sample | Public FlyWire-630 computational pilot complete | Explicit MN9 readout; screening has 10 paired seeds and confirmation has 30 fresh paired seeds |
| Brain-to-body bridge | Explicitly bounded | Existing bridge remains optional and readout-gapped; no causal neural-to-behavior mapping is claimed |
| Evidence bundle and human review | Implemented as a gate | Report/handoff templates exist; ranking approval is bound to an exact report hash |
| AI synthesis | Safe fallback implemented | Template reports work without an AI API; AI may not mutate QC, ranking, or evidence |
| Frozen public benchmark | Source freeze complete; comparative gate open | `shiu_public_benchmark_v1.yaml` contains 21 verified rows across four sections (13/8 split, 17/4 source labels); section mapping, scientific sign-off and held-out evaluation remain pending |
| Independent reproduction | Verification tooling implemented; reproduction not complete | `scripts/verify_workbench_reproduction.py` and `workbench verify-reproduction` compare success/failure manifests, provenance and per-job metrics; a second operator must still run it |
| Wet-lab validation | Not in this sprint | No new wet-lab data is assumed or claimed |

## Current computational artifacts

- Motor pilot: `.workbench/motor_case_py312/`.
- Generic LIF smoke: `.workbench/lif_case_py312/`.
- Final annotated MN9 pilot: `.workbench/sensory_mn9_case_final_py312/`.
- 10-seed screening campaign: `.workbench/sensory_mn9_screening_10seed_20260916/`.
- 30-seed confirmation campaign: `.workbench/sensory_mn9_confirmation_30seed_20260916/`.
- MN9 public ID registry:
  `../drosophila-pd-neural-disease/annotations/flywire630_sensory_mn9_public.csv`.
- Public sensory study specification:
  `configs/workbench/sensory_mn9_lif.yaml`.

The MN9 manifest records the 22-row registry checksum
`ce8058f56b33ac105c62ade6ac257ecec02247547335a10bf16ae0bcd533a25b`, the
FlyWire-630 dataset ID, completeness/connectivity hashes, and a dirty-worktree
digest. The dirty flag is intentional: the current development changes have
not been committed and must be reviewed before a release archive is made.

## Publication gates

The repository now satisfies the software-correctness gate for v0.1, but it is
not yet a Q1 paper package. The remaining evidence and release actions are:

1. Obtain scientific sign-off for the 21-case freeze and compare Workbench
   ranking against random, effect-only, and simple heuristic
   baselines; report confusion matrix, precision, recall, precision@k, false
   negatives, class balance, and model-assessable coverage.
2. Preserve and report the completed 10-seed screening and fresh 30-seed
   confirmation protocol for the bounded MN9 computational study, with
   sensitivity results kept separate from biological replication. This seed
   gate currently passes; it is not a substitute for independent reproduction.
3. Have a second operator reproduce a frozen subset from a clean environment,
  including both success and failure artifacts.
4. Obtain scientific review of the MN9 input/readout interpretation and define
  a prospective wet-lab assay before making a biological prioritization claim.
5. Commit and tag both repositories from clean worktrees only after the
   preceding evidence has been reviewed.

Until these gates pass, valid wording is “reproducible computational
prioritization pilot” or “methods/workbench software artifact.” Invalid wording
includes universal Drosophila validity, disease simulation, equivalence to real
flies, causal MN9 inference, or demonstrated wet-lab cost savings.

## Follow-up audit: 2026-09-16

The first public benchmark registry is now present at
`configs/workbench/shiu_public_benchmark_v1.yaml`. It contains 21 unique
FlyWire-ID rows from four sections of Shiu et al. Supplementary Table 11B, a
13/8 development and held-out split, the source checksum, section-specific
assay context, and an explicit model-vs-experiment agreement label policy. The
independent validator
`scripts/validate_shiu_benchmark_registry.py` verified the registry against
the downloaded public XLSX: 21/21 rows matched, with 17 positive and 4
negative agreement labels. It now resolves the repeated label header by
section; row 180 is validated against column G rather than column F used by
the preceding sections.

This closes source integrity preparation for the benchmark, not the publication
gate. The section-specific mapping and source labels still require a second
scientific review, and the benchmark has not yet been run with Workbench,
random, effect-only, and heuristic baselines on the held-out split. The source
table's mixed assay scope and class imbalance must remain visible in any
manuscript.

The following release-gate records are now machine-readable:

- `configs/workbench/mn9_biological_review.yaml` for target/driver-line and
  prospective wet-lab protocol review;
- `configs/workbench/reproduction_manifest.template.yaml` and
  `docs/workbench_reproduction_protocol.md` for second-operator reproduction;
- `scripts/verify_workbench_reproduction.py` and the `verify-reproduction`
  CLI command for deterministic manifest/output comparison;
- `src/drosophila_pd/workbench/benchmark_baselines.py` for development-only
  score calibration and declared random/effect-only/heuristic comparison;
- `scripts/workbench_release_gate.py` for the all-gates PASS/BLOCKED decision.

Running the release gate currently returns `BLOCKED` for the expected reasons:
the seed manifests are now supplied and pass, while benchmark mapping/source
review, held-out evaluation, independent reproduction, biological review,
clean worktrees, and release tags remain open. This is an intentional safety
result, not a failed biological finding.

## Execution evidence update: 2026-09-16

The declared MN9 computational seed protocol has now been executed with fresh
artifacts:

- Screening: `\.workbench/sensory_mn9_screening_10seed_20260916/` — `PASS`,
  20 completed jobs (10 paired seeds for control and activation), with a
  ranking-eligible computational result.
- Confirmation: `\.workbench/sensory_mn9_confirmation_30seed_20260916/` —
  `PASS`, 60/60 completed jobs (30 paired seeds, seeds 100--129),
  `new_seed_set=true`, and no failed or pending jobs.
- Machine-readable audit snapshots: `\.workbench/shiu_benchmark_validation_20260916.json`
  and `\.workbench/release_gate_20260916.json`.
- Confirmation ranking: `sugar_activation`, paired seed count 30, mean delta
  approximately `83.833 Hz`, bootstrap 95% interval approximately
  `[81.765, 85.968]`, direction stability `1.0`, hypothesis alignment
  `CONSISTENT`.

These are reproducible computational outputs for the declared LIF study. They
are not biological replication, do not validate a driver line, and do not
establish that MN9 activation changes behavior in vivo. The held-out public
benchmark is frozen and locally verified (21 cases, 17 positive and 4
negative agreement labels), but has not yet been evaluated with the Workbench,
random, effect-only, and heuristic baselines; the source labels also still
require scientific sign-off.

The release gate now reports the seed gates as `PASS`. It remains intentionally
`BLOCKED` for benchmark mapping/source scientific sign-off and matched
held-out comparison against all required baselines, independent second-operator reproduction,
MN9/driver-line and prospective wet-lab review, clean worktrees, and release
tags. No Q1-readiness claim should be made until those gates are completed and
the benchmark results support the manuscript claim.

## New-protocol execution update: 2026-09-16

The two newly declared computational protocols have now been executed from
their Workbench study configurations:

- E1 intensity sensitivity:
  `results/workbench/e1_intensity_screening_20260916/` — 40/40 completed
  jobs (four conditions × ten paired seeds), 30 paired candidate observations,
  three computational candidates ranked under the declared policy.
- E2 temporal sensitivity:
  `results/workbench/e2_temporal_screening_20260916/` — 30/30 completed
  jobs (control, sustained, and pulsed conditions × ten seeds). The first pass
  exposed a Brian2 non-contiguous subgroup assignment error; the campaign was
  interrupted, the failure was retained, the runner was corrected to assign
  refractory values per index, and resume completed all jobs with zero final
  failures. This is recorded as a software failure/recovery event, not as a
  biological result.
- E2 uses explicit `TimedArray` windows. The schedule, input IDs, and hashes
  are retained in the neural run artifacts; the frequency remains a model
  parameter and is not called a biological dose.
- The public Shiu supplementary workbook was downloaded and validated against
  the frozen registry: 21/21 rows, 13 development and 8 held-out cases,
  17/4 source agreement labels, and the declared SHA-256 checksum.

These executions establish computational reproducibility of the declared
protocols only. The E1/E2 rankings are not wet-lab validation, biological
replicates, driver-line validation, or evidence that firing rate maps to
behavior. The E1/E2 30-seed confirmations and the matched held-out benchmark
comparison remain separate publication gates.

## Confirmation execution update: 2026-09-17

E1 intensity confirmation has now completed from the frozen intensity study
configuration with four candidates (control, 50 Hz, 150 Hz, and 200 Hz), 30
fresh seeds per candidate, and 120/120 completed jobs. The confirmation
manifest is
`results/workbench/e1_intensity_confirmation_20260916/campaign_manifest.json`.
The fresh seed set is 100--129 and is disjoint from the screening set 0--9;
the strict release-gate seed checks pass with zero failed or pending jobs.

Under the declared paired-delta bootstrap policy, all three intervention
conditions have 30 paired observations, direction stability 1.0, and
`CONSISTENT` alignment with the expected increase:

- `sugar_200hz`: mean delta approximately 94.70 Hz; 95% interval
  `[92.866, 96.402]`; computational ranking 1.
- `sugar_150hz`: mean delta approximately 83.83 Hz; 95% interval
  `[81.233, 86.072]`; computational ranking 2.
- `sugar_50hz`: mean delta approximately 19.77 Hz; 95% interval
  `[17.200, 22.368]`; computational ranking 3.

The ranking score is the declared effect-to-interval-width score, so rank is
not a claim that a larger firing-rate effect is biologically preferable. Seeds
remain computational repeats rather than biological replicates, and the
result is a model readout at the MN9 metric path. E2 currently has a complete
10-seed screening run but no 30-seed confirmation; no biological conclusion
is drawn from either protocol.

The release-gate snapshot is
`results/workbench/release_gate_e1_confirmation_20260917.json`. It records
the screening and confirmation seed gates as `PASS`, while the overall gate
remains `BLOCKED` for scientific benchmark sign-off and held-out comparative
evaluation, independent second-operator reproduction, MN9/driver-line and
prospective wet-lab review, clean worktrees, and release tags. This update
does not support a Q1-readiness claim by itself.

## Public-data validation implementation update: 2026-09-17

The public-data validation profile has now been implemented as a separate,
claim-safe profile. `scripts/build_shiu_benchmark_v2.py` generates a checksum-
pinned JSON registry from Shiu Supplementary Table 3, and
`scripts/validate_workbench_registry.py` verifies the source hash, row unit,
split coverage, class labels, and group leakage. The generated registry has
106 source rows, 14 response-present and 92 response-absent labels, with 74
development and 32 held-out rows. It remains marked
`COMPUTATIONAL_AUDIT_ONLY_HUMAN_REVIEW_PENDING`.

The benchmark evaluator now reports average precision and can evaluate all
systems on a common assessable denominator. A directed double-edge-swap null
model is available in `workbench.graph_nulls`; it records degree, outgoing
weight, stratum, seed, and partial-run invariants. This is a structural null,
not a claim about biological plausibility.

`configs/workbench/sensory_mn9_temporal_matched_input.yaml` declares E2-v2 with
75 Hz sustained versus two 150 Hz pulses as the matched rate-time contrast,
alongside no-input and sustained-150-Hz controls. The previous E2 artifacts are
preserved and are not relabelled as matched-input evidence.

The reproduction verifier no longer assigns `second_operator` implicitly. A
same-operator or AI clean run is computational reproduction; the independent
operator gate remains open until a separate human explicitly performs and
records the run. These additions improve auditability but do not close the
legacy release gate or establish Q1 readiness.

## Matched-input campaign update: 2026-09-17

E2-v2 completed 40/40 computational jobs (four declared conditions and ten
paired seeds per condition) with no failed or pending jobs. The runner now
reads the ranking control and expected direction from `study.metadata` rather
than hard-coding `no_intervention` and `increase`. The completed artifact was
created by the earlier runner; the corrected primary-contrast analysis is
stored separately at
`results/workbench/e2_matched_input_screening_20260917/ranking_primary_contrast_10000_bootstrap.json`.

For the predeclared pulsed-150-Hz versus sustained-75-Hz contrast, the mean
MN9 delta was approximately `-9.4 Hz`, with a case-level computational
bootstrap interval of `[-14.6, -3.5]` and direction stability `0.7`. Because
the stability threshold is `0.8`, the candidate is marked exploratory rather
than ranked. This is a model-sensitivity result only; it is not a biological
effect, dose equivalence, or firing-to-behavior claim. No E2 30-seed
confirmation or parameter-sensitivity panel has been completed yet.
