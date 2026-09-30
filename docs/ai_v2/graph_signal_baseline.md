# Development graph signal baseline — AI V2 Task 1

Status: `DEVELOPMENT_ONLY`. This small comparison tests whether connectome topology contains useful ranking signal before considering a larger graph model. All 74 development cases use the fixed five-fold manifest (`6b054c6ff0a6669cb6038b0cd365a6787f5fa5f2d0e5018094badd6cce256dab`). One GraphSAGE configuration and the decision rule were committed before comparative results were viewed. Configuration SHA-256: `55909e29f6f876407965e50f1be9b2cb61cf6e4da86624c3c9041f4c909ca137`.

## Graph and case representation

Source: FlyWire-630 directed connectivity parquet, SHA-256 `94db8c650533bc36ffa3223f2e62325d5648b8d6bd31c3a4e1c804628c7557b3`. It contains 127,400 incident node IDs and 14,687,178 directed weighted rows. Four fixed node features are `log1p` in-degree, out-degree, in-strength and out-strength. The incoming-neighbor summary is the unweighted mean of presynaptic node features. Weight values contribute to strengths, not to the GraphSAGE neighbor mean. These transformations do not fit statistics from labels.

The existing exact-match mapping registry (SHA-256 `67291ca3b68b79b2ec1d6f32c3ba7fcc938cbcffe1c25e867b39afc9e7e89165`) maps 74/74 development cases to graph IDs, representing 246 unique target neurons. Case-level structural features average the mapped target-node vectors. Ambiguous or absent mappings produce `REQUIRES_REVIEW`. The registry's `review_status` is **`PENDING_SCIENTIFIC_REVIEW` for all 74 cases**. Its IDs are inherited for computational exploration; this experiment does not establish a newly reviewed biological mapping. The frozen config phrase `mean_of_exact_reviewed_target_ids` overstates this review state. This documentation correction was made after the run; it changes neither input IDs nor calculations, and the original config/hash remain archived.

The effect reference uses `rewire_effect_only.evaluated_cases.ranking_score` from the existing development ablation (SHA-256 `7be3413b85be977a0eede4a57e6d0f682a9e1837f8431f8a04a9245311865fef`). Its value matches `simulation_effect_hz` on all 74 development cases. The complete source artifact also contains nonlabel score rows outside development; the runner selects only the 74 `evaluated_cases` rows and never uses those other scores for fitting or evaluation.

## Fixed systems and CV

| System | Inputs | Head |
| --- | --- | --- |
| B0 | Existing effect score | No training; rank directly |
| B1 | Four structural features | Train-fold standardization + logistic regression |
| B2 | Effect + four structural features | Train-fold standardization + logistic regression |
| B3 | Target and incoming-neighbor features | One-layer mean GraphSAGE + binary head |
| B4 | B3 embedding + effect | One-layer mean GraphSAGE + binary head |

GraphSAGE uses hidden dimension 8, dropout 0.1, Adam learning rate 0.01, weight decay 0.001 and 80 fixed epochs. Its positive-class weight comes from the training fold only. The same five fixed folds are used throughout. This experiment is `TRANSDUCTIVE_STRUCTURE_LABEL_ISOLATED`; see [graph_learning_setting.md](graph_learning_setting.md). The primary summaries are per-fold Average Precision, Precision@5, Recall@5 and coverage. Trained binary heads also report AUROC and AUPRC when both classes are present. No pooled cross-fold ranking is used.

## Development results

Mean ± sample standard deviation across five folds. Coverage is 1.00 for every system and fold.

| System | AP | P@5 | Recall@5 | ΔAP vs B0 | ΔP@5 vs B0 | Parameters |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| B0 | 0.549 ± 0.462 | 0.280 ± 0.415 | 0.500 ± 0.500 | 0.000 | 0.000 | 0 |
| B1 | 0.588 ± 0.418 | 0.240 ± 0.329 | 0.560 ± 0.518 | +0.039 | −0.040 | 5 |
| B2 | 0.467 ± 0.377 | 0.240 ± 0.329 | 0.560 ± 0.518 | −0.083 | −0.040 | 6 |
| B3 | 0.719 ± 0.389 | 0.200 ± 0.000 | 0.740 ± 0.371 | +0.170 | −0.080 | 81 |
| B4 | 0.670 ± 0.353 | 0.280 ± 0.179 | 0.820 ± 0.249 | +0.121 | 0.000 | 82 |

Per-fold values are AP / P@5 / Recall@5:

| Fold | B0 | B1 | B2 | B3 | B4 |
| --- | --- | --- | --- | --- | --- |
| 0 | .071 / .0 / .0 | .167 / .0 / .0 | .143 / .0 / .0 | 1.000 / .2 / 1.0 | 1.000 / .2 / 1.0 |
| 1 | .591 / .2 / .5 | .162 / .0 / .0 | .147 / .0 / .0 | .216 / .2 / .5 | .268 / .2 / .5 |
| 2 | 1.000 / 1.0 / 1.0 | .610 / .8 / .8 | .710 / .8 / .8 | .381 / .2 / .2 | .750 / .6 / .6 |
| 3 | .083 / .0 / .0 | 1.000 / .2 / 1.0 | .333 / .2 / 1.0 | 1.000 / .2 / 1.0 | .333 / .2 / 1.0 |
| 4 | 1.000 / .2 / 1.0 | 1.000 / .2 / 1.0 | 1.000 / .2 / 1.0 | 1.000 / .2 / 1.0 | 1.000 / .2 / 1.0 |

`GRAPH_SIGNAL_WEAK` under the predeclared rule. B4's mean AP exceeds B0 by 0.121 but its fold-level gain is inconsistent and mean P@5 is tied. B3's larger mean AP gain does not improve mean P@5. Some validation folds contain just one positive development case, making these fold metrics highly variable. The five-fold B0 AP is not the same estimand as the older pooled 74-case development AP; they should not be compared as if they were the same evaluation.

## Artifacts and limits

Local outputs are under `results/ai_v2_dev/graph_signal_v1/`: predeclared config copy, environment, graph hashes, fold metrics, label-free predictions, training logs, ablation CSV, summary and experiment manifest. Results are ignored by Git; rerun with `PYTHONPATH=src python scripts/run_ai_v2_graph_signal.py` in a fresh results directory after restoring the pinned public inputs. The run's source commit is `0ee05f2aa77ad29d53bfd1efe930b17b942d42ed`. `experiment_manifest.json` SHA-256 is `13ef81a8bb2b9d92b32c39539d712b8123ae3d03f7a5b785a8b5953724f650c4`; aggregate summary SHA-256 is `459567e108106d0382d7315408f3fa90acc19605f7a144510ebf33824aecbe21`.

Five-fold training time totals were about 0.15 s (B1), 0.08 s (B2), 2.02 s (B3) and 1.98 s (B4) on this machine, excluding graph preprocessing; these are not standardized speed benchmarks. Peak native memory was not reliably measured. No graph result validates a biological response, Parkinson mechanism, wet-lab utility or generalization to a second connectome. Internal held-out and external validation remain untouched.
