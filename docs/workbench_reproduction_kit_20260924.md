# Workbench reproduction kit for the second operator

This document is the handoff checklist for Tuấn. It reproduces the frozen
computational artifact; it does not authorize changing the score formula or
using the 32 held-out labels for tuning.

## Frozen identity

| Item | Value |
| --- | --- |
| Root branch | `feature/workbench-state4-review` |
| Root commit | `9c5d99f` |
| FlyGym commit | `77b4df5` |
| Protocol hash | `43b3704750572dade4774d514bcd986697f537b1b11de81ce918bac3310aad9f` |
| Protocol split | 74 development / 32 held-out |
| Frozen batch | 106 cases, status `COMPLETE` |
| Frozen rewire artifact | `external/Drosophila_brain_model/results/workbench_benchmark_20260923/frozen_rewire_run02` |
| Frozen checksum manifest | `checksums.sha256` in the freeze artifact |

The freeze manifest records the source hashes for the protocol, mapping,
degree-preserving-rewire connectivity, and prior benchmark report. Tuấn should
compare those hashes before running anything.

## Clean environment

Use Python 3.12 in a fresh environment. Do not run PowerShell commands in
`cmd.exe`; the commands below are PowerShell commands.

```powershell
$Repo = "E:\research-\drosophila-pd-flygym"
$Python = "E:\research-\.venvs\baseline-2024-312\Scripts\python.exe"
Set-Location $Repo
& $Python -m pytest -q tests/test_workbench_score_lock.py tests/test_freeze_shiu_v2_rewired_lif_batch.py tests/test_workbench_reproduction.py -p no:cacheprovider
```

The expected targeted test result is all tests passing. The test command is a
software-contract check, not an independent simulation claim.

## Reproduce the locked development ablation

```powershell
$Ablation = "E:\research-\external\Drosophila_brain_model\results\workbench_benchmark_20260923\development_ablation_v1\tuans_development_ablation.json"
& $Python scripts/run_shiu_workbench_ablation.py `
  --rewire-scores "E:\research-\external\Drosophila_brain_model\results\workbench_benchmark_20260923\frozen_rewire_run02\per_case_scores.csv" `
  --output $Ablation
```

Expected properties are 74 development cases, protocol hash
`43b3704750572dade4774d514bcd986697f537b1b11de81ce918bac3310aad9f`, and no
held-out calibration. Numerical equality should be checked from the JSON rather
than copied from this document.

## Final held-out step after review

Do not run the final held-out claim until the score lock and the independent
operator reproduction have been accepted. Before that point, run only the
readiness audit:

```powershell
$Preflight = "E:\research-\external\Drosophila_brain_model\results\workbench_benchmark_20260923\heldout_preflight_v1.json"
& $Python scripts/audit_shiu_heldout_preflight.py `
  --rewire-scores "E:\research-\external\Drosophila_brain_model\results\workbench_benchmark_20260923\frozen_rewire_run02\per_case_scores.csv" `
  --benchmark-report "E:\research-\external\Drosophila_brain_model\results\workbench_benchmark_20260923\comparative_benchmark.json" `
  --output $Preflight
```

The expected status is `READY_FOR_FINAL_HELDOUT_EVALUATION`. That status means
inputs are complete; it is not a held-out performance result.

## Independent-operator record

Tuấn should preserve a replica output directory and record:

1. operator name and role `second_operator`;
2. Python version and clean-install declaration;
3. platform and neural repository commit IDs;
4. protocol hash and source hashes;
5. batch summary, freeze manifest, and checksum result;
6. any failed or silent cases without converting them into negatives.

The reproduction verifier should be run with
`--operator-role second_operator` only after the replica manifest exists. A
successful software reproduction is required for the independent claim, but it
still does not establish biological or wet-lab validity.
