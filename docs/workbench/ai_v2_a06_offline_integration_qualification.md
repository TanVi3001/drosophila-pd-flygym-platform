# AI V2 A06 — Offline integration qualification

**Status:** `PASS_SYNTHETIC_OFFLINE_CONTRACTS`

## Why this step exists

No formal A06 specification was present in the checked-out repository or the
project roadmap. This scoped A06 is the next non-held-out engineering step:
exercise the real A01 retrieval, A02 draft validation, and A04 evaluator
together using synthetic fixtures, and verify the boundary that keeps a draft
from becoming an executable study. It does not claim a real AI-quality result.

## What is exercised

`tests/test_workbench_v2_offline_integration.py` performs one deterministic,
network-free path:

1. Write and checksum-load a synthetic approved-corpus fixture.
2. Retrieve evidence for an answerable fixture question.
3. Pass only retrieved excerpts to a deterministic fake generator and validate
   its A02 draft.
4. Confirm the draft remains unapproved and has created no study, mapping, job,
   graph access, or simulation.
5. Ask an unanswerable fixture question and verify A01/A02 abstain without
   calling the generator a second time.
6. Convert the two fixture outputs into the A04 contract and score them with
   `evaluation_split=synthetic_fixture`.

The fixture report checks retrieval recall/MRR, abstention, false acceptance,
the non-executable invariant, and input hashing. These values are software
contract checks on two handcrafted fixtures, **not model-performance metrics**
and not eligible as paper results.

## Integration issue found and fixed

The integrated path exposed a contract mismatch: A02 placed its free-text
`uncertainties` list inside `proposed_fields`, while A04 intentionally accepts
only the structured claim fields it can score. An actual A02 artifact could
therefore not be represented by the A04 draft contract without an ad hoc
transformation. A02 now emits `uncertainties` as a separate top-level field;
the artifact schema is versioned as `workbench-v2-study-spec-draft-2`;
it remains available to the researcher but is not counted as an executable
StudySpec field or in A04 structured-field accuracy. A regression assertion
protects the boundary. This is an output-schema correction; no score formula,
`k=5`, benchmark artifact, or scientific behavior was changed.

## Reproduce

From the platform repository root in PowerShell:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
python -m pytest -q -p no:cacheprovider `
  tests/test_workbench_v2_offline_integration.py `
  tests/test_workbench_v2_evidence.py `
  tests/test_workbench_v2_evaluation.py
```

The complete focused AI V2 regression command also includes
`test_workbench_v2_runtime.py` and `test_workbench_v2_automation.py`.

## What this does not establish

- No real provider/model was called; provider quality is unmeasured.
- The fixture is not the project's approved real evidence corpus or question set.
- This does not test Tuấn's external/production runtime or resolve its
  integration conflicts.
- It does not validate scientific mapping, biological correctness, wet-lab
  utility, or researcher benefit.
- It does not inspect, read, score, or run any held-out case.

```text
A06_OFFLINE_INTEGRATION = PASS_SYNTHETIC_CONTRACTS
A05_REAL_MODEL_EVALUATION = NOT_RUN
HELDOUT_STATUS = LOCKED_NOT_RUN
```
