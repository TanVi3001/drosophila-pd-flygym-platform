# Shiu v2 held-out score preparation summary

Status: `PARTIAL_BASELINES_ONLY`

This is a retrospective published-field score preparation report. It is not a
complete comparative result and does not establish biological validity.

## Frozen protocol

- Protocol: `shiu-public-retrospective-v2-table3`
- Protocol hash: `43b3704750572dade4774d514bcd986697f537b1b11de81ce918bac3310aad9f`
- Cases: 106 total; 74 development; 32 held-out
- Labels: 14 positive, 92 negative response-presence labels
- Missing declared system: `degree_preserving_rewire`

## Held-out metrics

| System | Coverage | Precision | Recall | Precision@5 | Average precision | Unassessable | False negatives |
|---|---:|---:|---:|---:|---:|---:|---:|
| Workbench | 1.0000 | 1.0000 | 0.5000 | 0.6000 | 0.7900 | 0 | 2 |
| Effect-only | 1.0000 | 1.0000 | 0.5000 | 0.6000 | 0.7900 | 0 | 2 |
| Original-model | 1.0000 | 1.0000 | 0.5000 | 0.6000 | 0.7900 | 0 | 2 |
| Random | 1.0000 | 0.0769 | 0.2500 | 0.0000 | 0.1381 | 0 | 3 |
| Heuristic | 0.9688 | 0.2500 | 1.0000 | 0.4000 | 0.4103 | 1 | 0 |

The heuristic is unassessable for `shiu_table3_row_067` because its declared
shortest-path score is missing. The common assessable denominator is therefore
31/32, so the cross-system status remains `PARTIAL`.

The current published-field Workbench score has the same summary metrics as
effect-only and original-model. This does not support a superiority claim; it
indicates that the current score construction is not yet discriminating those
systems on this registry.

## Required next evidence

1. Domain reviewers complete the 106-row source/assay comparability packet.
2. A real degree-preserving-rewire backend produces scores for the exact frozen
   case IDs.
3. The final comparison uses a complete matched held-out denominator, or keeps
   the result explicitly partial.
