# Second-operator handoff (pre-heldout)

This handoff is a frozen owner reference, **not** evidence that a second operator has reproduced it. `HELDOUT_STATUS = LOCKED_NOT_RUN`. Do not inspect the 32 held-out outcomes or run their evaluator.

## Independent setup

An independent teammate (currently designated: Tô Đặng Minh Tuấn) must use their own clean platform/neural checkouts and Python 3.12.10 environments, not the owner's environments. Record `git rev-parse HEAD` and `git status --short` for both repos. The neural revision must be `e8a3cb2de2107925311053f9afcf2bfbc39fdf3c`. The platform revision must contain the separately recorded portability fix commit and the handoff runner. Run `python -m pip check` in both environments and the related reproduction/score-lock tests before scientific execution.

Copy the complete handoff directory to the independent operator's machine. Verify every line of `checksums.sha256` there. The original `owner/original_checksums.sha256` records the larger frozen source batch; the handoff manifest is the inventory of files actually supplied here. Never edit the package in place. The `reference/success_campaign.json` and `reference/failure_campaign.json` use relative artifact links. Their copies under `reference/original_campaigns/` preserve the owner's original absolute links for audit, but should not be used as portable verifier inputs.

## Development-only ablation

Run from the clean platform checkout, writing outputs outside the handoff and owner reference:

```powershell
& $PlatformPython scripts/run_shiu_workbench_ablation.py `
  --registry "$Handoff/inputs/protocol.json" `
  --mapping "$Handoff/inputs/mapping.csv" `
  --rewire-scores "$Handoff/owner/per_case_scores.csv" `
  --score-spec configs/workbench/shiu_workbench_score_v1.json `
  --output "$Replica/development_ablation.json"
```

Confirm `DEVELOPMENT_ABLATION_COMPLETE`, 74 development cases, protocol hash `43b3704750572dade4774d514bcd986697f537b1b11de81ce918bac3310aad9f`, and `held_out_used_for_score_selection=false`. Compare both output files with the frozen owner versions by SHA256; do not change the locked score or choose settings from held-out data.

## Technical success and controlled failure

Run the frozen two-case subset from the same clean platform checkout:

```powershell
& $PlatformPython scripts/run_second_operator_subset.py `
  --handoff $Handoff `
  --platform-repo $PlatformRepo `
  --neural-repo $NeuralRepo `
  --neural-python $NeuralPython `
  --expected-platform-commit $PlatformCommit `
  --output "$Replica/technical_subset"
```

This runner refuses an existing output directory and verifies the three input hashes, clean worktrees, revisions, and dependency checks before writing anything. It creates one `COMPLETED` success case and one explicit `FAILED` annotation-missing/QC case; the annotation is temporarily moved only in the new replica output and restored. The script does not assert operator independence.

## Verification and evidence freeze

Only the human who actually performed the separate run, after confirming their own independent environment, may declare `operator_role=second_operator`. The required `--operator-name` is metadata and must be the real operator's name; changing this text/name does not change the frozen scientific settings:

```powershell
& $PlatformPython scripts/verify_workbench_reproduction.py `
  --reference-manifest "$Handoff/reference/success_campaign.json" `
  --replica-manifest "$Replica/technical_subset/success_campaign.json" `
  --failure-reference-manifest "$Handoff/reference/failure_campaign.json" `
  --failure-replica-manifest "$Replica/technical_subset/failure_campaign.json" `
  --operator-name "<actual independent operator name>" `
  --operator-role second_operator --clean-install `
  --python-version 3.12.10 `
  --benchmark-protocol-hash 43b3704750572dade4774d514bcd986697f537b1b11de81ce918bac3310aad9f `
  --output "$Replica/second_operator_verification.json"
```

Freeze the replica results, environment/Git/input-hash records, verifier JSON, and final SHA256 inventory. A verifier `PASS` is computational reproduction only; the owner still must approve any later held-out run. Do not update project status to independent PASS from a self-declared role or from this handoff alone.
