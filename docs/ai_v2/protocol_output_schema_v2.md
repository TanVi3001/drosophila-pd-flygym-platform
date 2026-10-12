# Protocol intake output contract — v2 proposal

Status: implementation proposal; not yet frozen or provider-tested.

## Why this version exists

The 2026-10-09 owner-reviewed synthetic comparison returned parseable JSON, but
the raw responses did not match the Workbench intake contract in 0/11 protocol
cases. The post-sanitization drafts matched in 11/11 cases because sanitization
discarded or repaired malformed optional fields. The raw-schema metric is the
right signal for this issue; the evaluator must remain strict and must not
count repaired output as raw-valid.

## v2 changes

- Prompt ID: `protocol-intake-output-v2`.
- Request format: OpenAI-compatible `json_schema`, using the same schema builder
  as the request preview. This replaces syntax-only `json_object` mode.
- Root keys are allow-listed; additional keys are disallowed.
- The four required protocol fields remain `hypothesis`,
  `falsifiable_prediction`, `assay`, and `primary_metric`. If a required value
  is unsupported, omit its property and name it in `missing_fields`.
- `missing_fields` may contain only those four required-field names; optional
  fields must never appear there.
- `context`, when present, is a non-empty object of approved string-valued keys,
  never a free-text string. Omit it when no explicit key/value pair is
  supported. Do not turn a synthetic-boundary note into context.
- Suggestion and citation fields are arrays, not `null`; use empty arrays when
  there are no supported suggestions or evidence citations.
- Citations in the evidence-conditioned arm must copy only `source_id` and
  `chunk_id` from retrieved excerpts. The no-retrieval arm must return no
  citations.
- Sanitization, raw-schema evaluation, gold values, retrieval ranking, and
  biological/mapping decisions are unchanged.

## Re-run conditions and limits

This is a new prompt/implementation version. The existing v1 frozen package
pins the previous source hashes and must not be edited or used to bypass its
integrity check. A new review package and freeze are required before another
provider run. Its request preview is local-only and does not call Gemini.

The next run should use the same approved synthetic inputs and Gemini model,
one run per arm, with the manual baseline left `PENDING`/`NOT_MEASURED` unless
the owner supplies a real manual worksheet. Report case-level raw schema
status, processed schema status, errors, and the unchanged task metrics. A
schema-valid output is not evidence of correct fields, supported claims,
biological validity, or independent review.

Google documents structured output for Gemini through its OpenAI-compatible
Chat Completions interface and recommends application-side validation because
schema compliance does not establish semantic correctness:

- https://ai.google.dev/gemini-api/docs/openai#structured-output
- https://ai.google.dev/gemini-api/docs/structured-output

The actual request/response behavior for the selected model and account tier
still needs a new authorized run; no provider call was made while preparing
this proposal.
