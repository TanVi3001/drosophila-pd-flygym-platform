# Evidence gated research and candidate selection

This workflow adds an explicit support check before a research study can run or
produce a priority list. It keeps four questions separate:

1. Does the declared backend implement the assay and intervention?
2. Is each target-to-model mapping traceable, versioned, and reviewed?
3. Do the declared assay context and mapping context agree?
4. Which supported candidates have sufficiently stable paired simulation
   results to fit the declared candidate budget?

Passing these checks supports a computational run or computational
prioritization. It does not establish biological validity or replace wet-lab
validation.

## Optional protocol intake

The intake provider is disabled by default. Configure an OpenAI-compatible chat
completions endpoint only when protocol text may be sent to that service:

```powershell
$env:PYTHONPATH = "src"
$env:WORKBENCH_LLM_KEY = "..."
python scripts/workbench.py `
  --intake-base-url https://provider.example/v1 `
  --intake-model MODEL_NAME `
  --intake-api-key-env WORKBENCH_LLM_KEY `
  protocol-intake --file protocol.txt --source-uri https://doi.org/...
```

The result is saved under `.workbench/artifacts/intake_drafts/` with the
protocol SHA-256, source URI, provider/model, prompt version, proposed fields,
and missing fields. The schema accepts only draft-level protocol fields.
Mapping IDs, neuron IDs, interventions, backends, simulation parameters,
approvals, and job actions are discarded. Intake never creates a `StudySpec`
or a mapping record; a researcher must review the draft and prepare those
records separately. If no endpoint and model are configured, normal Workbench
commands do not call an AI provider.

The local server accepts the same `--intake-base-url`, `--intake-model`, and
`--intake-api-key-env` options. Protocol text is sent only when the user
explicitly invokes the intake endpoint.

## Public mapping registry

Regenerate the Shiu Table 3 traceability registry from the checked-out public
model source and its FlyWire-630 inventory:

```powershell
python scripts/export_shiu_mapping_registry.py
```

The generated `configs/workbench/shiu_table3_neuron_mapping_v1.json` currently
contains 106 cases: 105 exact name matches, one case-fold alias, no missing
names, and no IDs outside the declared inventory. All records remain
`PENDING_SCIENTIFIC_REVIEW`. This is source traceability for an upstream model
input set; it is not evidence of driver-line specificity or experimental
equivalence. The alias is kept visible and requires human review.

Import only non-empty exact and alias records. Missing and invalid ID sets are
skipped:

```powershell
python scripts/workbench.py `
  --db .workbench/workbench.sqlite3 `
  --artifacts .workbench/artifacts `
  mapping-import --file configs/workbench/shiu_table3_neuron_mapping_v1.json
python scripts/workbench.py --db .workbench/workbench.sqlite3 mapping-list
```

Mapping IDs are immutable. A reviewed revision gets a new mapping ID and
version; retain its source citations and add the human reviewer and review
timestamp. Use `mapping-register --file reviewed_mapping.json` for a manually
reviewed record. `COMPUTATIONALLY_REVIEWED` means the computational mapping was
reviewed; use `BIOLOGY_REVIEWED` only after an appropriately qualified review.
Neither status is assigned by the AI intake flow.

## Support gated study lifecycle

Prepare a researcher-authored StudySpec JSON containing the hypothesis,
falsifiable prediction, assay, primary metric, explicit candidate/control
list, backend, and run plan. Each non-control candidate must reference a
registered `mapping_id` in its metadata. Set `metadata.dataset_id` and
`metadata.context` when those are part of the question being asked. Set the
ID namespace in study metadata or backend requirements, and keep it consistent
with the dataset and mapping records.

```powershell
python scripts/workbench.py `
  --db .workbench/workbench.sqlite3 `
  --artifacts .workbench/artifacts `
  create-research-study --file research_study.json
```

Creation immediately assesses capability, mapping review, dataset, namespace,
and requested context, and runs the backend's non-simulating configuration
preflight when every mapping is eligible. The command returns both the study
and assessment. If mappings are reviewed later, rerun `assess-support` to
refresh that assessment.

```powershell
python scripts/workbench.py --db .workbench/workbench.sqlite3 assess-support STUDY_ID
python scripts/workbench.py --db .workbench/workbench.sqlite3 approve-support STUDY_ID --reviewer "Reviewer name"
python scripts/workbench.py --db .workbench/workbench.sqlite3 screen-study STUDY_ID --seeds screening_seeds.json
python scripts/workbench.py --db .workbench/workbench.sqlite3 run-screening STUDY_ID
```

`assess-support` reports missing mapping records, pending/rejected review,
backend/assay/intervention mismatches, dataset or namespace mismatches,
missing backend files/readouts, IDs absent from the pinned completeness
inventory, and context mismatches. It does not run a simulation. A pending or
out-of-scope candidate prevents the study from being approved to run. Approval
is bound to the study configuration and assessment hash; reassessing
invalidates the previous approval.

Screening seed count must match the repetition count declared in the frozen
study. Submission creates pending jobs; `run-screening` executes only the
submitted screening set after the support approval is current.

For a support gated job, the candidate ID is mandatory and must exist in the
frozen StudySpec. The Workbench materializes the reviewed mapping's target IDs
into the intervention input, records the mapping ID/hash, namespace, and
dataset in the job config, and rejects a conflicting ID list or backend
override. This binds the assessment to what the backend receives. Mapping
materialization is currently defined for `activation`, `silence`, and
`outgoing_synapse_block`; other intervention types need an explicit reviewed
mapping contract before they can use this workflow.

## Candidate budget and uncertainty

After every declared candidate has complete paired observations against the
declared control, create `selection_policy.json`, for example:

```json
{
  "assay": "sensory_mn9",
  "primary_metric": "mn9_rate",
  "budget_k": 3,
  "control_candidate_id": "control",
  "minimum_pairs": 3,
  "bootstrap_samples": 1000,
  "minimum_direction_stability": 0.8
}
```

Then run:

```powershell
python scripts/workbench.py `
  --db .workbench/workbench.sqlite3 `
  --artifacts .workbench/artifacts `
  select-study STUDY_ID --policy selection_policy.json
```

Evidence, review state, and context are eligibility gates. Among eligible
candidates, the rule ranks the lower confidence bound in the predeclared
direction, requires the configured number of paired computational seeds and
direction stability, and selects at most `budget_k` candidate IDs. The report
records exclusions, uncertainty, support hash, source job manifests, policy
hash, and unspent budget. Missing or QC-failed results are not converted to
negative biological evidence. Controls do not consume candidate budget.

## Retrospective benchmark and research claims

The existing benchmark utilities support frozen development/held-out splits,
random, heuristic, effect-only, original-model, and degree-preserving-rewire
comparators. The public benchmark runner deliberately emits `BLOCKED` until a
real rewire score map on the same declared cases is supplied:

```powershell
python scripts/run_public_benchmark_evaluation.py --output .workbench/public_comparison.json
```

Published aggregate response-presence labels are a retrospective target, not
biological positive/negative labels. Do not tune on the held-out split. A
`READY_FOR_REVIEW` computational comparison still requires scientific review
and does not establish prospective utility. Independent second-operator
reproduction and wet-lab validation remain separate evidence gates.
