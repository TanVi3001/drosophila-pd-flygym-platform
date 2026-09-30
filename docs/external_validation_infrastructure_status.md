# External validation infrastructure status

`EXTERNAL_VALIDATION_INFRASTRUCTURE = READY`

`EXTERNAL_VALIDATION_DATASET = NOT_SELECTED`

`VALIDATION_LABELS_AVAILABLE_TO_OWNER = FALSE`

`NEW_VALIDATION_EXECUTION = FORBIDDEN`

`CURRENT_32_CASE_EXECUTION = FORBIDDEN`

`HELDOUT_PRISTINE_CLAIM = UNAVAILABLE`

`INDEPENDENT_CURATOR_REQUIRED = TRUE`

`NEXT_ACTION = INDEPENDENT_CURATOR_DATASET_SELECTION`

## What is ready

- The v1 owner-receipt contract is specified in [`external_validation_package_spec.md`](external_validation_package_spec.md).
- The access policy defines role-by-stage permissions and defaults graph pretraining to inductive.
- The no-peeking validator checks an owner-facing, synthetic-compatible receipt without opening a sealed-label directory.
- Prediction freeze, label release, owner receipt, curator handoff and AI V2 compatibility are documented separately.
- Automated tests use synthetic case IDs and synthetic metadata only.

## What is not ready/authorized

No external study has been selected, no real package has been received, and no labels are available to the owner. The validator is a syntactic safeguard—not a cryptographic access-control system or proof of semantic blinding. Deployment still needs separate curator/evaluator accounts, isolated storage and audit logs. The current 32 cases remain potentially exposed; no incident response restores their pristine status.

The two prior research exposure records are [Task 3A](external_validation_candidate_audit_exposure_20260930.md) and [Task 3A-R](external_validation_candidate_audit_exposure_20260930_task3ar.md). Dataset research is delegated to an independent curator and is not performed in the development workspace.
