# New Workbench experiments

This release adds two runnable computational experiments and two evidence-bound
cases. They extend the Workbench protocol without claiming new wet-lab data.

## E1 — input-intensity sensitivity

`configs/workbench/sensory_mn9_intensity.yaml` compares the same reviewed sugar
input set at 50, 150, and 200 Hz against a paired no-input condition. Each
condition uses the same seed set. Ten seeds are for screening; up to three
selected conditions can use 30 fresh confirmation seeds.

The frequency is a Poisson input parameter of the LIF model. It is not a
sucrose concentration, laser power, or biological dose.

## E2 — temporal stimulus sensitivity

`configs/workbench/sensory_mn9_temporal.yaml` compares sustained sugar input with
two explicit 250 ms pulses. The runner records the schedule in the condition
config and uses Brian2 `TimedArray` inputs. Overlapping windows are permitted
for coactivation only when they do not repeat an input ID; repeated IDs in
overlapping windows are rejected as ambiguous.

## E3 — cross-circuit public-data extension

Sapkal et al. 2024 is registered as a possible P9/BPN/FG/BB/BRK extension. It
is not runnable yet because the source readouts and neuron namespace have not
been mapped and reviewed against the local dataset. The registry intentionally
keeps this case blocked rather than inventing IDs.

## E4 — out-of-scope abstention case

Wang et al. 2025 is used to test whether the Workbench abstains when a public
result depends on sex, mating experience, dopamine state, and peripheral Gr5a
recordings. It must not enter the MN9 ranking.

All four cases remain computational/public-data evidence. None is a substitute
for a prospective fly experiment or an independent biological review.

## Execution record

On 2026-09-16, E1 screening completed 40/40 jobs and E2 screening completed
30/30 jobs from the YAML study configurations. E1 produced 30 paired candidate
observations across ten seeds; E2 produced ten paired observations for each of
the sustained and pulsed conditions. Both reports retain bootstrap intervals
and direction stability under the declared computational policy.

E2 initially failed on a Brian2 indexing assumption for a non-contiguous set of
stimulus targets. The failure artifact was preserved, the runner was corrected,
and resume completed the pending and failed jobs. This is a software QC event
that should be reported in a methods supplement; it must not be counted as a
negative biological observation.
