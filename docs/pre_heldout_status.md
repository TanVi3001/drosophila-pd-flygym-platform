# PRE-HELDOUT status report

**Checked:** 2026-09-28 on `feature/workbench-state4-review`

**Scope:** Workbench computational paper preparation

**HELDOUT_STATUS = LOCKED_NOT_RUN**

| Gate | Status | Evidence and remaining check |
|---|---|---|
| Development ablation | **COMPLETE** | 74 development cases; AP and precision@5 in the [Methods/Results draft](workbench_state4_methods_results_draft_20260924.md). No final held-out metric is reported here. |
| Owner-assisted reproduction | **PASS reported by owner** | Exact development-output reproduction was reported. Preserve the reference/replica artifacts and a separate owner validation record for release review. |
| Success reproduction case | **PASS reported by owner** | Reference and replica both completed; numerical output/provenance match was reported. |
| Failure/QC reproduction case | **PASS reported by owner** | Both sides preserved an explicit failure state; this is a technical QC check. |
| Independent second-operator reproduction | **PENDING — handoff prepared, operator run not yet performed** | Cross-machine path portability was fixed and regression-tested. A checksummed owner handoff is staged on E drive. Development reproduction, independent success/failure subset and final verifier have not been run by Tuấn. |
| Held-out evaluation | **LOCKED_NOT_RUN** | Final 32-case evaluation has not been run in this update. Do not open outcomes before the gate decision. |
| Biological validation | **NOT DONE / OUT OF CURRENT SCOPE** | Scientific mapping review is pending. No wet-lab or Parkinson claim follows from the computational results. |

The owner's reported success/failure verifier output had `status=PASS`,
`operator_role=same_operator`, `independent_operator_claim_eligible=False`,
and zero discrepancies. Those are **reported prior-run facts**, not a fresh
verification of the external owner artifacts performed by this update.

Tuấn's [2026-09-28 preflight record](../validation/second_operator_preflight_20260928/preflight_blockers.json)
reports clean checkouts, Python 3.12.10, passing dependency checks, matching
protocol/mapping identity and 9 software-contract tests. It explicitly records
`status=NOT_PASSED`, `independent_operator_claim_eligible=false`, and missing
frozen owner inputs. The owner-side package and rewired connectivity were
located on drive E after this preflight. A portable handoff was generated and
checksum-verified at `E:\research-\external\Drosophila_brain_model\results\workbench_benchmark_20260923\second_operator_handoff_20260928_v5`.
The owner-machine packaging check passes, but that does not establish an
independent run. The final held-out gate remains closed.

The active machine-readable gate file is
[`active_manuscript_scope.yaml`](../configs/workbench/active_manuscript_scope.yaml).
It records `scientific_case_review=PENDING_EXTERNAL_REVIEW`,
`independent_second_operator=PENDING_HUMAN_RUN`, and the final held-out
comparison as ready but not run. An older scope document references a partial
historical preparation report; that document is not treated as the final
locked evaluation. The publication team should reconcile that legacy record
without using it to tune or claim final held-out performance.

## Software checks in this update

- Python: isolated project Python 3.12.10.
- Synthetic contract modules: score lock, 106-case freeze logic, reproduction,
  and artifact integrity. These fixtures do not load the public benchmark
  cases or inspect held-out labels.
- A missing test-temp parent caused the first attempt to stop after 2 passes
  and 5 setup errors. Creating the temp directory on drive E resolved it.
- Portability regression cases cover different machine roots, changed input
  hashes, changed scientific parameters, and the controlled missing-annotation
  failure. The four related modules pass (`14 passed`).
- The portable owner reference campaigns pass a read-only verifier check from
  the handoff directory; this is a packaging check, not a second-operator run.

See [`pre_heldout_preparation.md`](pre_heldout_preparation.md) for the
remaining gate work and safe test command, and
[`pre_heldout_methods.md`](pre_heldout_methods.md) for the complete study flow.
