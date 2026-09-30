# Paper PRE-HELDOUT readiness report

**Review date:** 2026-09-30  
**Platform branch:** `feature/workbench-state4-review`  
**Starting platform commit:** `646c6e9ca35c771aca578994fe731353c7a26625`  
**Starting root/superproject commit:** `e588101a361dede32f8d5d6c66cd5d21dfdfbd36`  
**Frozen neural source revision:** `e8a3cb2de2107925311053f9afcf2bfbc39fdf3c`

## Paper story

Fly Research Workbench is a scope-bounded software methods layer between a research question and human experiment planning. It asks whether the available evidence and declared simulator support the proposed study, binds a supported study into a StudySpec, records simulation provenance and QC/failure states, and presents candidates for human prioritization. Its current evidence supports a workflow/reproducibility claim, not biological accuracy, behavior prediction, Parkinson validity, or wet-lab efficacy.

## Novelty

Potential contribution is the integration of evidence/capability constraints, explicit abstention, StudySpec approval, provenance/QC and prioritization—not any one component in isolation. Connectome/model/simulation/provenance systems already exist, the gates do not vary in this benchmark, and direct comparison to neuroscience virtual-screening systems remains pending. **NOVELTY_RISK = HIGH.** See [`novelty_matrix.md`](novelty_matrix.md).

## Development evidence

Frozen 74-case development metrics: effect-only AP 0.659/P@5 0.80; uncertainty-adjusted and full Workbench AP 0.626/P@5 0.80; random AP 0.248/P@5 0.40; coverage 1.00 for all. Full Workbench does not beat effect-only. Both gates pass on all 106 registered cases, so their incremental ranking value is not identifiable. See [`development_evidence_summary.md`](development_evidence_summary.md).

## Reproduction

Owner development and technical success/failure subset reproduction are reported PASS with `operator_role=same_operator`; artifact-level exact development output is reported byte-identical. The independent second-operator run by Tuấn remains **PENDING**. Do not claim independent reproduction until a separate operator's evidence is reviewed.

## Final evaluation protocol

Version: `shiu_v2_final_evaluation_v1`. The owner approved the four-system comparator set under OPTION_A; `heuristic` and `original_model` are excluded. Protocol status: `OWNER_APPROVED_COMPARATORS_ONLY`. This records comparator choice only; platform execution commit, approved evaluator and command, execution ledger, and approval token remain unresolved. The comparator lock is [`../configs/workbench/comparator_lock_v1.json`](../configs/workbench/comparator_lock_v1.json). Score-lock v1 hash: `e522aba1bb58a0883a589255c09debbfc2cf0ad1841358242b3dd248e93aa452`. Benchmark semantic identity: `43b3704750572dade4774d514bcd986697f537b1b11de81ce918bac3310aad9f`. Final protocol SHA-256: `A072A3822481EAEB01A49545FD08C472E1CF315E7064EDED3EA9F320D1BAE247` (any protocol edit invalidates this digest).

## Manuscript and figures

The canonical draft [`workbench_state4_methods_results_draft_20260924.md`](workbench_state4_methods_results_draft_20260924.md) now includes Introduction, Methods, development-only Results, Discussion, claims boundary, and an explicit pending held-out section. Figure plan covers architecture, split/freeze, development ablation, reproducibility, and a non-data-accepting held-out placeholder renderer. No held-out figure values are populated.

## Scientific review

`SCIENTIFIC_CASE_REVIEW = PENDING`. Computational ID validation and source traceability are not expert confirmation of assay comparability or biological meaning. No reviewer sign-off was fabricated.

## Held-out boundary

- `HELDOUT_EXPOSURE_STATUS = UNVERIFIABLE`
- `HELDOUT_PRISTINE_CLAIM = UNAVAILABLE`
- `HELDOUT_STATUS = LOCKED_NOT_RUN`
- `HELDOUT_EXECUTION_AUTHORIZED = FALSE`

`PRE_INCIDENT_METHOD_FREEZE = PRESERVED` at `7a1277338fe23169f961f9bd4cc1543670314eaf`. `NEW_PROSPECTIVE_VALIDATION_DESIGN = REQUIRED_FOR_STRONG_CONFIRMATORY_CLAIM`.

The integrity incident review could not determine whether any displayed case-level labels intersected the frozen 32-case set. The set is therefore `POST_FREEZE_POTENTIALLY_EXPOSED_EVALUATION_SET`, not a pristine confirmatory set. No held-out evaluation or metric was run for this task. The launcher remains execution-gated and the current protocol explicitly does not authorize a run. A new prospective validation design is required for a strong confirmatory claim; do not present this set as untouched or pristine.

The invocation is intentionally only a template; do not set the approval token from this preparation task:

```powershell
python scripts/run_guarded_heldout_evaluation.py `
  --protocol configs/workbench/final_evaluation_protocol_v1.json `
  --expected-protocol-sha256 <owner-verified-protocol-sha256> `
  --expected-source-commit <owner-approved-clean-40-character-commit> `
  --rewire-scores <frozen-score-file> `
  --output <new-directory-outside-repository> `
  --execution-ledger <new-external-single-use-ledger.json>
```

The expected commit and protocol digest are passed from the owner's reviewed execution record to avoid a self-referential commit hash inside the protocol being executed.

## Decision and remaining blockers

**NOT_READY_FOR_HELDOUT**

Reasons: (1) the current 32-case set is potentially exposed and cannot support a pristine confirmatory claim; (2) Tuấn's independent reproduction remains pending; (3) external scientific case review remains pending; (4) exact platform execution commit and evaluator pin are not yet set; (5) a prospective validation design is required for a strong confirmatory claim; (6) pre-existing user changes must be preserved and reconciled before any clean execution release. Comparator selection is approved, but that approval does not unlock execution.

**POST_HELDOUT_DECISION_PENDING**. See [`paper_survival_gate.md`](paper_survival_gate.md) and [`pre_submission_checklist.md`](pre_submission_checklist.md).
