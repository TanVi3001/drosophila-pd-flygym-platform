# External validation candidate-audit exposure — 2026-09-30

## Status

`TASK_3A_STATUS = STOPPED_AFTER_ACCIDENTAL_RESULT_SNIPPET_EXPOSURE`

This note records an accidental research-output exposure during the metadata-only candidate audit. It intentionally omits all outcome directions, labels, values, and case identifiers.

## What happened

While searching primary-source material for the Shiu et al. 2024 Drosophila computational brain-model paper, a web-search response returned snippets containing experimental result statements. A later response from the paper's public PMC full-text page returned more extensive result-bearing prose, including aggregate performance statements. These result excerpts entered the assistant's context. After recognizing that the output crossed the task's no-outcome-inspection boundary, research stopped immediately.

Queries involved the paper title and requests for its public data-availability / optogenetic-experiment metadata. The result-bearing sources were the Nature article and its PMC full-text record:

- https://www.nature.com/articles/s41586-024-07763-9
- https://pmc.ncbi.nlm.nih.gov/articles/PMC11446845/

No supplementary outcome table, CSV, or dataset was opened or downloaded by this audit. No candidate external dataset was selected, no metrics were calculated, and no validation execution occurred. This does not undo the fact that outcome-bearing text appeared in the search output.

## Scope and implications

- Assistant-context exposure to result-bearing Shiu-paper text: **confirmed**.
- Owner's independent prior exposure: **not assessed**.
- Whether the exposed statements overlap the project's current internal benchmark or any proposed candidate subset: **not assessed**; no benchmark registry, held-out membership, or label file was inspected for this note.
- Candidate suitability decision: **not made**.
- Current internal-set state remains governed by the existing incident record: `HELDOUT_PRISTINE_CLAIM = UNAVAILABLE`.
- `CURRENT_32_CASE_EXECUTION = FORBIDDEN` and `NEW_VALIDATION_EXECUTION = FORBIDDEN` for this task.

The Shiu paper and any outcome-bearing subset from it must not be described as label-blind or independently sealed on the basis of this audit. An independent curator would need to decide whether any future candidate can still be sealed without the exposed information influencing the curator or prediction process.

## Required next step

Do not resume Task 3A dataset ranking or select a validation dataset from this session. The owner should decide whether to restart the literature audit in a genuinely isolated/blinded process or exclude outcome-bearing sources already surfaced here. No new split from the existing 106 cases should be created as a remedy.

No score lock, comparator lock, `k=5`, model, ranking logic, split, or execution authorization was changed.
