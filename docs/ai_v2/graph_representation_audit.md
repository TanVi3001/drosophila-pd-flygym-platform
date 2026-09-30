# Task 1 graph representation audit — post-result, label-blind

The [machine-readable diagnostic](../../data/ai_v2_dev/graph_representation_diagnostic_v1.json) was computed from the 74-case sanitized mapping and public FlyWire connectivity, without development labels or model training. Its SHA-256 is `dc9d435cfb7736eba88a29dcbf9c417cb0a8c94e84e61fcd496e6e2d033322e`. Task 1's `GRAPH_SIGNAL_WEAK` conclusion remains historical evidence; this audit was motivated by that result.

## Current representation and observed properties

Task 1 uses four `log1p` node features: in/out degree and in/out connection strength. Incoming presynaptic features are averaged without edge weights. A case averages its mapped target-node vectors. The GraphSAGE input therefore has eight scalar values per target (four self plus four incoming-neighbor mean); the simple structural case vector has four. There are 74 cases, 246 unique mapped targets, and 1–15 targets per case (median 2). Sixty-eight cases have more than one target.

Across the 74 case-level means, the variances of the four self features are 0.467, 0.955, 0.853 and 2.040 in the order above. The corresponding incoming-neighbor-mean variances are 0.154, 0.067, 0.265 and 0.156. No case feature has near-zero variance under the predeclared `1e-8` threshold. No pair of combined eight-dimensional case inputs is identical or within maximum absolute distance `1e-3`. This shows compression, not a demonstrated loss of predictive information.

Mapped target degrees span approximately 11–1,196 incoming and 1–1,185 outgoing, with medians 146 and 133. Incoming strengths span approximately 35–7,106 (median 611); outgoing strengths span 1–7,411 (median 476.5). These figures are approximate because `log1p` float32 features were inverted for reporting. No mapped target has zero in-degree, zero out-degree or total degree ≤1; all 246 have incoming edges.

Three target neurons are shared across two cases (2/74 cases, 2.7%). In the original CV, two validation cases had a shared target in a training case, one in fold 0 and one in fold 2. This is a possible dependence between case units, not evidence of label leakage. In the post-Task-1 stratified folds, the shared-target pair falls in one fold, so the corresponding cross-fold count is zero. The new folds were assigned by deterministic stratification, not by manual target placement.

## Information-loss questions, not tested replacements

**Node → case mean.** Fifteen of the 68 multi-target cases have a range greater than one log unit in at least one node feature. Mean pooling can conceal such heterogeneity, target-set size, extremes and distribution shape. The current mapping does not give a verified left/right tag for each target; a side-aware feature would require a separate scientific mapping review rather than inference from ID order.

**Unweighted incoming-neighbor mean.** Synaptic counts are used in strength features but do not weight neighbor messages. For the 246 mapped targets, the largest incoming edge contributes a median 7.4% of total incoming edge weight; the 95th percentile is 30.2% and the maximum is 41.0%. No target has a single edge above 50%. An unweighted mean can still discard edge-weight distribution and relative input strength. A weighted mean is a candidate, not a demonstrated improvement.

The [representation candidate config](../../configs/ai_v2/graph_representation_candidates_v2.json) lists only R0–R4. R0 is the current four-feature view; R1 adds target-set size/spread/extremes; R2 uses weight-normalized incoming neighbor aggregation; R3 proposes a bounded two-hop structural summary; R4 proposes mean-plus-standard-deviation pooling of GraphSAGE target embeddings. These are design choices grounded in topology and aggregation semantics, not label separation or observed positive/negative cases. **None is implemented or evaluated in Task 1B.**

For target embedding width `d`, mean pooling yields `d` values; mean+max and mean+standard deviation yield `2d` (16 for Task 1's `d=8`). Attention/set pooling could return `d` or a configured width but would require a later separately registered trainable model and stronger overfitting controls. For four raw structural features, the corresponding widths are 4 or 8. Target-set count adds one separate scalar in R1.

**Weighted message-passing design note.** A future R2 would use directed presynaptic → postsynaptic edges and nonnegative connectivity count `w`, normalizing each target's incoming message weights as `w/(sum_incoming_w + ε)`. It needs a specified zero-incoming fallback, a pinned `ε`, train-only normalization for any learned statistics, and a direct comparison with the unweighted summary. Large synapse count is structural evidence; it does not guarantee stronger causal or biological efficacy. Numerical stability and unit semantics must be reviewed before implementation.

## Interpretation

Task 1 graph models displayed possible development ranking signal but inconsistent fold gains. B3 and B4 differed; simply adding the effect feature to a graph embedding was not reliably beneficial. B4's higher Recall@5 with unchanged mean Precision@5 is consistent with broader capture across folds without stronger top-five concentration, but the uneven fold prevalence limits that interpretation. The evidence is insufficient to justify a larger graph model. `GRAPH_SIGNAL_WEAK` is preserved.
