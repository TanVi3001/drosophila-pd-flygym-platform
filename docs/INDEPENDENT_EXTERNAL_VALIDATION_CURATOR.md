# Independent external-validation curator handoff

## Separation requirement

Dataset discovery and outcome handling belong to the independent curator, outside the owner/Codex development workspace. The curator may inspect source papers and outcome data as needed for eligibility and label construction; the owner, Codex, LLM/RAG, simulator and training processes must not receive candidate outcomes before predictions are frozen. Do not use the owner/Codex workspace for literature or outcome discovery. This separation is important because two earlier audit attempts recorded result-bearing search-snippet exposures: [first exposure record](external_validation_candidate_audit_exposure_20260930.md) and [Task 3A-R exposure record](external_validation_candidate_audit_exposure_20260930_task3ar.md).

## Curator workflow

1. **Select and document a source independently.** Choose a Drosophila study with a defensible scientific question, accessible methods/data metadata, identifiable intervention and response, a suitable independent unit, and enough cases for the planned analysis. Confirm it is not part of the current 106-case benchmark or development evidence. The source choice is not made by this repository task.
2. **Assess assay fit without forcing equivalence.** Record organism/life stage, intervention, target identity, response modality, connectome/cell-type mapping feasibility, and whether the work is same-task or cross-assay. If a target is ambiguous, mark `REQUIRES_REVIEW`; never infer a biological mapping from a convenient connectome match. A behavioral endpoint is not an MN9 firing measurement.
3. **Predeclare the package and analysis.** Agree with the owner on the input schema, eligible-case rules, metric family, independent unit, exclusion policy and missingness handling before revealing any outcomes. Do not tune an endpoint or metric after seeing labels.
4. **Create neutral IDs.** Assign IDs such as `EXTVAL_0001`, sorted lexicographically. Keep the ID-to-source-record key only in the curator vault. Do not encode response, genotype group, source order, class, phenotype or expected rank in IDs, filenames, descriptions or row order.
5. **Build the input-only receipt.** Create `validation_input_package/input_schema.json` and `cases.jsonl` containing only case IDs, assay/intervention metadata, target identity, mapping provenance and simulator inputs. Add the metadata-only `validation_manifest.json`; put only the label-schema digest in it. Generate `checksums.sha256` covering the manifest and owner-facing input files.
6. **Build the sealed package separately.** In a different access-controlled location, keep `label_schema.json`, the ID-to-source key and `validation_labels_sealed/labels.jsonl`. Create a curator-only `curator_checksums.sha256` for the schema and sealed labels; never include it in the owner receipt. Do not place these files in Git, shared development drive, owner email, or LLM/RAG corpus.
7. **Run package checks before handoff.** On a copy of the owner-facing receipt, run `python scripts/validate_external_validation_package.py <owner_receipt>`. Review failures without opening the sealed package from the owner environment. The validator's PASS is not a substitute for your signed no-leakage attestation.
8. **Transfer input only.** Send the owner only the receipt directory, manifest, checksums and citation. Do not send the label schema itself, class totals, label-bearing filenames, result plots, per-class QC or outcome-dependent inclusion notes.
9. **Retain and protect labels.** Preserve the sealed package and source mapping privately with access logs. Do not reveal labels until the owner has frozen predictions and the independent evaluator has verified the freeze hash and owner authorization.
10. **Release to evaluator only.** After all release gates pass, verify the curator-only checksum and send the sealed labels directly to the evaluator. The evaluator returns a signed aggregate report; the curator keeps the raw label package and documents any discrepancy or failed join.

## Required curator attestations

- The input package was prepared without encoding outcomes in identifiers, filenames, ordering or descriptive metadata.
- The owner receipt contains no outcome values and no label package.
- The sealed package remained under curator-only access before the verified prediction freeze.
- The source is independent of the current 106-case benchmark and declared development evidence, to the extent ascertainable from provenance.
- Any uncertain mapping or case eligibility was flagged for review rather than guessed.

If any attestation cannot be made, do not release the package as blinded validation. Stop and report the limitation without forwarding labels.
