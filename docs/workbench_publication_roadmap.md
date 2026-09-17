# Fly Research Workbench: research-grade roadmap

This document turns the v0.1 implementation into a 3–6 month methods and
biology study. It is a work plan, not a claim that the current repository is
ready for a Q1 submission.

## Paper position

The primary contribution should be a reproducible research-workbench method:

1. explicit study/candidate/backend contracts;
2. paired computational screening with QC and scope-aware uncertainty;
3. auditable provenance and human review;
4. a public retrospective benchmark and a concrete MN9 sensory-circuit case.

The benchmark and MN9 case are evidence for usefulness, not proof that the
software makes universally correct biological decisions. A conference ranking
is not a journal quartile; the target venue and its current author/reviewer
criteria must be checked again at submission time.

## Release gates

### Gate A — software correctness

- Python 3.12 clean environment, locked dependency export, and CI with the
  optional Workbench API dependencies.
- Candidate intervention materialization tests for every built-in backend.
- The separate `lif_2024` adapter must be tested with a new spike-producing
  run; `neural_bridge` remains a consumer of already generated artifacts.
- Trial-count, string-ID, NaN/Inf, orientation, scale-zero, result-path, and
  stale-worker regression tests.
- Web and CLI produce the same `RunManifest`, ranking report, and evidence
  bundle for the same database and configuration.

### Gate B — two supported computational studies

- Motor study: healthy control versus an explicitly configured controller
  parameter perturbation, with path speed, path length, displacement, turning,
  bilateral symmetry, and orientation QC.
- Sensory study: use the `lif_2024` adapter only with public reference/model
  files, manifests, explicit FlyWire-630 IDs, a declared ID inventory, and a
  prespecified readout. The current 1-s MN9 screening/confirmation pilot is a software/readout
  smoke, not the completed biological case. The optional `neural_bridge`
  still consumes validated spike outputs and does not generate new LIF spikes.
  Missing or incompatible artifacts remain `BLOCKED`/`WAITING`, never
  synthetic data.
- Each study records pilot time/RAM, seed plan, configuration hash, input
  hashes, backend version, and a claim-safe interpretation.

### Gate C — frozen public benchmark

- Select at least 20 public conditions with independently traceable positive and
  negative reference labels.
- Freeze inclusion/exclusion, label mapping, source checksums, and the
  development/evaluation split before threshold selection.
- Compare at least random, effect-only, simple heuristic, and Workbench
  ranking baselines.
- Report confusion matrix, precision, recall, precision@k, false negatives,
  class balance, model-assessable coverage, and confidence intervals where the
  unit of resampling is justified.
- Require a matched assessable denominator across Workbench and all baselines
  for the release comparison; a partial or section-incompatible result remains
  a scope audit, not the main performance claim.
- Keep unassessable cases visible and separate; never convert them to negative
  labels.

### Gate D — independent reproducibility

- A second operator follows the clean-install quickstart on a fresh machine or
  isolated environment.
- Re-run a frozen subset without editing thresholds or source labels.
- Compare manifests, hashes, outputs within declared tolerances, and all
  failure states.
- Publish code, environment lock, public input manifest, protocol, raw summary
  tables, and analysis scripts; do not publish private or oversized artifacts.

### Gate E — biological interpretation

- Use the MN9 case to ask one bounded question: whether the computational
  circuit-level readout prioritizes the prespecified activation/blocking
  contrast under the selected stimulus and public evidence.
- State which predicted readout is directly measured, which mapping is a proxy,
  and which mechanisms are absent.
- Do not convert firing rate to behavior probability without a validated
  quantitative relationship.
- Treat a contradiction or null as a reason for follow-up design, not automatic
  rejection of the biological mechanism.

## 12-week execution order

| Weeks | Deliverable | Exit evidence |
|---|---|---|
| 1–2 | v0.1 correctness and worker/provenance gates | CI, regression suite, clean install |
| 3–4 | motor study end-to-end and metrics contract | new outputs, QC report, pilot budget |
| 5–6 | neural public-data intake and ID-scope-compliant MN9 run | source manifest, bridge report or explicit blocked report |
| 7–8 | frozen benchmark and baseline implementations | protocol hash, split lock, benchmark tables |
| 9–10 | sensitivity/ablation and independent reproduction | unchanged eval set, failure audit |
| 11 | biological interpretation and lab handoff review | evidence bundle, reviewer log, limitations |
| 12 | release and manuscript package | reproducibility archive, figures/tables, claim audit |

## Claims that remain prohibited until the gates pass

- universal disease or neuron-level validity;
- a single “virtual fly equals X% real fly” score;
- safe elimination of every negative computational candidate;
- wet-lab cost savings without a prospective lab study;
- benchmark generalization beyond the frozen public-data scope.

The minimum publishable result is a transparent, reproducible method with a
bounded biological case and independently inspectable failures. Stronger
claims require new data and a new review decision.
