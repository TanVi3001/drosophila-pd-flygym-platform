# AI V2 experiment manifest — PROPOSED / DEVELOPMENT

`DevelopmentExperiment.run_fold()` writes `predictions.json` and `manifest.json` under a new immediate child of a dedicated development output root. Its manifest includes experiment ID, UTC time, source commit, clean/dirty worktree state supplied by the caller, development split hash, fold membership hash, fold number and counts, model ID/config, seed, input artifact hashes, feature families, requested metrics with interpretation, metric values and the SHA-256 of the prediction output.

The caller must supply a real source commit and worktree state when moving beyond synthetic tests. The runner rejects non-development label IDs and mismatched prediction IDs/configs. It never writes label values to the prediction artifact. Hashes support replay; they do not prove biological accuracy. Keep generated experiment outputs outside Git and outside frozen V1 artifact directories.

Metrics: Average Precision is mean precision at positive ranks; Precision@K is positive fraction in the top K; Recall@K is fraction of all positives found in the top K; Coverage is fraction of eligible cases with finite predictions. Ties are broken by case ID. `k=5` is a development default in this runner and does not change V1's locked `k=5` protocol. External metric selection is out of scope.
