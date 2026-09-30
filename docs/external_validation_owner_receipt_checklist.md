# Owner receipt checklist — blinded external validation

Complete this checklist when a curator submits an input-only package. It does not grant execution permission.

- [ ] I received no validation labels, outcomes, phenotype assignments, label schema, class totals or outcome-derived plots.
- [ ] The `validation_labels_sealed/` package is absent from the receipt and owner workspace used for this review.
- [ ] `python scripts/validate_external_validation_package.py <owner_receipt>` returns `NO_PEEKING_VALIDATION=PASS`.
- [ ] Manifest case count, assay type, source citation, curator identifier and UTC creation timestamp are present.
- [ ] Input schema version and its digest match the manifest; all receipt checksums verify.
- [ ] Case IDs are neutral, unique and ordered by ID; there is no outcome-coded filename, metadata or source-row order.
- [ ] Mapping review uses input-side identity/provenance only. Ambiguities are marked `REQUIRES_REVIEW`; no outcomes were used to resolve them.
- [ ] The assay/end point is explicitly classified as same-task, cross-assay or incompatible; behavior is not relabeled as MN9 activity.
- [ ] Current Workbench science, score/comparator lock and `k=5` remain unchanged. Any assay-specific adapter or metric is separately proposed and frozen before labels.
- [ ] A label-blind evaluation plan and evaluator hash are approved before execution; this checklist alone does not authorize either current-32 or new validation execution.
- [ ] Both prior search-snippet exposure records were considered when judging whether the selected source can genuinely remain blinded.

Receipt disposition: `PENDING` / `ACCEPTED_FOR_PROTOCOL_REVIEW` / `REJECTED`.
Reviewer and date: record only after completing the checks above.
