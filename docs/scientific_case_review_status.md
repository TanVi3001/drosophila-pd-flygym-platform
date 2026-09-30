# Scientific case review status

**SCIENTIFIC_CASE_REVIEW = PENDING** (`PENDING_EXTERNAL_REVIEW` in active scope). No expert sign-off is inferred from automated mapping, owner testing, or this documentation update.

| Review class | Current status | Permitted interpretation |
|---|---|---|
| Computationally validated mapping fields and IDs | Recorded in frozen mapping/benchmark artifacts; software can validate schema and IDs | The exact computational IDs and declared protocol were used. |
| Source-data-supported links | Source-linked mapping records and public Shiu/FlyWire source references exist | Traceability to cited source material, not proof that an assay is biologically comparable. |
| Ambiguous assay/context mappings | Must remain `REQUIRES_REVIEW` or unassessable until a domain reviewer resolves them | Do not force a positive/negative interpretation. |
| Cases requiring expert review | External domain review remains pending for the active case registry | Do not describe review as complete or imply gene/driver specificity. |
| Excluded from stronger biological interpretation | All mappings without completed expert review; all firing-to-behavior, Parkinson and wet-lab claims | Use only for the bounded computational benchmark; no causal biological claim. |

The score artifact's approval fields and the status of biological validity are separate questions. Even a computationally approved mapping does not establish assay equivalence or model validity. Update this file only when dated reviewer records and scope are available.
