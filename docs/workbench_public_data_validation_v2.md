# Public-data validation profile v2

Status: computationally implemented on 2026-09-17; domain-scientist review and
independent human operator remain pending.

## Context of use

The Workbench is evaluated as a scope-bounded computational prioritization
procedure for supported Drosophila assays. It is not evaluated as a disease
simulator, a substitute for a live fly, or a causal inference engine.

The primary paper direction is methods plus benchmark. The Parkinson-related
proxy is a limitation audit. The current LIF substrate does not contain a
validated dopamine-modulation dynamic, so structural perturbation outputs must
not be called dopaminergic disease effects.

## Frozen retrospective benchmark

`configs/workbench/shiu_public_benchmark_v2.json` is generated from the local
SHA-256-pinned Shiu et al. supplementary workbook, Table 3. It contains 106
source rows: 14 response-present and 92 response-absent according to the
published aggregate activation-rate field. The response-present label is not a
significance test and the response-absent label is not proof of biological
absence.

The split is 74 development and 32 held-out cases, stratified by the declared
source-row unit with seed `17092026`. No driver line, frequency, hemisphere or
model-sensitivity column is expanded into an independent biological case.
Because the published model and experiment are part of the same upstream
study, this is retrospective evaluation of the Workbench procedure and not an
upstream-independent validation set.

The registry is computationally frozen with a source checksum and protocol
hash. `COMPUTATIONAL_AUDIT_ONLY_HUMAN_REVIEW_PENDING` is intentional: a passing
registry validator certifies row/checksum/split integrity only.

## Evaluation policy

Calibration uses development cases only. The primary comparative metric is
precision@5 on the common assessable held-out denominator. Secondary metrics
are average precision, precision@10, recall, false negatives, class balance,
and assessable coverage. The evaluator reports 10,000 case-level bootstrap
resamples for ranking metrics; these are not fly-level or model-mechanism
uncertainty intervals. If the common denominator lacks a class or is too
small, the corresponding estimate is reported as insufficient rather than
interpreted as biological evidence.

The required comparison systems are:

1. original-model reproduction;
2. Workbench score;
3. effect-only score;
4. direct-connectivity heuristic;
5. random and majority-class references; and
6. degree-preserving directed rewiring.

The rewiring null preserves in-degree, out-degree, per-source outgoing weight
multisets and the declared edge stratum. A partial null graph is a failed
replicate, not an imputable score. The null graph tests structural specificity;
it does not represent an equally plausible biological connectome.

The annotation audit currently finds 0/106 exact unique mappings from the
Table 3 names to the downloaded FlyWire annotation release. This remains a
blocker: the public annotation release and the Shiu model's FlyWire 630
snapshot are not interchangeable, and name-prefix guesses would create false
structural evidence. The audit artifact is
`results/workbench/shiu_benchmark_v2_annotation_mapping_audit.json`.

## Simulation campaigns

Screening uses 10 computational seeds. Confirmation uses 30 fresh seeds for
the predeclared top three candidates. Seeds are not fly counts. Sensitivity
varies synaptic strength by 0.7/1.0/1.3 and inhibitory strength by
0.5/1.0/1.5 without reading held-out labels.

E2-v2 adds a matched-input temporal protocol: sustained 75 Hz for 1 s versus
two 150 Hz pulses totaling 0.5 s, plus no-input and sustained 150 Hz controls.
The declared rate-time product is matched; actual spike counts are not assumed
to be equal.

The completed screening artifact is
`results/workbench/e2_matched_input_screening_20260917/campaign_manifest.json`
(40/40 jobs, 10 paired seeds per condition). The primary-contrast audit is
`results/workbench/e2_matched_input_screening_20260917/ranking_primary_contrast_10000_bootstrap.json`:
the pulsed-versus-sustained-low contrast has mean delta `-9.4 Hz`, bootstrap
95% interval `[-14.6, -3.5]`, and direction stability `0.7`, below the
predeclared `0.8` ranking threshold. It is therefore retained as exploratory
and not promoted to a ranked priority. This report is derived from completed
artifacts after correcting the runner's control-policy handling; it does not
represent a new simulation campaign.

## Reproduction and AI disclosure

Clean execution by the project owner, a script, or AI is recorded as
`same_operator`, `automated`, or `computational_public_data`. The verifier no
longer labels a run `second_operator` unless that role is explicitly supplied.
Only a genuinely separate human operator can satisfy the independent-operator
claim, and the verifier does not create a scientific signature on that
person's behalf.

AI may inspect public sources, check mappings, generate audit tables and flag
overclaims. It cannot approve driver specificity, stock availability, in-vivo
interpretation or wet-lab feasibility. AI model/version/date and source URLs
must be recorded in the evidence bundle; the project author remains responsible
for every claim.

## Allowed claim after this profile

"A reproducible, scope-bounded computational prioritization procedure was
evaluated against a checksum-pinned retrospective public-data benchmark and
declared structural/effect-only baselines."

The following remain disallowed without additional evidence: disease
simulation, equivalence to a real fly, causal MN9 inference, gene-specific
validation, demonstrated wet-lab cost savings, universal Drosophila validity,
or a claim that the benchmark is independently validated by a second human.
