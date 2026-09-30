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

Proposed version: `shiu_v2_final_evaluation_v1`. Comparator set follows the frozen four-system ablation, while legacy heuristic/original-model additions are explicitly unapproved. Protocol status: `PROPOSED_OWNER_APPROVAL_REQUIRED`; the dated owner approval, exact execution commit and approved evaluator command are intentionally absent. Score-lock v1 hash: `e522aba1bb58a0883a589255c09debbfc2cf0ad1841358242b3dd248e93aa452`. Benchmark semantic identity: `43b3704750572dade4774d514bcd986697f537b1b11de81ce918bac3310aad9f`. Proposed protocol file SHA-256: `ac253ef85b59dc0fe61dfdbd90c78740077ee452925978c4b5a32b8b0344ebdf` (any edit invalidates this pin).

## Manuscript and figures

The canonical draft [`workbench_state4_methods_results_draft_20260924.md`](workbench_state4_methods_results_draft_20260924.md) now includes Introduction, Methods, development-only Results, Discussion, claims boundary, and an explicit pending held-out section. Figure plan covers architecture, split/freeze, development ablation, reproducibility, and a non-data-accepting held-out placeholder renderer. No held-out figure values are populated.

## Scientific review

`SCIENTIFIC_CASE_REVIEW = PENDING`. Computational ID validation and source traceability are not expert confirmation of assay comparability or biological meaning. No reviewer sign-off was fabricated.

## Held-out boundary

`HELDOUT_STATUS = LOCKED_NOT_RUN`

The 32 held-out outcomes were not inspected and no held-out run or metric was performed for this package. The launcher refuses unless a literal owner approval token, owner-approved protocol, pinned source revision, clean worktree, exact hashes, new output directory, external single-use ledger, and hash-pinned evaluator explicitly contract-pinned to the held-out partition and 32 cases are all supplied. The current protocol cannot pass those gates.

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

Reasons: (1) comparator choice awaits owner approval; (2) Tuấn's independent reproduction remains pending; (3) external scientific case review remains pending; (4) exact platform execution commit and evaluator pin are not yet set; (5) the platform worktree contains pre-existing user changes that must be preserved and reconciled before a clean execution release. Owner may decide whether independent reproduction is a submission gate or use the documented owner-only contingency, but this package does not make that choice.

**POST_HELDOUT_DECISION_PENDING**. See [`paper_survival_gate.md`](paper_survival_gate.md) and [`pre_submission_checklist.md`](pre_submission_checklist.md).
