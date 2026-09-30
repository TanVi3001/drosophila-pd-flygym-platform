# External validation label-release protocol

Labels remain in the independent curator's vault unless every gate below is satisfied. No dataset is currently selected, and this protocol does not authorize a run or release.

## Preconditions for release

1. An owner-approved external protocol identifies the assay, eligible population, input schema, exclusions, endpoint and analysis plan.
2. The owner receipt passes `scripts/validate_external_validation_package.py`; the curator separately verifies input/label ID correspondence without sharing outcomes.
3. The prediction package exists in immutable/read-only storage and has a verified SHA-256 manifest, frozen source commit, environment/command identity, timestamp and operator record.
4. The independent curator independently verifies the prediction package hash and signs a `PREDICTIONS_FROZEN` attestation before accessing/releasing label material.
5. A separate evaluator implementation and its source hash are frozen. The metric family and analysis code are declared after input-schema/assay review but before outcome revelation. They are not selected by observing outcomes.
6. The owner signs a written label-release authorization; the curator records the authorization and release event in an append-only audit log.

## Release path

The curator transfers `label_schema.json` and `validation_labels_sealed/` directly to the independent evaluator, not to the owner repository, Codex workspace, LLM/RAG index, simulator, or model-training environment. The evaluator verifies curator-provided hashes, joins only on neutral IDs, computes the frozen analysis, and reports predeclared aggregate metrics, denominators and failures. Raw labels stay curator/evaluator-only. The owner receives the evaluator's signed aggregate report after the analysis passes the audit checks.

Any missing gate means `LABEL_RELEASE = DENIED`. The owner cannot waive the prediction freeze after seeing labels. A compromised prediction package or leaked label requires stopping and documenting the incident; it cannot be repaired by changing IDs or rerunning on the same outcomes.

## Metric freeze

Do not assume internal P@5 is suitable. After input format, endpoint and independent unit are known—but before labels are revealed—the owner/statistician and evaluator predeclare the metric family, tie/missing-data handling, common denominator, uncertainty method and multiplicity policy. Candidate families may include ranking, binary classification or continuous-response agreement. Selection among them is outside this infrastructure task.
