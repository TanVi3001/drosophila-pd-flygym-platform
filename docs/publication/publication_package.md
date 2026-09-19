# Publication Package

This package inventory identifies the repository artifacts supporting public
scientific dissemination of version 1.0.0. It does not modify or reinterpret
scientific results.

## Manuscript

- Canonical manuscript source: `docs/report/final_report.md`
- Report methods: `docs/report/methods.md`
- Report results: `docs/report/results.md`
- Report discussion: `docs/report/discussion.md`
- Report limitations: `docs/report/limitations.md`
- Reproducibility statement: `docs/report/reproducibility.md`
- Evidence traceability: `docs/report/evidence_traceability.md`
- Figure captions: `docs/report/figure_captions.md`

## Evidence

- Block 8.12 audit: `results/baseline/block_8_12_audit.json`
- Milestone 8B materialization:
  `results/baseline/milestone_8b_materialization.json`
- Milestone C unperturbed baseline: `results/baseline/healthy_baseline.json`
- Milestone D identity perturbation: `results/perturbations/identity.json`
- Milestone D action-scale perturbation:
  `results/perturbations/action_scale_080.json`
- Milestone E1 parameter response: `results/sweeps/milestone_e1.json`
- Milestone E2 combined phenotype:
  `results/sweeps/milestone_e2_combined.json`
- Milestone E3 robustness:
  `results/validation/milestone_e3_candidate_robustness.json`
- Milestone E4 concordance:
  `results/validation/milestone_e4_concordance.json`
- Milestone E5 computational reversibility:
  `results/validation/milestone_e5_computational_rescue.json`
- Milestone E6 synthesis: `results/analysis/milestone_e6_synthesis.json`

## Figures

- `results/analysis/figures/e1_parameter_response.png`
- `results/analysis/figures/e2_condition_comparison.png`
- `results/analysis/figures/e3_paired_seed_robustness.png`
- `results/analysis/figures/e5_computational_reversibility.png`

## Tables

- `results/analysis/tables/evidence_manifest.csv`
- `results/analysis/tables/e1_parameter_response.csv`
- `results/analysis/tables/e2_condition_summary.csv`
- `results/analysis/tables/e3_seed_summary.csv`
- `results/analysis/tables/e5_reversibility_summary.csv`

## Report Artifacts

- `dist/Drosophila_PD_FlyGym_Final_Report.docx`
- `dist/Drosophila_PD_FlyGym_Final_Report.pdf`
- `dist/final_report_manifest.json`

## Release Artifacts

- Release notes: `docs/release/v1.0.0.md`
- Release tag: `v1.0.0`
- Canonical branch: `main`

## Citation

- Citation metadata: `CITATION.cff`
- Citation guidance: `docs/citation.md`
- Repository URL: <https://github.com/tuanwannafly/drosophila-pd-flygym>
- Release URL:
  <https://github.com/tuanwannafly/drosophila-pd-flygym/releases/tag/v1.0.0>

No DOI, journal article, or external publication is declared in the repository
unless added after an actual archival or publication event.

## License

- License file: `LICENSE`
- License: MIT

## Scientific Boundary

The package supports a computational/phenomenological simulation framework.
It does not claim biological Parkinson's disease validation, dopamine
equivalence, disease-severity mapping, biological rescue, mechanistic
equivalence, or statistical significance.
