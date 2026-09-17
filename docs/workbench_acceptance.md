# Fly Research Workbench v0.1 - Acceptance Record

**Recorded:** 2026-09-16  
**Scope:** local Workbench coordination layer, not biological validation

This is the v0.1 acceptance snapshot. The current Q1-facing status is tracked
in `docs/workbench_implementation_status.md`; this record is retained for
historical traceability and does not imply release readiness.

## Completed gates

- Current full platform regression: **582 passed, 2 skipped** in the verified
  Python 3.12 runtime
  across models, store, adapters, assays, ranking, confirmation, benchmark,
  CLI, service, API, and seed/override gates. The base development `.venv`
  may still skip FastAPI-specific tests when the optional extra is absent;
  the locked Python 3.12 environment has the API dependencies installed.
- The suite used the CI-style editable install without `PYTHONPATH=src`.
  The two skips are optional-environment tests; the constant-input Wilcoxon
  edge case is handled explicitly and the final suite emitted no warning.
- Full neural regression: **190 passed** in the separate Python 3.12 Brian2
  environment, including the bridge ID-scope, manifest, LIF-runner, and
  connectome-registry contracts.
- Seed and parameter-override gate: **4 passed**. Healthy and brain-driven
  runners declare explicit seed and override passthrough; the neural bridge
  remains blocked unless its external CLI declares the same contract.
- Runtime seed smoke-test: a newly executed healthy baseline retained
  `random_seed=123` and `controller.intrinsic_frequency_hz=13.0` in its output
  configuration, with all baseline checks passing.
- Clean-environment gate: `pip check` passed in both the Python 3.12 FlyGym
  and Brian2 environments; Workbench imports, FastAPI route
  registration, CLI help, and bytecode compilation passed.
- Demo acceptance: two newly executed healthy-baseline jobs completed, the
  identical-control comparison was `EXPLORATORY` with zero delta, ranking was
  ineligible as expected, and the handoff remained `DRAFT_UNREVIEWED`.
- Candidate execution smoke: a new motor case ran one control and one declared
  `controller_parameter_override` candidate through the Workbench. Both jobs
  completed with finite readouts and passed assay QC; their commands/configs
  were different and the paired path-speed comparison was `EXPLORATORY` with
  an absolute delta of approximately `3.8781571387` for seed `0`. This is a
  computational runtime check, not biological evidence.
- New LIF execution smoke: the separate Python 3.12 Brian2 environment created
  a fresh `lif-run-manifest-1`, spike parquet, and evaluated metrics from a new
  condition run. A Workbench `lif_2024` control/activation pair also completed
  through the neural assay and produced a paired computational ranking. The
  smoke used one short trial and one reviewed input ID; it is not the MN9
  biological case or the frozen public benchmark.
- Public FlyWire-630 MN9 readout pilot: the initial Workbench pair used all 21
  upstream-notebook sugar input IDs, explicit readout ID
  `720575940660219265`, one 100-ms trial, and fresh spike/metrics artifacts.
  The observed computational readout was 50 Hz versus 0 Hz in the no-input
  control, with ranking status `RANKED` under the one-seed exploratory policy.
  The run validated and hashed the 22-row FlyWire-630 annotation registry
  (`sha256=ce8058f56b33ac105c62ade6ac257ecec02247547335a10bf16ae0bcd533a25b`).
  This is a smoke result only; it is not a causal MN9 claim, driver-line
  validation, wet-lab recommendation, or public benchmark result.
- Config-driven sensory screening: the checked-in `sensory_mn9_lif.yaml`
  loaded through the CLI and executed all three declared candidate conditions
  under one seed (`3/3 COMPLETED`, no submission errors), including the
  explicit MN9 outgoing-synapse-block condition.
- Provenance/worker gate: manifests now record resolved job config, input
  hashes, environment fingerprint, code revision plus dirty-worktree digest,
  fixed result path, and SQLite/process worker claims. Stale jobs are
  recoverable only as explicit failures.
- Neural ID-scope gate: the bridge rejects annotation/spike IDs outside a
  declared inventory and preserves silent neurons using manifest trial count;
  legacy manifests without inventory receive `id_scope_not_declared`.
- Benchmark gate: the public benchmark template remains intentionally
  blocked for scientific mapping/sign-off and held-out score mapping. The
  frozen registry now contains 21 public-data cases, both labels, selection
  rules, and a development/held-out split. The evaluator preserves
  unassessable cases outside the confusion matrix and reports coverage
  explicitly; release still requires a complete matched denominator.

## Verified runtime artifacts

- The target-Python motor smoke is under `.workbench/motor_case_py312/`.
  It contains two newly executed Workbench runs, fixed-path result artifacts,
  run manifests, and the paired comparison summary.
- The target-Python LIF smoke is under `.workbench/lif_case_py312/`.
  The simulation itself was delegated to the separate Brian2 environment and
  the Workbench service process ran under the Python 3.12 FlyGym environment.
- The final annotated MN9 100-ms pilot is under
  `.workbench/sensory_mn9_case_final_py312/`.
- Earlier demo outputs may still exist under `.workbench/day10_demo_final/`;
  they are replay artifacts, not biological evidence.

All of these are computational reproducibility artifacts. None establishes
that a biological hypothesis has been confirmed.

## Explicit boundaries

- Confirmation submission creates computational jobs only. Running them does
  not establish biological confirmation.
- The base submission keeps the declared sensitivity grid out of execution;
  `--include-sensitivity` explicitly creates the case x candidate/control x
  fresh-seed jobs and records each `parameter_overrides` mapping.
- Fresh seeds are computational repeats, not biological replicates.
- Sensitivity summaries are descriptive until effect and stability thresholds
  are approved in the study protocol.
- The public benchmark is still pending scientific case selection and freeze;
  no synthetic fixture is reported as scientific evidence.
- A real lab handoff still requires reviewer approval, source inspection, and
  an explicitly proposed wet-lab validation assay.
- The verified release target is Python 3.12. The motor smoke and Workbench
  service process were run under the clean Python 3.12 FlyGym environment;
  the LIF subprocess used the separate Python 3.12 Brian2 environment, as
  required by the two-repository package isolation contract.
- This clean-runtime evidence covers the current smoke cases and targeted
  regression suite. It does not yet cover a frozen public benchmark, a second
  independent operator/machine, or wet-lab validation.

## Re-run commands

```powershell
$env:PYTHONPATH = "src"
& .venvs\flygym-runtime-312\Scripts\python.exe -m pytest -q tests/test_workbench* --basetemp=.pytest-tmp-workbench-regression
& .venvs\flygym-runtime-312\Scripts\python.exe scripts/run_workbench_motor_case.py --output-root .workbench/motor_case_py312 --seed 0
& .venvs\flygym-runtime-312\Scripts\python.exe scripts/run_workbench_lif_case.py --neural-python ..\.venvs\baseline-2024-312\Scripts\python.exe --input-id 720575940624963786 --seeds 0 --trials 1 --duration 0.01 --output-root .workbench/lif_case_py312
& .venvs\flygym-runtime-312\Scripts\python.exe scripts/workbench.py --help
```
