# Task 3A-R candidate-audit exposure — 2026-09-30

## Status

`TASK_3A_R_STATUS = STOPPED_AFTER_CANDIDATE_LEVEL_OUTCOME_SNIPPET`

This note records a second accidental exposure during the metadata-only external-validation audit. It contains no individual phenotype, label, outcome value, or neuron-level result.

## What happened

A web search was issued for the fixed Candidate B source, Cande et al. 2018, to locate its public Data Availability information and repository metadata. The search response included a snippet from the public PMC full-text record containing result-section text that described individual activation phenotypes. That candidate-level content entered the assistant's context. The audit stopped as soon as the boundary violation was recognized.

Source returned in the search response:

- https://pmc.ncbi.nlm.nih.gov/articles/PMC6031430/
- Dataset landing page specified by the owner: https://doi.org/10.5061/dryad.fr89c0c

The full paper was not opened separately for this audit, and no Dryad outcome file or table was downloaded or inspected. This does not undo the search-snippet exposure.

## Scope and implications

- Assistant-context exposure to candidate-level Cande result text: **confirmed**.
- Owner's independent prior exposure: **not assessed**.
- Candidate-level outcome values reproduced in this record: **no**.
- Candidate suitability or individual-case selection: **not assessed**.
- Whether this source could be independently sealed by a separate curator: **not determined**.
- No candidate validation was executed and no metrics were calculated.
- Current internal held-out state remains unchanged: `HELDOUT_PRISTINE_CLAIM = UNAVAILABLE` and `CURRENT_32_CASE_EXECUTION = FORBIDDEN`.
- `NEW_VALIDATION_EXECUTION = FORBIDDEN`.

Do not use this assistant session as a blinded curator for Cande outcomes. Do not continue Task 3A-R candidate ranking from this session. Any restart must use an independent process that has not received the result-bearing snippet, or exclude this source from a blinded analysis unless an independent curator can establish a clean separation.

No score lock, comparator lock, split, `k=5`, model, ranking logic, or execution authorization was changed.
