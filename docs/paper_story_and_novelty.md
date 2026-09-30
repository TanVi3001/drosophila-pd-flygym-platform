# Paper story and novelty boundary

**Working title:** *An evidence-aware and reproducible workbench for prioritizing connectome-based computational experiments*

## Research problem and paper claim

Connectome data and neural simulators do not by themselves tell a researcher whether a proposed question is supported by the available evidence, whether the model can represent its assay, what exact computational study should be run, or how to distinguish a failed run from a negative-looking model output. Fly Research Workbench is a software/methods layer between a biological question and a human decision: it checks evidence and model capability, records an explicit StudySpec, runs only a declared computational study, preserves provenance and QC states, and presents a bounded candidate ranking for human review.

The strongest claim currently supported is that the repository implements a scope-bounded, auditable workflow and a frozen retrospective development benchmark whose score construction is label-blind, with owner-side computational reproduction evidence. Development data show a rewire-based ranking above a seeded random reference, but do **not** show an advantage of full Workbench over effect-only scoring. Independent second-operator reproduction and final held-out evaluation are pending. This is a methods/software claim, not a claim that the system accurately models Parkinson disease, predicts whole-animal behavior, replaces wet-lab work, or identifies successful biological interventions.

## Contribution status against repository evidence

| Candidate contribution | Classification | Evidence and boundary |
|---|---|---|
| Evidence-aware gating | SUPPORTING | Mapping/reviewer fields and label-blind score lock exist; all 106 benchmark cases pass, so incremental utility is not identified here. |
| Capability-constrained simulation | SUPPORTING | Research-study path checks declared assay/intervention/readout/context; not every legacy/demo path is globally gated. |
| Explicit abstention / NOT_SUPPORTED / REQUIRES_REVIEW | CORE | Unsupported, pending, unassessable and failed states are represented rather than silently converted into negative outcomes. |
| StudySpec as experiment contract | CORE | Study configuration and candidate definitions are hash-bound and approval is tied to the assessed configuration. |
| Provenance and artifact integrity | CORE | Manifests capture source, environment, input/output digests and run state; integrity verification has dedicated tests. |
| Reproducible success/failure execution | CORE | Owner subset reports both a completed case and a controlled failure/QC case; remains owner-assisted, not independent. |
| Frozen benchmark evaluation | SUPPORTING | 106-row registry and 74/32 split are declared; held-out remains locked and comparator choice still needs owner approval. |
| Candidate prioritization / ranking | SUPPORTING | Ranking and budget-selection components exist; the new workflow's practical benefit has not been prospectively validated. |
| Cross-machine / cross-operator reproduction support | SUPPORTING | Portable handoff and verifier exist; Tuấn's independent run is still pending. |

These classifications describe implemented software and evidence status, not biological validity. See [novelty matrix](novelty_matrix.md) and [scientific case review status](scientific_case_review_status.md).

## Position relative to prior work

FlyWire supplies a whole-brain wiring diagram and annotation resources; Shiu et al. provide the source computational brain model and its sensorimotor analyses; NeuroMechFly v2 targets embodied sensorimotor control. Reproducible simulation/provenance workflows also predate this project (for example, Lancet and AiiDA). The defensible distinction to investigate is the *combined operational contract* that refuses unsupported scopes, binds approval to a StudySpec, carries explicit failure/unassessable states, and tracks provenance into a human-facing prioritization step. These ingredients are not individually claimed as new. A broader literature audit of neuroscience virtual screening and candidate prioritization remains pending; novelty risk is therefore **HIGH** until direct overlap and the value beyond integration are externally reviewed.

## Claim ladder

1. **Now supportable:** software contracts, bounded computational workflow, frozen development findings, and owner-side reproduction—reported separately.
2. **After second operator:** independent computational reproduction, only if Tuấn (or another genuinely independent operator) runs the declared clean setup and the verifier passes.
3. **After owner authorization and one-time held-out run:** retrospective ranking generalization on the declared held-out subset, limited to the published label and approved comparator set.
4. **Not established by this project state:** causal biological accuracy, in-vivo behavior prediction, Parkinson model validity, wet-lab utility, or clinical relevance.

## Selected primary literature

- Dorkenwald et al. (2024), “Neuronal wiring diagram of an adult brain,” *Nature*, DOI [10.1038/s41586-024-07558-y](https://doi.org/10.1038/s41586-024-07558-y).
- Schlegel et al. (2024), “Whole-brain annotation and multi-connectome cell typing of Drosophila,” *Nature*, DOI [10.1038/s41586-024-07686-5](https://doi.org/10.1038/s41586-024-07686-5).
- Shiu et al. (2024), “A Drosophila computational brain model reveals sensorimotor processing,” *Nature*, DOI [10.1038/s41586-024-07763-9](https://doi.org/10.1038/s41586-024-07763-9).
- Wang-Chen et al. (2024), “NeuroMechFly v2: simulating embodied sensorimotor control in adult Drosophila,” *Nature Methods*, DOI [10.1038/s41592-024-02497-y](https://doi.org/10.1038/s41592-024-02497-y).
- McDougal et al. (2016), “Reproducibility in Computational Neuroscience Models and Simulations,” *IEEE TBME*, DOI [10.1109/TBME.2016.2539602](https://doi.org/10.1109/TBME.2016.2539602).
- Stevens et al. (2013), “An automated and reproducible workflow for running and analyzing neural simulations using Lancet and IPython Notebook,” *Frontiers in Neuroinformatics*, DOI [10.3389/fninf.2013.00044](https://doi.org/10.3389/fninf.2013.00044).
- Huber et al. (2020), “AiiDA 1.0, a scalable computational infrastructure for automated reproducible workflows and data provenance,” *Scientific Data*, DOI [10.1038/s41597-020-00638-4](https://doi.org/10.1038/s41597-020-00638-4).

This is a targeted comparison, not a systematic review. Direct comparison against neuroscience prioritization/virtual-screening systems is `EXTERNAL_LITERATURE_CHECK_PENDING`.
