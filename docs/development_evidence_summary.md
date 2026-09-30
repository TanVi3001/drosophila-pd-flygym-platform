# Frozen development evidence summary

**Scope:** development split only; artifact is the owner handoff's `owner/development_ablation.json` (74 cases). The artifact reports protocol hash `43b3704750572dade4774d514bcd986697f537b1b11de81ce918bac3310aad9f`, score lock `shiu_workbench_score_v1` v1, and `held_out_used_for_score_selection=false`. Its recorded SHA-256 is `7BE3413B85BE977A0EEDE4A57E6D0F682A9E1837F8431F8A04A9245311865FEF`.

## Development ranking metrics

| System | AP | Precision@5 | Coverage |
|---|---:|---:|---:|
| Rewire effect-only | 0.6592 | 0.80 | 1.00 |
| Rewire + uncertainty | 0.6259 | 0.80 | 1.00 |
| Full Workbench locked | 0.6259 | 0.80 | 1.00 |
| Seeded random reference | 0.2477 | 0.40 | 1.00 |

These are retrospective **development** results. The random ranking is a negative reference, not a tuned competitor. Development bootstrap intervals describe case-level ranking uncertainty and do not represent biological uncertainty. The artifact's full Workbench AP percentile interval is 0.314–0.930 and P@5 interval is 0.40–1.00 (10,000 resamples); these wide intervals discourage over-reading a 74-case result.

## What the ablation does and does not say

- **Effect-only vs uncertainty-adjusted:** uncertainty adjustment decreases AP by about 0.0333 while P@5 remains 0.80.
- **Full Workbench vs effect-only:** Claim A (“full Workbench clearly outperforms effect-only”) is **not supported**: full Workbench has lower AP (0.6259 vs 0.6592) and identical P@5 (0.80).
- **Workflow claim:** Claim B is the defensible current framing. Score construction is recorded as label-blind, explicit constraints/QC/provenance are implemented, and owner-side computational reproduction is reported separately. This supports a methods/workflow contribution, not yet an empirical claim that the gates improve experimental discovery.
- **Gate discrimination:** the development artifact records both evidence and capability gates passing for all 106 cases, with no variation. Their incremental ranking benefit is therefore **not identifiable** in this benchmark. Do not attribute the observed random-baseline gap to these gates.
- **Heuristic comparator:** it appears in older scope/protocol descriptions, but is absent from the locked four-system ablation. A different evaluator also defines heuristic as `1/(1 + shortest_path)` and has an `original_model` comparator that duplicates its effect-only score. These are not silently treated as results in the current ablation; the final comparator decision requires owner approval (see the proposed protocol).

No development value in this report is a held-out estimate, biological endpoint, behavioral prediction, or wet-lab result. Do not infer one from high coverage or a positive ranking metric.
