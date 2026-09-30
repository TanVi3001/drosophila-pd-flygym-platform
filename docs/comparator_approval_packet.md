# Final comparator approval packet — Task 2A

**Historical purpose:** provide the owner with a reviewable recommendation. This packet's recommendation was advisory; the subsequent owner decision is separately recorded below and in the incident-aware final protocol.

**Historical context:** this packet was prepared before the integrity incident and is retained for its development-only comparator rationale. Its original protocol-pending statements below describe the audit-time state, not the current approval status. The incident-aware approval record is at the end of this file.

## Source identity and audit basis

- Branch: `feature/workbench-state4-review`
- Source commit at audit start: `4de0971750cf3e448055e81b675f2dcb4fc2130c`
- Protocol at Task 2A audit time: `shiu_v2_final_evaluation_v1`, then `PROPOSED_OWNER_APPROVAL_REQUIRED`; `owner_approval.status=PENDING`.
- Score lock: `shiu_workbench_score_v1` v1; SHA-256 `e522aba1bb58a0883a589255c09debbfc2cf0ad1841358242b3dd248e93aa452`.
- Benchmark registry SHA-256: `8743feba5149f78d96238e9ee3bfacbc1d7dd8a33960b6a5eaf6bda77d8fdedb`; semantic identity `43b3704750572dade4774d514bcd986697f537b1b11de81ce918bac3310aad9f`; split-membership SHA-256 `45bb9c206ff3d35d75fcf6b1f888d270ab7bd1b105e03d1e5aa04ea4c42ee2e4` (membership only, not labels/outcomes).
- Frozen development artifact: `E:\research-\external\Drosophila_brain_model\results\workbench_benchmark_20260923\second_operator_handoff_20260928_v5\owner\development_ablation.json`; SHA-256 `7BE3413B85BE977A0EEDE4A57E6D0F682A9E1837F8431F8A04A9245311865FEF`. Status `DEVELOPMENT_ABLATION_COMPLETE`, 74 development cases, protocol semantic hash matches, and `held_out_used_for_score_selection=false`.
- Metric values below were read only from this development artifact. No held-out outcomes were used.

## Proposed primary comparator set

| ID | Exact definition / role | Development metrics (AP / P@5 / coverage) | Information and leakage audit | Fairness and recommendation |
|---|---|---:|---|---|
| `rewire_effect_only` | Frozen per-case `degree_preserving_rewire` `score_hz`; no uncertainty normalization and no evidence/capability multiplier. Strong effect-only baseline / ablation. | 0.6591959 / 0.80 / 1.00 | Uses the frozen rewire score map. `build_locked_scores` reads score, mapping fields and published uncertainty; it does not use reference labels, observed response fraction or `shortest_path`. | Full development coverage. Same case universe and higher-is-better ranking as other primary systems. It is the strongest meaningful frozen baseline by development AP; keep primary so full Workbench is tested against a substantive comparator, not only random. `INCLUDE_PRIMARY`. |
| `rewire_plus_uncertainty` | `rewire_effect_only / max(mean published left/right MN9 SD at 50 Hz, 1e-12)`; omits both gates. Isolates uncertainty normalization relative to effect-only. | 0.6258625 / 0.80 / 1.00 | Uncertainty comes from public `model_mn9_sd_hz` in the frozen registry, not held-out-derived calibration. Score construction is label-blind. | Same 74-case development denominator and full coverage. The effect-to-uncertainty division changes ranking (not merely units); no tuning found in the lock. `INCLUDE_PRIMARY`. |
| `full_workbench_locked` | Exact score-lock v1: `rewire_effect_only / max(published_uncertainty_mean_hz, 1e-12) × evidence_gate × capability_gate`. | 0.6258625 / 0.80 / 1.00 | Evidence gate derives only from mapping/reviewer approval fields; capability gate from `assay_comparable`, nonempty input IDs, and the exact two configured MN9 readout IDs. Score builder marks construction label-blind. Reviewer-process blinding itself is not established by code. | Same development denominator and coverage. Both gates pass all 106 registered cases, so the development benchmark has no gate variation; this system is numerically the uncertainty-only ablation here. Include as the locked target, but do not claim incremental gate benefit from this dataset. `INCLUDE_PRIMARY`. |
| `random_reference` | `random.Random(17092026)` generates one deterministic random score per declared ordered case-ID list using the frozen runner; higher score ranks first. Negative reference, not a scientific model. | 0.2477406 / 0.40 / 1.00 | Uses the seed and case IDs only; no model features or outcome labels. Reproducibility is for the frozen case ordering and implementation. | Same 74 development cases and full coverage. Useful as a floor/sanity reference, not as the principal comparator and not a basis for a superiority claim by itself. `INCLUDE_PRIMARY`. |

The development artifact reports full Workbench does **not** beat effect-only: AP is lower (0.6259 vs 0.6592) and P@5 is tied (0.80). Uncertainty adjustment lowers AP by about 0.0333 while P@5 stays the same. Preserve this negative/non-superiority result.

## Legacy comparator disposition

| ID | Exact implementation found | Issues | Disposition |
|---|---|---|---|
| `heuristic` | In `scripts/run_public_benchmark_evaluation.py`, `1 / (1 + shortest_path)`; scores are omitted when `shortest_path` is nonfinite/missing. | `shortest_path` is explicitly in `forbidden_score_inputs` in both the score lock and final protocol. Code appears label-blind, but its use conflicts with the frozen allowed-input contract. It was absent from the four-system development ablation; adding it now would be post hoc and may give a different denominator. It is not needed to isolate effect, uncertainty, gates, or random-reference behavior. | **EXCLUDE** from this final evaluation. Reconsider only under a separately authorized, predeclared protocol and explicit scientific rationale; do not treat the legacy score as a current result. |
| `original_model` | In the same legacy evaluator, `effect=(left+right)/2` from published 50-Hz `model_mn9_rates_hz`; both `original_model[case_id]` and legacy `effect_only[case_id]` are assigned this exact value. | It is mathematically identical to the *legacy evaluator's* `effect_only`, so those two must not appear as separate baselines. It is **not** identical to current `rewire_effect_only`, which comes from frozen degree-preserving-rewire scores; it is operationally a distinct raw published-rate score. It was not part of the frozen four-system development ablation and would add a different comparator after analysis. | **EXCLUDE** from this final evaluation. The raw-rate version could be evaluated in a future separately specified study, but it is not needed for the current locked ablation question and must not be silently substituted for rewire effect-only. |

## Fairness and metric compatibility

- **Split and case universe:** all four primary systems in the frozen development artifact are assessed on the same 74 development cases; coverage is 1.00 each. The score builder requires mapping and rewire-score IDs to equal the full registry ID universe. The future held-out common denominator and per-system coverage must be reported under the existing protocol; this audit did not calculate or inspect them.
- **Label blindness:** score construction for the four systems does not consume reference labels, observed response fraction or shortest path. Development threshold calibration in the runner is fit on development labels for binary classifications; it is in-sample for development. However, AP and P@5 are computed from the original ranking score, so this calibration does not tune the ranking. Do not use calibrated classification metrics as primary ranking evidence.
- **Comparator-specific inputs:** rewire effect is the frozen computed score; uncertainty is the published 50-Hz MN9 SD; gates use the mapping/review and declared assay/readout fields; random uses only seed and ordered IDs. These features were available from the declared public benchmark/run contract at ranking time. Human reviewers' exposure to labels is not proven by the scoring code and should not be described as blinded unless independently documented.
- **Ties:** actual ranking sorts descending ranking score, then ascending string case identifier. This is deterministic and predeclared. Zero/equal scores remain ranked; if gate failures produce tied zeroes, lexical tie order can affect P@5. Report that rule and keep zero scores as valid numeric scores.
- **Missing/unassessable:** nonfinite or absent score predictions are unassessable, excluded from ordering and not converted to negative. Report each system's coverage and the common-assessable denominator, as the protocol requires. Legacy heuristic's coverage can be lower because missing paths are skipped. Do not infer future held-out coverage from development coverage.
- **Score scale:** AP and P@5 are ranking metrics and do not compare absolute score units. A monotonic scaling alone does not improve them; per-case uncertainty normalization can change ordering. Ties remain relevant, hence the fixed tie rule.
- **Leaked reference labels:** no score-generation path for the four primary systems reads them. Reference labels are used only by the evaluation metric after scores are fixed. This is a code-path audit, not proof that any human mapping reviewer was blinded.
- **Forbidden inputs:** legacy `heuristic` explicitly uses forbidden `shortest_path`; that is a decisive reason to exclude it from this locked evaluation. No score-lock or protocol input list is changed here.

## Scientific question answered

> On the same predeclared benchmark cases, how does the frozen rewire-based Workbench ranking compare with (i) its raw effect-only component, (ii) the same effect normalized by frozen published uncertainty, and (iii) a deterministic random negative reference, using Precision@5 as the primary ranking metric and AP, coverage, and unassessable count as secondary reports?

This design distinguishes raw effect, uncertainty normalization, the full locked construction, and a negative reference. It **cannot identify the incremental ranking contribution of evidence/capability gates** in the current registry because all 106 cases pass both gates and full Workbench equals uncertainty-only on this case universe.

## What the comparison cannot establish

- Biological efficacy, causal biological validity, or successful intervention selection.
- Drosophila whole-animal behavioral prediction or conversion of MN9 activity into behavior.
- Parkinson disease model validity, human disease relevance, wet-lab utility, cost savings, or clinical value.
- Benefit of evidence/capability gates when all cases pass them.
- Novelty or superiority of the ranking algorithm.
- Generalization beyond the declared public benchmark, even if a future held-out comparison is positive.

## Remaining comparator risks

1. Gate utility is not identifiable from a dataset with no gate variation; a separate prospective or development-only study would be needed to test that proposition.
2. The protocol's common-assessable rule is appropriate, but any missingness differences can change the evaluated case mix; report both system coverage and the same matched subset.
3. P@5 is sensitive to ties at the cutoff; the lexical case-ID tie rule is fixed but should be disclosed. Bootstrap intervals, if reported, are case-level ranking uncertainty, not biological uncertainty.
4. Random is intentionally weak. The effect-only comparator is the substantive baseline, and its non-inferiority/superiority results must be shown without story-driven omission.
5. Current artifact reports `coverage=1` for all four systems on development; this does not establish future held-out coverage.

## Advisory recommendation

`CODEX_RECOMMENDATION = OPTION_A`

The four systems match the completed frozen development ablation and answer the bounded component-ablation question without introducing post hoc comparators. Exclude `heuristic` because it violates the forbidden-input contract; exclude `original_model` because the legacy implementation duplicates its own `effect_only` alias and this raw-rate score was not part of the frozen ablation. This recommendation is not owner approval.

## Owner decision after integrity incident

The owner selected `OPTION_A`, approving the four primary systems listed above and excluding `heuristic` and `original_model`. The auditable comparator-only decision is recorded in [`configs/workbench/comparator_lock_v1.json`](../configs/workbench/comparator_lock_v1.json) and [`configs/workbench/final_evaluation_protocol_v1.json`](../configs/workbench/final_evaluation_protocol_v1.json).

`OWNER_COMPARATOR_APPROVAL = APPROVED_OPTION_A`

This approval freezes comparator selection only. Following the incident review, `HELDOUT_EXPOSURE_STATUS = UNVERIFIABLE` and `HELDOUT_PRISTINE_CLAIM = UNAVAILABLE`. The current 32-case set is `POST_FREEZE_POTENTIALLY_EXPOSED_EVALUATION_SET`; no held-out execution is authorized. The original selection timestamp was unavailable, so the recorded timestamp is explicitly the owner's Task 2B-R reaffirmation time, not an inferred original decision time.

## Original owner decision prompt — superseded

The options below are retained as historical context only. The owner has since selected OPTION_A, recorded in the incident-aware approval record above. They are no longer pending choices.

### OPTION A — APPROVE RECOMMENDED FOUR-SYSTEM SET

```text
rewire_effect_only
rewire_plus_uncertainty
full_workbench_locked
random_reference
```

Legacy heuristic/original-model excluded from primary held-out evaluation.

### OPTION B — REQUEST COMPARATOR REVISION

Owner must specify rationale. No held-out access permitted during revision.

### OPTION C — PAUSE FINAL EVALUATION

Comparator validity remains unresolved.
