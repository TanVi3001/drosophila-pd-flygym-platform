# AI V2 A02 — Evidence-grounded StudySpec draft

## Scope

A02 adds `POST /v2/study-spec/draft`. Software assembles a fixed rule prompt,
the research question, and the A01 retrieved excerpts. The configured pretrained
model may propose only a small draft field set; it cannot make an executable
Workbench `StudySpec`, create a mapping, choose neuron IDs or interventions,
set simulation parameters, approve a study, or create/run jobs.

`HELDOUT_STATUS = LOCKED_NOT_RUN`

The older `/v2/protocol-intake/draft` remains a separate legacy extraction
endpoint with no retrieval. Its output reports
`retrieval_mode=NOT_USED_BY_LEGACY_INTAKE` and should not be represented as RAG.

## Prompt and data boundary

- `build_study_spec_prompts` creates a versioned system prompt and a JSON user
  payload. Rules, user question, and evidence are separate fields.
- Retrieved paper content is explicitly treated as untrusted quoted data. The
  provider has no tools or code-execution interface.
- The prompt requests only title, hypothesis, falsifiable prediction, assay,
  primary metric, primary metric unit, supported context, field-level evidence
  IDs, and uncertainties.
- Model/provider is opt-in and separate from V1 and the older V2 intake provider.
  No fine-tuning is performed. No live model request is part of the test suite.

The artifact uses schema `workbench-v2-study-spec-draft-2` and contains the
question hash, prompt version/hash, provider ID,
corpus hash, retrieval algorithm, retrieved evidence IDs, validated citations,
proposed fields, a separate `uncertainties` list, missing fields, checks and an
explicit non-executable status. Uncertainties are not executable StudySpec
fields and are excluded from the A04 structured-field accuracy denominator.
It does not store the raw question, prompt, model response, or retrieved chunk
text. The retrieval and draft event share the privacy-minimized JSONL audit log.

## Output and checks

Draft outputs are written outside the repository under
`<runtime-root>/ai_v2/outputs/drafts/` and are immutable new files. The
application performs these checks before an artifact is accepted:

- unknown or forbidden model keys fail closed; mapping IDs, neuron IDs,
  interventions, backend/configuration, approval and job/run fields are rejected;
- likely mapping/neuron identifier strings in generated prose are also rejected
  (conservative patterns for FlyWire/root IDs and common FlyBase IDs; this is a
  guardrail, not a semantic biology validator);
- every field citation must point to an evidence chunk actually retrieved for
  this request; output citations are rendered from corpus metadata rather than
  free-form model citations;
- an uncited scientific field is withheld from proposed fields and listed as
  missing; a valid chunk reference proves traceability, not semantic entailment;
- assay identifiers are checked against configured backend capabilities, which
  is only a software compatibility check, not proof of biological comparability;
- an optional researcher-supplied `mapping_target` is resolved by exact
  normalized target-name equality against existing `COMPUTATIONALLY_REVIEWED`
  or `BIOLOGY_REVIEWED` records. There is no alias, fuzzy, or model-based match.
  Only candidate records and their existing provenance are returned; a human
  must select/review them. Results appear only in a separate `mapping_lookup`
  section and are not inserted into proposed StudySpec fields; resolver-returned
  mapping records/IDs are not sent to the LLM;
- obvious Hz naming inconsistencies (`mn9_rate` or a metric ending `_hz`) are
  flagged. Other metrics return a human-review status because no complete,
  approved metric-unit registry exists. Units are not silently corrected;
- missing A01 evidence skips the provider call entirely and returns a draft
  with missing fields. Missing provider configuration blocks generation.

Every result is `DRAFT_REQUIRES_RESEARCHER_REVIEW` (or
`NO_APPROVED_EVIDENCE`), with `approved=false`, `study_created=false`,
`mapping_created=false`, `job_created=false`, `graph_used=false`, and
`simulation_started=false`. Required pre-execution items include reviewed
mapping, intervention/parameters, control, backend compatibility, run plan and
human approval bound to the final configuration.

The [A07 reviewed-study handoff](ai_v2_a07_reviewed_study_handoff.md) now provides
an explicit local API for a researcher to review the saved draft checksum,
submit a complete final design and create a support-gated study. Promotion is
separate from run approval and leaves the original draft unchanged.

## Configure the optional provider

Only after an approved A01 corpus is available, explicitly opt into V2 and set
the independent StudySpec provider settings:

```powershell
$env:FLY_WORKBENCH_V2_ENABLED = "1"
$env:FLY_WORKBENCH_V2_RUNTIME_ROOT = "E:\fly-research-runtime"
$env:FLY_WORKBENCH_V2_CORPUS_PATH = "E:\fly-research-runtime\ai_v2\corpus\corpus.json"
$env:FLY_WORKBENCH_V2_CORPUS_SHA256 = "<SHA-256 of exact corpus.json bytes>"
$env:FLY_WORKBENCH_V2_STUDY_SPEC_BASE_URL = "https://YOUR-APPROVED-ENDPOINT/v1"
$env:FLY_WORKBENCH_V2_STUDY_SPEC_MODEL = "YOUR-PRETRAINED-MODEL"
$env:FLY_WORKBENCH_V2_STUDY_SPEC_API_KEY_ENV = "YOUR_SECRET_ENV_NAME"
# Put the secret itself in the environment variable named above.
```

These settings cause no model request until `/v2/study-spec/draft` is called.
Review the provider's retention/training policy before sending research
questions or unpublished protocols. If there is no provider but the retriever
returns no evidence, the API still reports missing evidence without calling an
LLM; if evidence is found, generation is unavailable until a provider is set.

Example request:

```json
{"question":"Draft a study specification for this assay question.","top_k":5}
```

An optional exact mapping lookup can be requested separately:

```json
{"question":"Draft a study specification for this assay question.","mapping_target":"exact reviewed biological target name","top_k":5}
```

## Verification and limits

Fixture tests cover prompt-injection containment, no-evidence/no-provider
behavior, citation ID validation, missing citations, unsupported fields,
forbidden mapping/backend outputs, assay capability mismatches, obvious unit
mismatches, external artifact isolation and privacy-minimized audit records.
They verify software contracts, not answer quality, biological correctness,
researcher utility, provider privacy, or wet-lab relevance. A human-annotated
draft-quality/safety evaluation and a real provider run remain unperformed.
