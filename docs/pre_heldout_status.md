# PRE-HELDOUT status

**Checked:** 2026-09-30. **Platform branch:** `feature/workbench-state4-review`. **Platform starting commit:** `646c6e9ca35c771aca578994fe731353c7a26625`. **Root/superproject starting commit:** `e588101a361dede32f8d5d6c66cd5d21dfdfbd36`. **Frozen neural source revision:** `e8a3cb2de2107925311053f9afcf2bfbc39fdf3c`.

**HELDOUT_STATUS = LOCKED_NOT_RUN**

| Gate | Status | Evidence / remaining requirement |
|---|---|---|
| Development ablation | **COMPLETE** | 74-case frozen development artifact; exact metrics and interpretation in [`development_evidence_summary.md`](development_evidence_summary.md). |
| Owner-assisted reproduction | **PASS reported; same operator** | Owner reports byte-identical development output. Do not label independent. |
| Success reproduction case | **PASS reported; same operator** | Owner reference/replica completed and verifier reportedly passed. |
| Failure/QC reproduction case | **PASS reported; same operator** | Explicit controlled failure reproduced; technical QC, not biological evidence. |
| Independent second-operator reproduction | **PENDING** | Handoff is checksummed; Tuấn's run and final verifier evidence are not present. |
| Comparator protocol approval | **APPROVED_OPTION_A — COMPARATOR ONLY** | Four score-lock systems approved; `heuristic` and `original_model` excluded. See [`comparator_lock_v1.json`](../configs/workbench/comparator_lock_v1.json). |
| Scientific case review | **PENDING EXTERNAL REVIEW** | No expert sign-off supplied. |
| Held-out integrity | **UNVERIFIABLE** | Accidental label display occurred; the available transcript cannot establish whether the displayed records intersected the 32-case set. Pristine claim unavailable. |
| Held-out evaluation | **LOCKED_NOT_RUN** | Comparator approval only. Execution is unauthorized; exact source/executor pins and a new prospective validation design for a strong confirmatory claim remain required. |
| Biological validation | **NOT DONE / OUT OF SCOPE** | No wet-lab, Parkinson, direct behavior, or intervention validation claim. |

Software tests, computational reproduction, independent reproduction, held-out evaluation, and biological validation are five distinct evidence classes. A PASS at one level does not imply a PASS at another.

`PRE_INCIDENT_METHOD_FREEZE = PRESERVED` at `7a1277338fe23169f961f9bd4cc1543670314eaf`. `OWNER_COMPARATOR_APPROVAL = APPROVED_OPTION_A`. `HELDOUT_PRISTINE_CLAIM = UNAVAILABLE`. `NEW_PROSPECTIVE_VALIDATION_DESIGN = REQUIRED_FOR_STRONG_CONFIRMATORY_CLAIM`.

The active machine-readable scope is [`active_manuscript_scope.yaml`](../configs/workbench/active_manuscript_scope.yaml). The incident-aware protocol records comparator approval only and does not unlock held-out.
