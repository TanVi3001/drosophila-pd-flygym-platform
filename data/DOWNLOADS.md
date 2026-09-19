# Dataset download guide

These commands are intentionally explicit. They keep large or externally
licensed inputs out of the Git history while preserving a reproducible source
record. A fresh clone does not need any of these files for the default unit
tests.

## FlyWire annotations

Upstream repository: <https://github.com/flyconnectome/flywire_annotations>

The repository documents the systematic annotation dumps for the FlyWire
783 public release. The direct neuron-annotation file is:

<https://raw.githubusercontent.com/flyconnectome/flywire_annotations/main/supplemental_files/Supplemental_file1_neuron_annotations.tsv>

PowerShell:

```powershell
New-Item -ItemType Directory -Force data | Out-Null
Invoke-WebRequest `
  -Uri "https://raw.githubusercontent.com/flyconnectome/flywire_annotations/main/supplemental_files/Supplemental_file1_neuron_annotations.tsv" `
  -OutFile data\flywire_annotations.tsv
```

Check the expected project-copy size and SHA-256 in
[source_manifest.json](source_manifest.json). If the upstream file has
changed, keep the new checksum and retrieval date in a separate provenance
record rather than overwriting the old record silently.

## FlyWire v783 completeness and connectivity

The official FlyWire data portal is <https://codex.flywire.ai/> and the public
release guidance is <https://home.flywire.ai/guidelines>.

The official connectivity record is:

<https://zenodo.org/records/10676866>

It contains the v783 proofread connections and larger synapse tables. The
project's `2025_Connectivity_783.parquet` is an analysis-ready local artifact;
download the corresponding v783 connectivity product from Zenodo, convert it
to the project's schema, and verify the resulting file against the manifest.

The completeness table is obtained from the v783 FlyWire/Codex release. Use
the portal's `dataset=fafb` and `data_version=783` selection:

<https://codex.flywire.ai/api/download?dataset=fafb&data_version=783>

Save the project-format table as `data\2025_Completeness_783.csv`, then verify
it against `data/source_manifest.json`.

## Nature supplementary workbook

Article landing page:

<https://www.nature.com/articles/s41586-024-07763-9>

Direct supplementary workbook:

<https://media.springernature.com/original/springer-static/esm/art%3A10.1038%2Fs41586-024-07763-9/MediaObjects/41586_2024_7763_MOESM2_ESM.xlsx>

PowerShell:

```powershell
New-Item -ItemType Directory -Force data\benchmarks | Out-Null
Invoke-WebRequest `
  -Uri "https://media.springernature.com/original/springer-static/esm/art%3A10.1038%2Fs41586-024-07763-9/MediaObjects/41586_2024_7763_MOESM2_ESM.xlsx" `
  -OutFile data\benchmarks\41586_2024_7763_MOESM2_ESM.xlsx
```

The validation script is
`scripts/validate_shiu_benchmark_registry.py`. The benchmark remains a
computational source-integrity check and does not by itself establish a new
biological claim.

## Reproducibility rule

Do not add these files with `git add -f`. Use the manifest and this guide when
sharing a new release. CI intentionally does not download external data.
