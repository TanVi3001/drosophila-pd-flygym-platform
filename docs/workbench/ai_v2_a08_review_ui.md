# AI V2 A08 — Local human-review interface

**Status:** `IMPLEMENTED_LOCAL_UI; SYNTHETIC_API_PATH_TESTED`

No formal A08 specification was present in the checked-out roadmap. This task
is scoped as the operator-facing UI gap left by A07: expose the already gated
draft/review/promotion/workflow APIs in the existing local Workbench page. It
does not add a new model capability or change scientific scoring.

## User-visible flow

1. Enter a development question and request an A01/A02 draft. This uses only the
   approved checksum-verified corpus configured at server startup. The model
   result remains a saved, non-executable draft.
2. Load and inspect the saved draft snapshot and checksum.
3. The researcher writes/edits the complete final StudySpec in the review form,
   verifies the evidence and mapping against the existing reviewed registry,
   supplies a reviewer attestation, and promotes the reviewed design.
4. Promotion creates a support-gated study only. It does not create jobs or run
   simulation. A selected scope is limited in the UI to `development` or
   `synthetic_fixture`; there is no held-out option.
5. A separate control group exposes support assessment, human run approval,
   explicit seed/job submission, explicit run, status, and provenance/QC report.
   The AI provider is not called by any of these execution actions.

The UI uses text-only rendering for returned JSON. It does not auto-copy model
fields into an executable design, select/create mappings, decide whether a
mapping is scientifically correct, or grant run approval on the user's behalf.
The backend remains the authority for checksum, mapping, capability, control,
unit, support, approval, and evaluation-scope validation.

## Local use and safety

The existing Workbench page at `/` contains the A08 section. Start it using the
normal local server instructions in the project README, with V2 explicitly
enabled and a repository-external runtime root. To generate a real draft, the
operator must additionally configure the approved evidence corpus and the
group-authorized provider/model. Never paste unpublished material into a
provider until the team approves its privacy and retention terms.

The local server defaults to `127.0.0.1`. It has no authentication, and the
reviewer name is an attestation string rather than verified identity. Do not
expose it to a network. A browser/API caller can still attempt route actions;
server-side gates prevent promotion or run without the required contracts, but
identity/role security is a deployment prerequisite.

The API integration checks use the synthetic A07 fixture: no external model is
called and its selected numerical readouts are not fly/neuroscience results.
`HELDOUT_STATUS = LOCKED_NOT_RUN`.

**Verification boundary:** The workflow-run buttons do not call a model provider;
the end-to-end fixture uses synthetic values only.
