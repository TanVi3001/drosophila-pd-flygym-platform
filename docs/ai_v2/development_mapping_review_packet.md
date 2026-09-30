# Development-only mapping review packet

The companion machine-readable table is [`data/ai_v2_dev/development_mapping_v1.json`](../../data/ai_v2_dev/development_mapping_v1.json). It has exactly the 74 approved development case IDs and **no labels**. Each row records the source biological identifier, normalized identifier, target FlyWire IDs/count, inherited exact name-to-neuron-set method, source and registry hashes, ambiguity state, duplicate/shared target counts, and review state. The upstream mapping registry has SHA-256 `67291ca3b68b79b2ec1d6f32c3ba7fcc938cbcffe1c25e867b39afc9e7e89165`; the source neuron-set artifact hash is recorded per row. This audit does not inspect or list held-out case records.

All 74 rows are `TECHNICAL_EXACT_MATCH` and `REQUIRES_SCIENTIFIC_REVIEW`. There are no technically ambiguous or rejected DEV mappings in this packet, and **zero scientifically approved rows**. Technical name matching and presence in the graph do not establish assay equivalence or biological validity. Two development cases share targets; three unique target neurons appear in more than one case. Those rows deserve particular attention for unit-of-analysis and fold-dependence review.

Reviewer checklist for each development row:

1. Verify source identifier, normalization and upstream neuron-set provenance against the source study.
2. Confirm the FlyWire ID set and whether source names correspond to the intended neuron/cell population, including side and multiplicity where the source permits it.
3. Assess assay and readout comparability; mark uncertainty rather than infer a mapping from a convenient graph match.
4. Examine shared-target cases as potentially correlated experimental units.
5. Record a named domain reviewer, dated decision and evidence before changing any row to `SCIENTIFICALLY_APPROVED`. `AMBIGUOUS` and `REJECTED` remain valid decisions. This task makes no approval decisions.

Only a human scientific reviewer can close this packet. Any future analysis must disclose the review state of the mappings it uses.
