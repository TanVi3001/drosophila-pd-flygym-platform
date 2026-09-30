# Held-out integrity incident review — 2026-09-30

## Determination

- **Incident classification:** `HELDOUT_EXPOSURE_UNVERIFIABLE`
- **Remediation recommendation:** `HELDOUT_PRISTINE_CLAIM_UNAVAILABLE`
- **Held-out execution authorized:** `FALSE`

This is a conservative metadata-only determination. It is not evidence that a held-out case was or was not among the records exposed.

## What happened

During an earlier repository search, a broad text search included the FlyWire-630 case-mapping CSV. Its output displayed multiple case-level mapping records together with their annotation/label fields. The output captured in the available conversation is truncated: the tool reported 455 output lines, while the rendered excerpt showed at least 26 mapping-record lines. The exact number of label-bearing rows and the complete set of identifiers cannot be reconstructed reliably from that capture. This report deliberately does not reproduce any case identifier, label, or row content.

The command that caused the exposure was:

```text
rg -n "Lê Tấn Vĩ|Le Tan Vi|Tấn Vĩ|approver|owner_name|project owner" docs configs README.md --glob '!**/*held*out*'
```

The search scope included `configs/workbench/shiu_v2_flywire630_mapping.csv`. The exact wall-clock time of the search is not recoverable from the captured output. This review used the existing conversation record only; it did not repeat the broad search or open the mapping or held-out membership files.

## Exposure and knowledge assessment

- Label/annotation text was displayed in the prior tool output: **yes**.
- Case-level records and label text appeared together: **yes, in the visible excerpt**.
- Complete exposed identifier set recoverable: **no**.
- Intersection with the frozen 32-case held-out membership verifiable without guessing: **no**.
- Held-out labels exposed: **unverifiable**. The available record does not support either confirming or ruling out an intersection.
- Outcome-linked knowledge: the output created the possibility of associating displayed labels with case-level records. Whether any such record was held out cannot be established from the available capture.
- Scientific adaptation based on the exposed output: **none found in the committed repository history after the incident**. The current HEAD remains `7a1277338fe23169f961f9bd4cc1543670314eaf` (`Prepare final comparator approval packet`), with no later commit. The temporary local Task 2B attempt concerned approval metadata and was reverted; current tracked diffs do not contain changes to the score formula, `k`, split, comparator definitions, model, or ranking. This statement is limited to the evidence available in repository history and the current worktree.

Because the exposed identifiers cannot be reconstructed reliably, this review did not run a membership-intersection program. Aggregate counts for exposed rows and held-out/development intersections are therefore `null` (unknown), not zero.

## Required handling

1. Do not claim that the held-out set remained pristine or that no held-out label was exposed.
2. Keep the existing held-out split and score lock unchanged; do not create a replacement split as a response to this incident.
3. Keep held-out execution locked. This incident review does not approve, authorize, or resume Task 2B comparator approval.
4. Preserve this incident record and the captured audit trail. Any future paper or report must disclose that held-out label exposure could not be ruled out and must not present the locked set as an untouched confirmatory evaluation.
5. Obtain owner/statistical-reviewer direction on a prospective evaluation design before any held-out execution. Do not infer that a newly selected split is independent or pristine without a documented, pre-specified design.

## Scope and claim boundary

This review performed no simulation, benchmark, score calculation, label inspection, held-out membership inspection, or split modification. It makes no biological, Parkinson's disease, wet-lab, or model-validity claim. It records an integrity limitation only.

## Repository evidence

- Pre/post incident repository revision available for this review: `7a1277338fe23169f961f9bd4cc1543670314eaf`.
- No commits after that revision were present at review time.
- Existing unrelated worktree changes were preserved and not included in this review's edits.
- Machine-readable status: `configs/workbench/heldout_integrity_status.json`.
