# Fly Research Workbench v0.1

This repository now contains the first shared coordination slice for the two-week plan.

## Run the CLI

From `drosophila-pd-flygym`:

```powershell
$env:PYTHONPATH = "src"
python scripts/workbench.py --db .workbench/workbench.sqlite3 --artifacts .workbench/artifacts capabilities
python scripts/workbench.py create-study --file configs/workbench/motor_flat_ground.yaml
```

To enable the neural bridge, pass both repositories explicitly (and keep the
interpreters separate):

```powershell
python scripts/workbench.py --neural-repo ..\drosophila-pd-neural-disease --neural-python ..\drosophila-pd-neural-disease\.venv\Scripts\python.exe capabilities
```

The CLI and the optional FastAPI server both call `WorkbenchService`; they do not maintain separate execution pipelines.

```powershell
pip install -e ".[workbench]"
python scripts/workbench_server.py --db .workbench/workbench.sqlite3 --artifacts .workbench/artifacts
```

Open `http://127.0.0.1:8000/` for the minimal local study page. It lists
capabilities, creates a `StudySpec`, and loads study/job/report state. The
existing Three.js viewer remains an artifact viewer; the workbench page does
not invent rollout data or silently run a simulation.

For the Day 10 local acceptance flow, run the real healthy baseline twice as
an identical control replay:

```powershell
python scripts/run_workbench_demo.py --output-root .workbench/day10_demo
```

The demo must produce two `COMPLETED` jobs, an `EXPLORATORY` comparison with
zero delta, `ranking_eligible: false`, and a `DRAFT_UNREVIEWED` handoff ZIP.
The replay is a software/reproducibility smoke test, not a comparison of two
biological mechanisms.

## Lab handoff and evidence review

After a job has produced a manifest, inspect the human-readable bundle:

```powershell
python scripts/workbench.py handoff STUDY_ID
python scripts/workbench.py compare STUDY_ID --reference-job JOB_A --condition-job JOB_B
python scripts/workbench.py review STUDY_ID --decision approved --reviewer "PI name" --comments "Reviewed limits and sources."
python scripts/workbench.py export-bundle STUDY_ID --output .workbench/handoff.zip
```

The default state is `DRAFT_UNREVIEWED`. Approval changes only the bundle
review state; it does not change run artifacts, QC, or ranking. The bundle
contains one dossier per candidate with the falsifiable prediction, target and
intervention fields, controls/confounds, metric, uncertainty, model limits,
source entries, run-manifest references, proposed validation, and reviewer
decision. Missing driver-line or connectome metadata remains
`not_provided`/`null` rather than being inferred.

When a `ranking_report.json` exists, the bundle also contains
`reports/ranking_report.json`, `ranking_review`, and each dossier's candidate
ranking record. The ranking review state is separate from the general bundle
state: a computational ranking is not silently treated as expert-approved
evidence.

## v0.1 contracts

- `StudySpec` stores the hypothesis, falsifiable prediction, assay, primary metric, candidates, controls, sources, and run plan.
- `BackendAdapter` exposes `describe`, `validate`, and `run`. The built-in adapters call scripts through an explicit interpreter and repository root.
- A concrete backend resolves the selected `candidate_id` back to the `StudySpec` before validation. Its intervention type must be declared in the backend capability matrix; the resolved intervention, candidate hash, and any declared parameters are persisted in the job config. A candidate ID alone is never treated as an intervention.
- `AssayAdapter` exposes `evaluate` and `compare`. The locomotion adapter only validates readout/QC presence; it does not rank biological hypotheses.
- `RunManifest` records the command, interpreter, repository, configuration hash, status, exit code, artifact checksums, backend capabilities, resolved job configuration, input file hashes, code revision plus dirty-worktree digest, and a compact execution-environment fingerprint. Each built-in command declares its result path; the service does not select an arbitrary JSON file when a run has multiple artifacts.
- SQLite stores studies, jobs, and audit events. Each attempt receives a new run directory.
- Job claiming is conditional on `status = PENDING` in SQLite and the worker uses an artifact-root lock across processes. A stale lock can be reclaimed only when its recorded process is gone; stale `RUNNING` jobs are reported as failed by `recover-stale` and require an explicit resume.
- `DecisionReport` separates computational result, QC/readout status, uncertainty, limitations, and recommendations. Ranking is disabled until a study-specific comparison layer supplies the required QC, paired seeds, CI, and effect threshold.
- `RankingPolicy` and `RankingObservation` provide the Day 11 study-specific ranking layer. They pair each candidate value with its control on the same computational seed, calculate a deterministic bootstrap CI, and keep QC failures, duplicate seeds, missing thresholds, and assay/metric/study mismatches outside `ranked_candidates`.
- `POST /v1/studies/{study_id}/compare` runs the registered assay comparison for two completed jobs and labels the result `EXPLORATORY`.
- `POST /v1/rankings` and `workbench rank` apply the same ranking evaluator. A candidate is eligible only when the predeclared effect threshold, minimum pair count, direction stability, and non-zero CI separation are satisfied.
- `POST /v1/studies/{study_id}/rank` and `workbench rank-study` collect observations from completed job artifacts, pair them to the declared control by explicit seed plus normalized phase, sensitivity case, backend, and shared configuration scope, and write `ranking_report.json` with source-manifest hashes. Missing declared candidates are reported as coverage gaps; they are not silently omitted.
- Ranking output separates observed effect direction/stability from hypothesis alignment. A stable effect in the opposite direction is labelled `CONTRADICTORY`, not `below threshold` and not a weak negative result.
- Evidence bundles include the persisted ranking report and a separate review gate. An approved ranking review is bound to the exact ranking content hash; changing the report invalidates the approval and forces re-review. Rejected, stale, or incomplete rankings remain visible but cannot be marked as handoff priority.
- `POST /v1/studies/{study_id}/confirmation-plan` and `workbench confirmation-plan` create a reviewed top-k confirmation plan with fresh non-overlapping seeds and a declared sensitivity grid. They produce templates only; they do not submit or run backend jobs.
- `POST /v1/studies/{study_id}/confirmation-plan/submit` and `workbench submit-confirmation` submit those templates only after the backend declares explicit seed passthrough; submission is idempotent and writes `confirmation_submission.json`.
- Base confirmation submission does not silently expand a sensitivity grid. Use
  `workbench submit-confirmation STUDY_ID --include-sensitivity` or send
  `{"include_sensitivity": true}` to the API to create one explicit job per
  declared sensitivity case, candidate/control, and fresh seed. Each such job
  stores `parameter_overrides` and the case index in its config and provenance.
- `POST /v1/studies/{study_id}/confirmation-plan/run` and `workbench run-confirmation` run only the submitted confirmation job IDs, one at a time, and write `confirmation_run.json`; failed/cancelled jobs are not silently resumed.
- `POST /v1/studies/{study_id}/screening/submit` and `workbench screen-study` expand an explicit candidate × seed matrix into persisted screening jobs. `screening/run` executes only that submission and keeps every candidate/seed status visible.
- `POST /v1/benchmarks/retrospective` and `POST /v1/benchmarks/sensitivity` expose the same frozen benchmark/sensitivity evaluators used by the CLI.
- `workbench benchmark` evaluates a frozen retrospective case list with confusion matrix, precision, recall, precision@k, false negatives, and model-assessable coverage. It does not run simulations.
- `workbench sensitivity` summarizes supplied reruns descriptively; it does not infer a stability threshold.

The `neural_bridge` backend is intentionally not enabled by default unless the neural repository and its separate interpreter are supplied to `default_adapters`. Its command consumes validated spike outputs; it does not claim to create new LIF spikes. The same explicit neural environment also exposes `lif_2024`: it calls `scripts/run_lif_condition.py`, imports the pinned upstream model by file path, creates new spike output, writes `lif-run-manifest-1`, and runs the metrics evaluator. The adapter requires reviewed IDs and public model files; it never infers a sensory or MN9 mapping.

`configs/workbench/sensory_mn9_lif.yaml` now contains a separate, explicit
FlyWire-630 public-ID case: the 21 sugar-sensing input IDs and the MN9 readout
ID are copied from the upstream public notebook and recorded in
`drosophila-pd-neural-disease/annotations/flywire630_sensory_mn9_public.csv`. The
existing FlyWire-783 annotation file is not reused for this case. The runner
reports `metrics.readout_rates_hz.<neuron_id>` and keeps a silent readout as a
numeric zero only when that ID belongs to the declared completeness inventory.
This makes the case computationally runnable, but does not make the notebook
label a driver-line specificity validation.

For a short computational adapter smoke with the pinned public FlyWire-630
files, use the separate neural interpreter explicitly:

```powershell
$env:PYTHONPATH = "src"
python scripts/run_workbench_lif_case.py `
  --neural-python ..\drosophila-pd-neural-disease\.venv\Scripts\python.exe `
  --annotation-file ..\drosophila-pd-neural-disease\annotations\flywire630_sensory_mn9_public.csv `
  --input-id 720575940624963786 `
  --seeds 0 1 2 `
  --output-root .workbench\lif_case
```

To exercise an explicit readout, repeat `--input-id` for the reviewed 630
sugar set and add:

```powershell
--readout-id 720575940660219265
```

The current verified 100-ms pilot used all 21 public input IDs, one seed, one
trial, and reported a 50-Hz MN9 readout against a 0-Hz no-input control. This
is a computational smoke result with one short trial, not biological evidence
or a Q1-level benchmark.

The resulting ranking is a computational smoke artifact. The public registry
supports the declared MN9 label within the FlyWire-630 notebook scope, but the
run does not establish causal MN9 biology, optogenetic driver specificity, or
that a wet-lab experiment should be run.

## Scope boundary

A process exit code of zero means that the configured computational command completed. It is not evidence of biological validation, equivalent conditions, or a safe elimination of a wet-lab direction. Failed QC and missing readouts remain visible and are not pushed to the bottom of a candidate ranking.

## Day 11 ranking gate

Example policy and observations can be supplied as JSON or YAML:

```powershell
python scripts/workbench.py rank --observations observations.json --policy configs/workbench/ranking_policy.example.yaml --output ranking_report.json
python scripts/workbench.py rank-study STUDY_ID --policy configs/workbench/ranking_policy.example.yaml
```

`configs/workbench/ranking_policy.example.yaml` is a template, not a frozen
scientific decision: replace `STUDY_ID` and approve the effect threshold in the
study protocol before using it.

The policy must identify one assay and primary metric. Supplying `study_id` is
recommended; if observations contain multiple study IDs, an explicit policy
scope is required for those observations to be eligible. The effect threshold
is intentionally mandatory for ranking: without it the candidate is reported
as `EXPLORATORY_NO_THRESHOLD`, not as a negative result. Seeds are computational
repeats only. The bootstrap interval describes seed-to-seed computational
variation and does not quantify missing mechanisms or biological variation.

`rank-study` requires `control_candidate_id` in the policy. It reads only
completed jobs, uses an explicit `seed`/`random_seed` from the job config or
backend result, rejects disagreement between the two, and records jobs that
cannot be paired under `collection.unpaired_jobs`. It never uses job order or
attempt number as a substitute seed.

## Day 14 confirmation gate

After a ranking is approved, create the next-run plan:

```powershell
python scripts/workbench.py confirmation-plan STUDY_ID --top-k 3 --output confirmation_plan.json
```

The planner defaults to `confirmation_seed_repetitions` from the study (30 if
not declared), generates numeric seeds after the largest screening seed, and
rejects string seeds unless `--seeds` supplies an explicit, non-overlapping
list. A study must declare `run_plan.sensitivity`; otherwise the plan remains
`BLOCKED` with `sensitivity_grid_missing`. The output contains candidate and
control job templates, ranking provenance, and no claim that confirmation has
occurred.

Submit only after inspecting the plan:

```powershell
python scripts/workbench.py submit-confirmation STUDY_ID
```

The command above submits only the base candidate/control confirmation jobs.
To opt into the declared parameter sensitivity cases, use:

```powershell
python scripts/workbench.py submit-confirmation STUDY_ID --include-sensitivity
```

This is an explicit computational expansion, not a biological replicate
claim. The backend must declare both seed and parameter-override passthrough
before these jobs are accepted.

`CapabilityDescriptor.supports_explicit_seed` is enabled for the local healthy
and brain-driven runners after their `--seed` wiring. It remains disabled for
the neural bridge until its external CLI declares and verifies equivalent
passthrough. Submission still creates computational jobs only; it is not
biological confirmation.

After inspecting the submission record, run only that confirmation set:

```powershell
python scripts/workbench.py run-confirmation STUDY_ID
```

The run report lists every job status and error. A successful process run is
still a computational result; ranking must be recomputed from the resulting
artifacts and reviewed again before any lab handoff.

If a process is interrupted, inspect and recover only abandoned jobs:

```powershell
python scripts/workbench.py recover-stale --stale-after 3600
```

The command never resumes a job automatically.

## Day 9 benchmark gate

`configs/workbench/retrospective_benchmark.template.yaml` is intentionally
not runnable: the case list must be selected from public data, include at
least 20 mapped conditions with both positive and negative labels, and be
frozen before evaluation. Use:

```powershell
python scripts/workbench.py benchmark --protocol protocol.yaml --predictions predictions.yaml --output benchmark_report.json
python scripts/workbench.py sensitivity --runs sensitivity_runs.yaml --output sensitivity_report.json
```

The report must retain unassessable cases separately. They are excluded from
the confusion matrix and coverage is reported explicitly; they are never
converted to negative cases to improve a metric.

## Clean installation check

The supported local install is:

```powershell
python -m venv .venv-workbench
.\.venv-workbench\Scripts\python.exe -m pip install -r requirements\workbench-py312.lock
.\.venv-workbench\Scripts\python.exe -m pip install -e . --no-deps
.\.venv-workbench\Scripts\python.exe -m pip check
```

FlyGym/MuJoCo remain optional simulation dependencies; the FastAPI server is
provided by the `[workbench]` extra. No AI provider is required for study
creation, execution, reporting, benchmarking, or handoff export.

Install the separate neural runtime from
`drosophila-pd-neural-disease/requirements/lif-runtime-py312.lock`, then install that
repository with `pip install -e . --no-deps`. Keep the two editable installs in
separate environments; the Workbench invokes the neural runner by subprocess.
