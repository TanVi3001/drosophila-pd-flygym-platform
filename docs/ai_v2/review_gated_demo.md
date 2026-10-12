# Review-gated end-to-end demo (synthetic only)

This demo exercises the requested path:

`Protocol → local evidence retrieval → draft → human edit/review → exact mapping selection → StudySpec/support validation`

It is deliberately separate from the existing full synthetic Workbench demo, which also demonstrates a synthetic approval/job/QC path. This version stops before approval, job submission, or simulation so it cannot look like an actual experiment was run.

## What the result means

- The protocol, evidence corpus, target, neuron/readout IDs, mapping review metadata, and draft are invented software fixtures.
- The retriever is a tiny deterministic token-overlap fixture. It does not use the production BM25 corpus loader and does not access the internet.
- The “AI draft” is a deterministic stub envelope, **not Gemini and not an LLM output**. It demonstrates how the real draft contract flows through review and mapping gates.
- The reviewer ID in the form is self-reported by whoever runs the local demo. It is not independent review, scientific approval, or owner approval of the research mapping.
- StudySpec support validation checks only this fixture capability and exact fixture mapping. `READY_FOR_COMPUTATIONAL_REVIEW` is not biological validity and does not approve a run.
- The code does not call a provider or simulator and does not access development benchmark outputs, held-out data, or sealed outcomes.

## Prepare the session

```powershell
Set-Location 'E:\research-\.workbench\ai-v2-dev'
$taskPython = 'E:\research-\.venvs\ai-v2-staging-312\Scripts\python.exe'
& $taskPython scripts/run_ai_v2_review_gated_demo.py --prepare
```

The command prints a unique local session path under `.workbench/ai-v2-e2e-demo/`. Open its `README.md` and inspect:

- `protocol_input.json` — synthetic protocol;
- `retrieved_evidence.json` — fixture retrieval trace;
- `ai_draft_fixture.json` — draft contract and provenance;
- `mapping_options.json` — the exact selectable fixture mapping;
- `human_review_form.json` — the one file you edit.

The prepared corpus, evidence, draft, mapping registry, and options are hash-pinned. Do not change them; if you want a new fixture session, create one with `--prepare` again.

## Human review/edit step

Open `human_review_form.json` in an editor. Fill it with your own decision:

- `reviewer_id`: a local ID you identify as the person operating this demo;
- `decision`: set to `ACCEPT_FOR_SYNTHETIC_DEMO_ONLY` only if you want to proceed with this software fixture;
- `rationale`: briefly say why the demo is acceptable for demonstrating software flow;
- `study_edits`: read the generated text and revise the name, hypothesis, or falsifiable prediction in your own words. Keep `assay` as `synthetic_demo` and `primary_metric` as `metrics.response` for the fixture capability;
- `mapping_choice`: copy the exact `mapping_id`, `version`, and `record_hash` from `mapping_options.json`;
- `acknowledgements`: set all three values to `true` only after acknowledging the fixture-only/non-biological scope.

These edits are a local demo interaction, not an approval to send real protocol text to Gemini or a scientific decision about any biological mapping.

## Finalize and inspect the StudySpec

Use the exact path printed by `--prepare`:

```powershell
$taskSession = '<paste the printed session directory here>'
& $taskPython scripts/run_ai_v2_review_gated_demo.py --finalize --session-dir $taskSession
Get-Content -Encoding UTF8 (Join-Path $taskSession 'finalized/demo_summary.json')
Get-Content -Encoding UTF8 (Join-Path $taskSession 'finalized/validated_study_spec.json')
Get-Content -Encoding UTF8 (Join-Path $taskSession 'finalized/support_assessment.json')
```

Expected stop state: `SYNTHETIC_STUDYSPEC_VALIDATED_AWAITING_RESEARCHER_APPROVAL`, with `human_approval=false`, `job_submitted=false`, `simulation_run=false`, and `HELDOUT_STATUS=LOCKED_NOT_RUN`. The session cannot be finalized twice; use a new session rather than overwriting artifacts.

The generated `sha256.json` covers stable files, including the checkpointed local Workbench state database; transient SQLite `-wal`/`-shm` sidecars are excluded because SQLite may remove them when the process exits.

## Not measured by this demo

This is not the three-arm comparison (manual template / LLM without retrieval / LLM+RAG), not an AI quality evaluation, not a validation of the production retriever/provider, and not a biological validation. The three-arm harness is documented separately in [protocol comparison](protocol_comparison.md). Real metrics require the reviewed/frozen development inputs, Gemini data-sharing decision and actual outputs; none are manufactured by this fixture.
