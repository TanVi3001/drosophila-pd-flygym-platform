# B02 — Task 1C Go/No-Go decision

**B02_STATUS = COMPLETE**  
**GRAPH_SIGNAL_DECISION = GRAPH_SIGNAL_UNSUPPORTED**  
**B03_STATUS = NOT_TRIGGERED**  
**HELDOUT_STATUS = LOCKED_NOT_RUN**

## Decision basis

This decision applies the rule fixed in [`task1c_robustness_experiment_spec.md`](task1c_robustness_experiment_spec.md) to the five-fold, 74-case development-only run. The rule and Task 1 configuration were not changed after observing results. Metrics below are means across the five validation folds, not a pooled ranking over all 74 cases.

| System | AP | ΔAP vs B0 | P@5 | ΔP@5 vs B0 | Recall@5 | Coverage |
|---|---:|---:|---:|---:|---:|---:|
| B0 — effect-only | 0.750 | 0.000 | 0.28 | 0.00 | 0.70 | 1.00 |
| B1 — structural only | 0.426 | −0.323 | 0.20 | −0.08 | 0.50 | 1.00 |
| B2 — effect + structural | 0.524 | −0.226 | 0.20 | −0.08 | 0.50 | 1.00 |
| B3 — GraphSAGE | 0.433 | −0.316 | 0.16 | −0.12 | 0.40 | 1.00 |
| B4 — effect + GraphSAGE | 0.635 | −0.115 | 0.28 | 0.00 | 0.70 | 1.00 |

## Rule application

The `GRAPH_SIGNAL_ROBUST` rule is **not met**: B4 has ΔAP −0.115 (required ≥0.05), ΔP@5 0.00 (required ≥0.04), and beats B0 on AP in only 1 of 5 folds (required at least 4). Although B4 mean AP exceeds B2, the full conjunction fails. The leave-one-fold-out B4−B0 AP differences are positive only when fold 0 is omitted; the other four are negative.

The fallback `GRAPH_SIGNAL_STILL_WEAK` rule is also **not met**. Neither graph-containing system has a positive mean ΔAP or ΔP@5 versus B0:

- B3: ΔAP −0.316; ΔP@5 −0.12.
- B4: ΔAP −0.115; ΔP@5 0.00.

Therefore the preregistered outcome is **`GRAPH_SIGNAL_UNSUPPORTED`** for these graph features, mappings, model settings and 74 development cases.

## Go/no-go action

- Do not proceed to B03 representation expansion under the current evidence; do not add graph complexity or tune this setup against the same results.
- Preserve the negative result as a valid development finding. If a distinct graph hypothesis is proposed later, specify it and its evaluation protocol before looking at its results.
- Continue work on the independently scoped Workbench/RAG workflow rather than waiting for graph-model gains.

This is not evidence that connectome structure is biologically irrelevant. The evaluation is small and development-only; moreover, all 74 inherited mappings remain pending scientific review. It does not establish biological correctness, external generalization, wet-lab utility, or an independent replication.

## Integrity and provenance

- B01 output: [`task1c_robustness_v1/summary.json`](../../results/ai_v2_dev/task1c_robustness_v1/summary.json)
- B01 manifest: [`task1c_robustness_v1/experiment_manifest.json`](../../results/ai_v2_dev/task1c_robustness_v1/experiment_manifest.json)
- Experiment manifest SHA-256: `b61c5ddea9a1435e6547f931dca1e48c6b8f571f47d26c5cbf21215a4158b591`
- Preregistration SHA-256: `2494f16432caa7ed7142121caab62edbe6017c011a7f47f9a17246d6432adbdc`
- All 12 listed B01 output artifact hashes were rechecked before recording this decision.
- Only `DEVELOPMENT_INPUT`, `DEVELOPMENT_LABEL` (exactly the approved 74 cases), and `PUBLIC_UNLABELED` access classes appear in the run audit. No held-out or external validation was read or run.
