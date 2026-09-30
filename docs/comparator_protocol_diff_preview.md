# Comparator protocol diff preview — not applied

This preview describes the minimum comparator-lock changes **if the owner later chooses OPTION A** in [`comparator_approval_packet.md`](comparator_approval_packet.md). It is not an approval record. The current final protocol remains `PROPOSED_OWNER_APPROVAL_REQUIRED`, and `owner_approval.status` remains `PENDING`.

## Changes required for comparator lock

The current `comparators.proposed_primary_set` already contains exactly the recommended four IDs and definitions. **No comparator score definition, primary ID, metric, split, score-lock setting, or `k=5` change is required.** The only comparator-decision text that would need to become owner-final is the `comparators.decision` string. The legacy definitions can remain as legacy metadata, with a clear owner-approved disposition that neither is in the primary evaluation.

| JSON path | Current value | Preview after owner OPTION A (example only) |
|---|---|---|
| `status` | `PROPOSED_OWNER_APPROVAL_REQUIRED` | `OWNER_APPROVED` |
| `owner_approval.status` | `PENDING` | `APPROVED` |
| `owner_approval.approver` | `null` | Actual owner's recorded name (must be supplied by owner; no value inferred here) |
| `owner_approval.approved_at_utc` | `null` | Actual approval timestamp (must be supplied by owner; no timestamp created here) |
| `owner_approval.decision_note` | Resolve legacy heuristic/original-model comparator discrepancy before held-out execution. | Owner approved the four listed primary systems; heuristic and original_model excluded from primary evaluation. |
| `comparators.decision` | Do not execute held-out until the owner records either approval of this set or an alternate predeclared set and required development verification. | Owner selected OPTION A for the existing four-system primary set; legacy heuristic/original_model are not in the primary evaluation. |

The preview above does **not** mean those edits were made. Do not mark the protocol owner-approved until the owner explicitly chooses an option and supplies their identity and timestamp. If an alternate decision is chosen, this preview is void and a revised candidate/diff is needed without held-out access.

## Changes deferred to Task 4

These fields remain untouched by comparator approval and must be handled in the later authorized execution-pinning task:

- `source_identity.platform_execution_commit` — exact clean execution commit.
- `approved_executor` — reviewed, content-hash-pinned evaluator contract.
- evaluator hash and exact command/arguments.
- any corresponding final protocol file SHA-256 refresh after owner approval and execution pinning.
- clean worktree, input identities, output directory, and one-use external ledger checks.

No held-out case is run during comparator approval. Even after owner selects OPTION A, the held-out gate is not open until the separately required independent reproduction, scientific review, Task 4 pins, and explicit execution authorization are complete.
