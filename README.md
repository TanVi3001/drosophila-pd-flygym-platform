# drosophila-pd-flygym

## Fly Research Workbench v0.1

The shared study/job coordination layer is documented in
[`docs/workbench_v0_1.md`](docs/workbench_v0_1.md). It provides auditable
`StudySpec`, backend adapters, SQLite job state, per-run manifests, a local
CLI, and an optional FastAPI surface. A completed subprocess is a
computational result, not biological validation.

[![Release](https://img.shields.io/github/v/release/TanVi3001/drosophila-pd-flygym?display_name=tag&sort=semver)](https://github.com/TanVi3001/drosophila-pd-flygym/releases)
![Python](https://img.shields.io/badge/python-3.12-blue)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Tests](https://img.shields.io/badge/tests-pytest-blue)

Research software scaffold for an in-silico Drosophila melanogaster
locomotion simulation using FlyGym, NeuroMechFly, and MuJoCo.

The project goal is to build a reproducible simulation workflow that can compare
an unperturbed locomotion baseline against future controlled perturbations after
the locomotion infrastructure is stable. This repository is the source of truth
for code, configuration, tests, and documentation. Google Colab is used as an
execution environment, not as the canonical project state.

This is a computational model. Simulation outputs must not be presented as
direct evidence from real Drosophila, and this repository does not currently
claim biological validation of any Parkinson's disease model.

## Current Checkpoint

Milestone F is the latest frozen submission-packaging checkpoint. Milestone E6
is FROZEN - REPRODUCIBLE EVIDENCE SYNTHESIS as an evidence-only analysis layer.
The canonical
repository implementation now reproduces the
pre-materialization anatomy audit, executes the authorized joint materialization
gate once, validates the post-materialization anatomy state, runs an
unperturbed deterministic FlyGym locomotion baseline, characterizes combined
motor-vigor and coordination proxy perturbations, validates the frozen E2
candidate's multi-seed robustness, records qualitative concordance against
selected adult Drosophila walking literature, and freezes the preregistered
Milestone E5 computational reversibility evidence.

Milestone C is an unperturbed simulation baseline. It is not biological
validation, not a Parkinson's disease model, and not evidence from real
Drosophila.

Milestones E2, E3, and E4 are also not biological validation and do not select a
validated Parkinson's-disease-like condition. E4 does not tune the frozen
candidate or calibrate simulation values to biological measurements.
E5 does not tune the frozen candidate, does not run a rescue parameter sweep,
and does not claim pharmacological, dopaminergic, mechanistic, biological, or
Parkinson's disease rescue.

Historical Session 02 Blocks 8.14-8.19 are superseded by canonical Milestone 8B
code and JSON evidence. The notebooks remain historical research records.

The verified Block 8.12 pre-materialization anatomy audit found:

- Python target: 3.12
- FlyGym target: 2.1.0
- MuJoCo target: 3.9.0
- Body segments: 69
- Anatomical joints: 68
- JointDOFs: 204
- Axis order: PITCH_ROLL_YAW
- Six leg groups: 24 JointDOFs each
- Non-leg JointDOFs: 60
- MJCF body mapping: 69/69
- JointDOF to MJCF joint mapping: 0, expected before materialization
- JointDOF to neutral angle mapping: 0, expected before materialization
- Actuator mappings: 0, expected before materialization
- `fly.skeleton is None`
- `add_joints()` has not been called

The verified Milestone 8B materialization checkpoint found:

- pre-state `fly.skeleton is None`
- pre-state MJCF joints: 0
- materialization gate used
- post-state skeleton is materialized
- post-state MJCF joints: 204
- JointDOF to MJCF joint mapping: 204
- JointDOF to neutral-angle mapping: 204
- actuator mappings: 0
- second materialization attempt rejected

The verified Milestone C unperturbed baseline found:

- Python 3.12.13, FlyGym 2.1.0, and MuJoCo 3.9.0
- duration: 0.5 s
- timestep: 0.0001 s
- steps: 5000
- position actuators: 42
- adhesion actuators: 6
- compiled MuJoCo `nu`: 48
- planar displacement: 6.284186050286936 mm
- mean planar speed: 12.568372100573873 mm/s
- yaw change: 0.2342730946151257 rad
- finite observations and derived metrics

## Project A - Healthy Baseline Study Preparation

Project A adds a planning-only contract and asset package for the first 100
Healthy baseline experiments (`Healthy_001` through `Healthy_100`, seeds 0-99).
The canonical materials are under `research/campaigns/healthy_baseline/` and
`docs/v10/`. They define the future dataset manifest, metadata, checksums,
metrics catalog, Figures 1-8, Tables 1-6, publication skeleton, and reviewer
gates.

No Healthy rollout, result, figure, table, or scientific conclusion is created
by Project A. When an approved real dataset is supplied under
`datasets/healthy/`, the existing V7-V9 gates and downstream pipeline remain
the execution path. A ready/integrity result is not biological validation.

## Project B - Parkinson Study Preparation

Project B is a planning-only package for 100 future computational-condition
experiments (`PD_001` through `PD_100`, seeds 0-99). Its protocol, dataset
contract, expected outputs, validation gates, reviewer checklists, and paper
skeleton are under `research/campaigns/parkinson_study/`,
`paper/parkinson_study/`, and `docs/v10/Project_B/`.

No PD rollout, simulation, synthetic data, new algorithm, or biological claim
is created. The `pd` dataset label is a computational planning category only.
Until an approved dataset and computational configuration exist, the existing
CLI/runtime correctly stops at `WAITING_DATASET`.

## Project X - Real Dataset Acquisition Pipeline

Project X adds the additive `drosophila_pd.dataset_registry` package for
receiving caller-supplied FlyGym datasets. It supports manifest-backed scanning,
directory/ZIP/single/multiple-rollout import, checksum and duplicate checks,
metadata and payload health reports, searchable indexing, and explicit CSV/JSON/
Markdown/SHA-256 artifact reports.

The registry does not run FlyGym or MuJoCo, create rollout data, alter
scientific algorithms, or make biological claims. Missing or invalid data
remains `WAITING_DATASET` or `FAILED`.

## Project Y - Large-scale Experiment Campaign Manager

Project Y adds `drosophila_pd.campaign` for campaign planning, declarative
execution matrices, explicit state transitions, deterministic queueing,
progress and artifact tracking, provenance, dashboard reports, and publication
planning. Templates for Healthy, PD, Candidate, Control, Validation,
Benchmark, Longitudinal, Perturbation, Recovery, and generic parameter
screening are in `configs/campaign_templates/`.

The manager is orchestration-only. It does not execute FlyGym, create rollouts,
generate data, add Parkinson algorithms, or make biological claims.

## Repository Layout

- `src/drosophila_pd/anatomy/` - anatomy and FlyGym mapping audit helpers
- `src/drosophila_pd/controllers/` - controller interfaces
- `src/drosophila_pd/perturbations/` - controlled perturbation interfaces
- `src/drosophila_pd/experiments/` - experiment orchestration code
- `src/drosophila_pd/experiment/` - explicit real-run orchestration, artifact, dataset, and benchmark management
- `src/drosophila_pd/metrics/` - gait and locomotion metrics
- `src/drosophila_pd/analysis/` - evidence-only synthesis of frozen reports
- `configs/experiments/` - version-controlled experiment configuration
- `configs/analysis/` - evidence-synthesis configuration
- `notebooks/session_*/` - session-based Colab research notebooks
- `scripts/` - command-line utilities
- `tests/` - automated checks
- `results/` - local/generated experiment outputs, kept lightweight by default
- `logs/` - local run logs

## Research Repository Migration (V3 Preparation)

The repository is also organized as an open research repository without
changing the frozen scientific chain. Use the [documentation hub](docs/README.md),
[architecture snapshot](docs/repository_architecture.md),
[public API reference](docs/public_api.md), and
[reproducibility records](reproducibility/README.md) for orientation.
Research-area anchors under `research/` and reusable documents under
`templates/` are organizational only; they do not create rollout data or new
scientific evidence. The migration roadmap is
[docs/vi/100_V3_Roadmap.md](docs/vi/100_V3_Roadmap.md).

## V4 Real Scientific Campaign Preparation

V4 adds protocol-driven preparation only: dataset specifications, experiment
protocols, analysis and publication playbooks, SOPs, QA checklists, and
readiness audits. It does not create datasets, run simulations, add framework
modules, or introduce new scientific conclusions. Start at the
[V4 preparation hub](docs/v4/README.md).

## V5 Experimental Campaign 01

V5 prepares the first real Healthy baseline campaign without running it. The
100-experiment matrix, manifest/metadata/checksum templates, execution plan,
figure/table plans, publication asset layout, notebook template, and reviewer
checklist are under
`research/campaigns/healthy_baseline/`. No rollout, figure, table, or new
scientific conclusion is included. See the [V5 planning hub](docs/v5/README.md).

## Interactive Digital Fly Laboratory

The Web Viewer can visualize imported FlyGym rollouts as an interactive Digital
Fly. It provides Canvas-based perspective/orthographic camera presets, orbit
and pan controls, body-part selection, mesh/skeleton/COM/trajectory overlays,
timeline playback, synchronized rollout comparison, and PNG/SVG view export.
These are presentation tools over imported computational data; they do not run
simulations or add biological interpretation. The Vietnamese guides are in
`docs/vi/51_3D_Viewer.md` through `docs/vi/56_Huong_Dan_3D.md`.

### End-to-end viewer bundle

In the documented Python 3.12 environment, one command runs the real FlyGym
rollout pipeline and creates a deployable static bundle under `dist/`:

```bash
python scripts/run_demo.py
```

The command creates or reuses `datasets/healthy/Healthy_001/`, exports
`rollout.json`, `rollout.npz`, `viewer_pose.json`, `manifest.json`, and builds
`dist/viewer_bundle.zip`. It never fabricates rollout data. If the simulator
stack is unavailable, it stops with an actionable environment error. To serve
the newest discovered pose locally after a successful run:

```bash
python scripts/run_viewer.py
```

The static ZIP can be uploaded to GitHub Pages or any static web host.

## Parkinson Research Workbench

The V2 Web Platform also provides a research workbench for imported rollouts.
It combines named workspace layouts, multi-experiment comparison controls,
validation summaries, figure composition, research notes, and a project bundle
manifest. It is a management and presentation layer over existing computational
artifacts: it does not run simulations, create evidence, or make biological
diagnoses. See the Vietnamese guides in `docs/vi/57_Workbench.md` through
`docs/vi/62_Project_Bundle.md`.

## Milestone 3 Automation

The repository includes an additive, metadata-only automation layer for
dataset catalogs, persistent experiment queues, reproducibility manifests,
software benchmarks, artifact/publication packaging, project health, and
developer inspection. It reuses the existing V2 campaign and experiment APIs;
there is no default simulation executor and no fabricated rollout data.

```bash
python scripts/research_automation_cli.py health-check
python scripts/research_automation_cli.py generate-manifest --output automation_manifest.json
python scripts/research_automation_cli.py create-bundle --output bundle/
```

The Vietnamese guides are in `docs/vi/63_Dataset_Catalog.md` through
`docs/vi/72_Kien_Truc_Milestone3.md`.

## Milestone 4 Digital Twin Platform

The V2 platform includes a management layer for multiple Digital Twin records
derived from imported rollouts. It provides snapshot/restore/branch history,
state diffs, temporal exploration, scenario workflow records, annotations,
knowledge-graph links, virtual-laboratory sessions, and collaboration history.
These are computational workflow tools only: they do not run simulations,
create rollout data, add scientific metrics, or make biological claims.

```bash
python scripts/digital_twin_platform_cli.py validate --input platform.json
```

The Vietnamese guides are in `docs/vi/73_Digital_Twin.md` through
`docs/vi/82_Milestone4.md`.

## Epic 20 Research Campaign Engine

The additive campaign layer manages experiment plans, dependency-aware states,
history, provenance, validation summaries, dashboards, reports, and publication
bundles over existing computational artifacts. It does not run FlyGym/MuJoCo,
create rollout data, modify the Digital Twin, or introduce scientific metrics.

```bash
python scripts/research_campaign_cli.py --help
```

The Vietnamese guides are in `docs/vi/83_Research_Campaign.md` through
`docs/vi/90_Kien_Truc_Campaign.md`.

## Research Phase I Unified Study Pipeline

`StudyOrchestrator` composes the existing dataset catalog, research campaign,
Digital Twin, analysis, statistics, computational-PD, scientific-validation,
publication, and provenance APIs. It creates `study.json` and
`research_package.zip` from supplied artifacts without running simulations or
introducing scientific results.

```bash
python scripts/run_study.py --study-id example --name "Example Study" \
  --dataset input=/path/to/existing_dataset.json
```

The Vietnamese guides are in `docs/vi/91_Pipeline_Nghien_Cuu.md` through
`docs/vi/95_Kiem_Dinh_Pipeline.md`.

## Workflow

1. Develop code, tests, and documentation locally with Codex.
2. Commit and push reviewed source changes to GitHub.
3. Pull the repository into Google Colab for FlyGym/MuJoCo execution.
4. Save reproducibility metadata, metrics, logs, and selected small artifacts.
5. Keep large raw artifacts outside Git unless explicitly curated.

## Installation

The repository uses a standard `src`-layout Python package and does not require
`PYTHONPATH` to be set:

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# Linux/macOS: source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
python -m drosophila_pd
pytest -q -rs -p no:cacheprovider
```

Install the optional simulation environment only when FlyGym execution is
authorized and available:

```bash
python -m pip install -e ".[simulation]"
```

## V2 experiment management

The Sprint 1 `drosophila_pd.experiment` package manages real caller-provided
experiment stages, manifests, checksums, logs, retries, and publication asset
registration. It has no default simulation handler: a FlyGym pipeline must be
injected explicitly, so the package cannot fabricate rollout data. Dataset
layout creation is metadata-only until existing files are registered.

## GitHub Discussions

GitHub Discussions are recommended for research planning, assay design,
literature-mapping questions, reproducibility notes, and non-urgent roadmap
coordination. Use issues for actionable bugs or scoped implementation requests,
and pull requests for reviewed repository changes.

Community and maintenance files:

- `CONTRIBUTING.md` - contribution workflow and scientific-boundary guidance
- `CODE_OF_CONDUCT.md` - participation expectations
- `SECURITY.md` - vulnerability reporting guidance
- `SUPPORT.md` - support and discussion guidance
- `docs/citation.md` - citation guidance for the repository, Release v1.0.0,
  and final report

## Reproducing Block 8.12

Block 8.12 can be reproduced with the non-mutating audit CLI:

```bash
python scripts/audit_block_8_12.py --output results/baseline/block_8_12_audit.json
```

The audit checks anatomy and mapping invariants only. It must leave
`fly.skeleton is None` and does not validate a Parkinson's disease model,
locomotor biology, or evidence from real flies.

Fresh Google Colab reproduction has passed using Python 3.12.13,
FlyGym 2.1.0, and MuJoCo 3.9.0. The generated
`results/baseline/block_8_12_audit.json` report returned
`overall_pass = true` with `fly.skeleton` remaining `None` before and after the
audit.

## Reproducing Milestone 8B

Milestone 8B can be reproduced with the joint materialization milestone CLI:

```bash
python scripts/run_joint_materialization_milestone.py --output results/baseline/milestone_8b_materialization.json
```

Fresh Google Colab reproduction has passed using Python 3.12.13,
FlyGym 2.1.0, and MuJoCo 3.9.0. The generated
`results/baseline/milestone_8b_materialization.json` report returned
`overall_pass = true`.

This milestone validates FlyGym/NeuroMechFly joint materialization and
post-materialization anatomy mappings only. It does not create actuators, run
locomotion, implement controllers, or validate a Parkinson's disease model.

## Reproducing Milestone C

Milestone C can be reproduced with the unperturbed baseline CLI:

```bash
python scripts/run_healthy_baseline.py \
  --config configs/experiments/healthy_baseline.yaml \
  --output results/baseline/healthy_baseline.json
```

Fresh Google Colab reproduction has passed using Python 3.12.13,
FlyGym 2.1.0, and MuJoCo 3.9.0. The generated
`results/baseline/healthy_baseline.json` report returned
`overall_pass = true`.

This milestone validates an unperturbed simulation baseline for future software
comparisons only. It does not establish biological realism or disease relevance.

## Running Milestone D

Milestone D runs paired controlled perturbation experiments:

```bash
python scripts/run_perturbation_experiment.py \
  --baseline-config configs/experiments/healthy_baseline.yaml \
  --perturbation-config configs/experiments/perturbations/identity.yaml \
  --output results/perturbations/identity.json
```

```bash
python scripts/run_perturbation_experiment.py \
  --baseline-config configs/experiments/healthy_baseline.yaml \
  --perturbation-config configs/experiments/perturbations/action_scale_080.yaml \
  --output results/perturbations/action_scale_080.json
```

These are controlled simulation perturbation experiments. They are not
Parkinson's disease models and are not biological validation.

Fresh Google Colab reproduction has passed for both Milestone D validation
runs using Python 3.12.13, FlyGym 2.1.0, and MuJoCo 3.9.0. The generated
evidence files are:

- `results/perturbations/identity.json`
- `results/perturbations/action_scale_080.json`

Both reports were generated from git commit
`f886c204d8ad3a95dcd953418a8f9df51927137f`.

The identity run returned `overall_pass = true` and
`identity_equivalence_pass = true`, with zero recorded comparison deltas. The
`action_scale_080` run returned `overall_pass = true`, scaled the 42
joint-angle controller commands by 0.8, preserved adhesion commands, and kept
all controlled variables matched between conditions.

For `action_scale_080`, the observed simulation response relative to the paired
baseline included planar displacement delta -0.6714494674507625 mm, mean planar
speed delta -1.342898934901525 mm/s, yaw-change delta
0.03061053070618347 rad, body-height mean delta 0.5321613121790706 mm, and no
adhesion duty-factor or transition-count deltas. These are simulation results,
not biological interpretation.

## Running Milestone E0/E1

Milestone E0/E1 runs generic parameter-response sweeps before selecting any
disease-like computational phenotype:

```bash
python scripts/run_parameter_sweep.py \
  --baseline-config configs/experiments/healthy_baseline.yaml \
  --sweep-config configs/experiments/sweeps/milestone_e1.yaml \
  --output results/sweeps/milestone_e1.json
```

The configured families are `motor_vigor_proxy` and `coordination_proxy`.
These are phenomenological computational proxies, not direct simulations of
dopamine concentration, dopaminergic neuron loss, or biological validation.

Fresh Google Colab reproduction has passed using Python 3.12.13,
FlyGym 2.1.0, and MuJoCo 3.9.0. The generated evidence file is
`results/sweeps/milestone_e1.json`, produced from git commit
`7cb2ed580b8eabb6a363b27f481564751eeb9e48`.

The report returned `overall_pass = true`: all 10 conditions completed, all
completed conditions passed, and both baseline-equivalent conditions passed.

Key simulation response-surface findings:

- Motor-vigor scaling produced a graded reduction in displacement and speed.
- Joint-action magnitude followed the commanded scaling exactly.
- Body-height response was nonlinear.
- CPG coupling reduction had modest effects at intermediate values.
- Near-zero CPG coupling produced large locomotion loss and large yaw deviation.

No E1 parameter value is currently designated as Parkinson's disease, dopamine
depletion, neuron-loss percentage, disease stage, or biological severity.

## Running Milestone E2

Milestone E2 is FROZEN — COMBINED PHENOTYPE CHARACTERIZATION.

It characterizes a compact explicit set of combined motor-vigor and
coordination proxy conditions:

```bash
python scripts/run_combined_phenotype_sweep.py \
  --baseline-config configs/experiments/healthy_baseline.yaml \
  --sweep-config configs/experiments/sweeps/milestone_e2.yaml \
  --output results/sweeps/milestone_e2_combined.json
```

Fresh Google Colab reproduction has passed using Python 3.12.13,
FlyGym 2.1.0, and MuJoCo 3.9.0. The generated evidence file is
`results/sweeps/milestone_e2_combined.json`, produced from git commit
`433269ed11e0475eb973b62d31f469d66843872f`.

The report returned `overall_pass = true`: all 9 conditions completed, all
completed conditions passed, the control-equivalent condition passed, controlled
variables were preserved, and fresh simulation state per condition was declared.

This run composes CPG coupling-weight scaling with joint-angle action scaling,
records both transformations separately, and reports baseline deltas plus
interaction residuals. It is a phenomenological simulation characterization
only; it does not choose or validate a Parkinson's-disease-like condition.

Key E2 observations:

- Speed and displacement interaction effects were mostly close to additive.
- Directional/yaw effects were more nonlinear across combined conditions.
- Motor scale 0.8 with coupling scale 0.75 is a leading computational candidate
  for further validation, not a final or validated disease model.

## Running Milestone E3

Milestone E3 is FROZEN - MULTI-SEED ROBUSTNESS VALIDATION. It runs paired
baseline-vs-candidate simulations for seeds 0 through 4 at 1.0 s duration:

```bash
python scripts/run_candidate_robustness.py \
  --baseline-config configs/experiments/healthy_baseline.yaml \
  --validation-config configs/experiments/validation/milestone_e3.yaml \
  --output results/validation/milestone_e3_candidate_robustness.json
```

The frozen candidate remains `motor_scale = 0.8` and
`coupling_scale = 0.75`, selected before E3 execution from Milestone E2. E3
does not tune those parameters, implement rescue experiments, or validate a
Parkinson's disease model.

Fresh Google Colab reproduction has passed using Python 3.12.13,
FlyGym 2.1.0, and MuJoCo 3.9.0. The generated evidence file is
`results/validation/milestone_e3_candidate_robustness.json`, produced from git
commit `730ab3acd8e5535b93f320a62c19080feca0448f`.

The report returned `overall_pass = true` and robustness classification
`ROBUST`: all 5 paired seeds completed, controlled variables were preserved,
candidate transformations were validated, required observations and metrics were
finite, and displacement/speed deltas were negative for all 5 seeds.

Key E3 aggregate observations:

- Displacement and speed means changed from 13.751281674590993 to
  12.302040063313584, about -10.54%.
- Planar path length mean changed from 19.31485503067457 to
  17.308442670909542, about -10.39%.
- Trajectory efficiency mean changed from 0.7119806020699851 to
  0.7107636180753024, about -0.16%, with mixed seed-wise deltas.
- Joint action absolute mean changed from 1.0256368082597096 to
  0.820559121832831, about -20.00%.
- Body height mean increased from 0.9465522152698778 mm to
  1.4910686043526398 mm and remains an important confound.
- Absolute yaw-change mean increased from 0.10385794490113649 rad to
  0.21120580249246884 rad; the yaw absolute-change delta was positive in 4 / 5
  seeds.

`ROBUST` means computational/software robustness under these tested seeds only.
It does not mean biological robustness, statistical significance, disease
validation, disease severity, dopamine depletion, or mechanistic validation.

## Running Milestone E4

Milestone E4 is LITERATURE-GROUNDED PHENOTYPE CONCORDANCE. It reads the curated
evidence matrix and frozen E3 evidence without running another FlyGym
simulation:

```bash
python scripts/run_phenotype_concordance.py \
  --output results/validation/milestone_e4_concordance.json
```

The evidence matrix is `docs/scientific/e4_evidence_matrix.yaml`. The generated
report classifies adult walking speed/velocity and covered-distance directions
as `CONCORDANT`, while preserving unsupported endpoints such as angular
velocity, distance per movement, centrophobism, climbing, pause/freezing, and
body-height interpretation as `NOT_COMPARABLE`, `NOT_AVAILABLE`, or
`INSUFFICIENT_EVIDENCE`.

The proposed E4 status is `PARTIAL_PHENOTYPE_CONCORDANCE`: reduced locomotor
output in the frozen E3 candidate is directionally consistent with selected
adult walking literature, but this is not biological validation, not a weighted
PD score, not dopamine depletion, and not mechanistic equivalence.

## Running Milestone E5

Milestone E5 is FROZEN - PREREGISTERED COMPUTATIONAL REVERSIBILITY. It runs a
fixed, preregistered computational reversibility experiment over the frozen
E3/E4 candidate:

```bash
python scripts/run_computational_rescue.py \
  --baseline-config configs/experiments/healthy_baseline.yaml \
  --validation-config configs/experiments/validation/milestone_e5.yaml \
  --output results/validation/milestone_e5_computational_rescue.json
```

The fixed conditions are `control` (`1.0 / 1.0`), `impaired_candidate`
(`0.8 / 0.75`), `motor_partial_rescue` (`0.9 / 0.75`),
`coordination_partial_rescue` (`0.8 / 0.875`),
`combined_partial_rescue` (`0.9 / 0.875`), and
`full_computational_restoration_reference` (`1.0 / 1.0`). The midpoint values
come from `(0.8 + 1.0) / 2 = 0.9` and `(0.75 + 1.0) / 2 = 0.875`.

Primary endpoints are `mean_planar_speed_mm_s` and `planar_path_length_mm`.
E5 reports computational recovery fractions using
`(rescue - impaired) / (control - impaired)` and handles near-zero denominators
explicitly. These are simulation quantities only, not biological recovery
percentages.

The frozen Colab evidence is
`results/validation/milestone_e5_computational_rescue.json`. It reports Python
3.12.13, FlyGym 2.1.0, MuJoCo 3.9.0, git commit
`7cffac001488589d089bc49266aa103e7458f476`, 30 / 30 completed condition runs,
and `overall_pass = true`.

Observed primary endpoint classifications:

- `motor_partial_rescue`: `DIRECTIONALLY_RESCUED`
- `coordination_partial_rescue`: `MIXED`
- `combined_partial_rescue`: `DIRECTIONALLY_RESCUED`
- `full_computational_restoration_reference`: reference only

Motor-axis restoration accounts for most of the primary locomotor recovery
observed in E5. Adding partial coordination restoration produced modest and
endpoint-dependent additional effects: combined partial restoration was slightly
higher than motor-only for mean speed but slightly lower for path length.
Combined partial restoration is therefore not universally superior.

The `full_computational_restoration_reference` condition is a software/control
equivalence check. It is not full rescue, cure, L-DOPA response, dopamine
restoration, or Parkinson's disease rescue.

## Milestone E6

Milestone E6 is FROZEN - REPRODUCIBLE EVIDENCE SYNTHESIS. It consumes exactly
the eight frozen C/D/E1/E2/E3/E4/E5 reports, does not run FlyGym or MuJoCo, and
does not modify any upstream evidence JSON:

```bash
python scripts/run_evidence_synthesis.py \
  --config configs/analysis/milestone_e6.yaml \
  --output results/analysis/milestone_e6_synthesis.json
```

The implementation is frozen at commit
`53e41d17365f56509ca708ba3352ddf724b0e89a`. The report validates upstream pass
states, provenance, and the frozen
`motor_scale = 0.8` / `coupling_scale = 0.75` candidate, then writes one JSON
report with 56 passing checks, four deterministic figures, and five CSV tables
under `results/analysis/`. E4 remains
`PARTIAL_PHENOTYPE_CONCORDANCE`; E5 remains computational reversibility only.
E6 PASS means only that the computational evidence was internally consistent and
the analysis artifacts were generated. It is not biological validation,
Parkinson's disease validation, mechanistic equivalence, or statistical
significance.

The report's `synthesis_worktree_dirty = true` records only the known
pre-existing dirty Session 02 notebook; that notebook was not modified or
staged.

## Milestone F Final Submission Package

Milestone F is FROZEN - FINAL SUBMISSION PACKAGE. The canonical manuscript is
`docs/report/final_report.md` at source commit
`004488cf7fd5e980137a209d360b977716865e1a`. Build the publication artifacts
with:

```bash
python scripts/build_final_report.py
```

The version-controlled final artifacts are:

- `dist/Drosophila_PD_FlyGym_Final_Report.docx`
- `dist/Drosophila_PD_FlyGym_Final_Report.pdf`
- `dist/final_report_manifest.json`

The manifest records artifact hashes, sizes, page count, build provenance, and
validation results. This package changes document formatting only; it does not
rerun simulations or expand the scientific scope. The report remains a
computational/phenomenological model with qualitative
`PARTIAL_PHENOTYPE_CONCORDANCE`, not Parkinson's disease validation, biological
rescue, dopamine equivalence, disease-severity mapping, mechanistic equivalence,
or a statistical-significance claim.

## Planned Research Stages

1. Unperturbed baseline
2. Controller interface
3. Controlled perturbations
4. Parameter-response characterization
5. Multi-seed robustness validation
6. Literature-grounded phenotype concordance
7. Preregistered computational reversibility
8. Gait metrics
9. PD-like perturbation
10. Healthy vs PD-like comparison
11. Potential biological-rescue interpretation, only after external evidence
   and explicit authorization

## V6 Execution Runtime

V6 adds a dataset-gated execution layer for the prepared campaign. It reads
manifest metadata, provenance, and declared payload paths without parsing
rollouts. With no executable dataset present, the runtime returns
`WAITING_DATASET` and does not invoke the research pipeline or create scientific
data.

```bash
python scripts/run_campaign.py discover
python scripts/run_campaign.py execute
```

When an approved real dataset is placed under `datasets/` with an executable
manifest, the runtime delegates to the existing `StudyOrchestrator`. See
[`docs/v6/120_V6_Architecture.md`](docs/v6/120_V6_Architecture.md).

## V7 FlyGym Dataset Integration

V7 adds a read-only adapter for curated FlyGym datasets. It discovers
`healthy`, `pd`, `candidate`, `control`, `validation`, and `benchmark` manifests,
checks metadata, paths, checksums, trajectory files, and frame counts, and
writes dataset reports without running simulation.

```bash
python scripts/dataset_cli.py discover
python scripts/dataset_cli.py validate
python scripts/dataset_cli.py report
```

No real rollout dataset is currently present, so the adapter reports
`WAITING_DATASET`. See [`docs/v7/126_V7_Architecture.md`](docs/v7/126_V7_Architecture.md).

## V8 Scientific Experiment Runtime

V8 adds session-based orchestration over the V7 dataset adapter. It persists
session state, execution events, runtime manifests, artifacts, and summaries.
When a dataset is absent, execution stops at `WAITING_DATASET`; when the V7
adapter returns `READY`, the runtime delegates to the existing
`StudyOrchestrator`.

```bash
python scripts/experiment_runtime.py prepare
python scripts/experiment_runtime.py bind
python scripts/experiment_runtime.py run
python scripts/experiment_runtime.py summary
```

See [`docs/v8/132_V8_Architecture.md`](docs/v8/132_V8_Architecture.md).

## V9 Scientific Operating System

V9 adds an orchestration-only Research Kernel over the existing V7 dataset
adapter and V8 experiment runtime. It provides a research event bus, service
registry, resource tracking, dependency scheduler, and kernel CLI without
adding simulation or scientific computation.

```bash
python scripts/kernel.py boot
python scripts/kernel.py status
python scripts/kernel.py resources
python scripts/kernel.py events
python scripts/kernel.py shutdown
```

With no approved rollout dataset present, the kernel stops at
`WAITING_DATASET`. See [`docs/v9/138_V9_Architecture.md`](docs/v9/138_V9_Architecture.md).

## Project Z Healthy Dataset Execution

Project Z completes the execution path for manifest-backed real Healthy
rollouts under `datasets/healthy/`. It uses the existing execution runtime and
study pipeline per declared rollout, writing `analysis/`, `statistics/`,
`validation/`, `reports/`, `figures/`, and `publication/` beneath the
operational output directory. It does not run simulation or create rollout
data.

```bash
python scripts/run_campaign.py discover
python scripts/run_campaign.py execute --limit 1
python scripts/run_campaign.py execute --limit 10
python scripts/run_campaign.py execute
```

Completed rollout outputs are resumed from their persisted status; failed
rollouts are retried by default. Use `--no-resume` or `--no-retry-failed` for
explicit control. Missing datasets return `WAITING_DATASET`; malformed or
unsupported manifests return `INVALID_DATASET`. Scientific validation is
reported as unavailable when no reference rollout is declared, rather than
being inferred or fabricated.

## Publication-Ready Research Platform

The repository is organized as a computational research platform with the
following workflow:

```text
FlyGym/MuJoCo
  -> recorder and rollout export
  -> viewer pose and static bundle
  -> imported-rollout analysis
  -> biomarker summaries and reports
```

The platform supports simulation, measurement, visualization, analysis,
provenance, and artifact packaging. It does not diagnose Parkinson's disease,
replace biological research or experimental fly data, or establish clinical
biomarker validity. Dataset labels such as `pd` remain computational labels
unless external biological evidence is supplied.

For a publication audit, start with:

- [Scientific validation](docs/scientific_validation.md)
- [Reproducibility guide](docs/reproducibility.md)
- [Publication checklist](docs/publication_checklist.md)
- [Figure manifest](docs/figure_manifest.md)
- [Table manifest](docs/table_manifest.md)
- [Research readiness report](docs/research_readiness.md)
- [Final repository audit](docs/final_repository_audit.md)

The canonical citation metadata is in [CITATION.cff](CITATION.cff), and the
license is [MIT](LICENSE). No DOI is declared by this repository. Reproduce a
software-only installation with:

```bash
python -m pip install -e ".[test]"
python scripts/check_runtime.py
python -m compileall -q src scripts tests
pytest -q -rs -p no:cacheprovider
```
