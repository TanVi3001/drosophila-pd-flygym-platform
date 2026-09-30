# External validation prediction freeze

No validation dataset is selected and no prediction run is authorized by this document. It defines the required freeze record for a future owner-approved protocol.

## Freeze sequence

```text
INPUT PACKAGE
    ↓
schema + no-peeking validation
    ↓
owner mapping review without labels
    ↓
frozen Workbench execution under a separately approved protocol
    ↓
predictions.csv
    ↓
SHA-256 + source commit + environment/command identity
    ↓
prediction manifest signed by owner and verified by curator
    ↓
PREDICTIONS_FROZEN
```

The frozen prediction package must include neutral case IDs, predictions/scores, predeclared unassessable states, protocol ID/hash, input-package hash, score/comparator lock identities, source commit, environment identity, command digest, operator, UTC timestamp and checksum manifest. It must not include labels or outcome-derived metadata.

## Immutability and reruns

Write the package to a new, non-overwriting location, hash it, and transfer a read-only copy to the independent curator. The curator records receipt time and verifies the digest before releasing anything. Do not edit predictions, reorder cases, remove failed cases, or replace an artifact after freeze. A rerun is a new, separately named and disclosed prediction package with its own commit, protocol, reason and hashes; it does not erase the first attempt. The evaluator must preserve all attempts and use only the predeclared one for the primary analysis.

The current Workbench score/comparator locks do not automatically define an external-assay score. Any assay-specific adapter or metric requires prospective approval before labels are revealed. No model fitting or tuning may use validation labels.
