# Task 1C robustness experiment — preregistered, NOT EXECUTED

`TASK_1C_PREREGISTERED = TRUE`

`TASK_1C_EXECUTED = FALSE`

This specification was written **after** Task 1 results and the Task 1B audit. Its purpose is to ask whether the Task 1 graph-signal direction persists when the ten positive development cases are distributed evenly across five folds. It does not erase or replace Task 1. The only intended change is the validation-fold membership: use [`development_cv_stratified_5fold_v2.json`](../../configs/ai_v2/development_cv_stratified_5fold_v2.json), seed `20260930`, membership SHA-256 `bddbe5a7a51a0610c4d6b82aaf27ac7e6fd10cf892eb0c824ec2dcd3f95fccfd`.

Keep B0–B4 definitions, GraphSAGE candidate, hyperparameters, epoch count, effect and structural inputs, topology, input hashes, train-only preprocessing and higher-is-better score direction from Task 1 configuration SHA-256 `55909e29f6f876407965e50f1be9b2cb61cf6e4da86624c3c9041f4c909ca137`. Read [sanitized development effect inputs](../../data/ai_v2_dev/development_effect_features_v1.json) and [sanitized development mappings](../../data/ai_v2_dev/development_mapping_v1.json); labels come only from a development-only evaluator input under the access firewall. The historical Task 1 runner remains unchanged. Before any Task 1C execution, adapt a new runner to these inputs and verify score parity on the 74 DEV cases without opening mixed benchmark rows.

For each fold and system, report AP, Precision@5, Recall@5 and coverage; trained binary heads may additionally report AUROC/AUPRC when defined. Compare B4–B0 and B3–B0 by fold and mean; report sample standard deviation and median. Do not pool independently fitted fold scores into one global ranking. Include parameter count, runtime, full artifact hashes and target-sharing counts. No held-out or external validation is authorized.

Decision rule, fixed before Task 1C execution:

- `GRAPH_SIGNAL_ROBUST` if B4 mean ΔAP versus B0 ≥0.05, B4 mean ΔP@5 ≥0.04 (one net extra top-five hit across five folds), B4 mean AP > B2 mean AP, B4 AP > B0 in at least four folds, and the mean B4–B0 AP delta remains positive after omitting any single fold.
- Otherwise `GRAPH_SIGNAL_STILL_WEAK` if at least one graph-containing system has a positive mean ΔAP or ΔP@5 versus B0.
- Otherwise `GRAPH_SIGNAL_UNSUPPORTED`.

This rule is exclusive and exhaustive. It does not guarantee a positive result and does not confer independent biological validation. Task 1C has **not** trained or evaluated any model as part of Task 1B.
