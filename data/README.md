# External data policy

The repository is designed to clone and test without downloading large
datasets. Raw FlyWire exports, derived connectivity tables, and the Nature
supplementary workbook are intentionally kept outside GitHub. The files can
be restored from the links in [DOWNLOADS.md](DOWNLOADS.md); the exact local
file names, sizes, and SHA-256 values are recorded in
[source_manifest.json](source_manifest.json).

## Required data by workflow

| Workflow | Local input | Required to clone/test? |
| --- | --- | --- |
| Package and unit tests | None of the files below | No |
| FlyWire annotation analysis | `data/flywire_annotations.tsv` | Only for that analysis |
| FlyWire v783 completeness checks | `data/2025_Completeness_783.csv` | Only for that analysis |
| Connectivity analysis | `data/2025_Connectivity_783.parquet` | Only for that analysis |
| Shiu et al. public benchmark | `data/benchmarks/41586_2024_7763_MOESM2_ESM.xlsx` | Only for the benchmark profile |

The project does not silently download data during installation, tests, or
GitHub Actions. A missing optional input should be reported as an external
fixture requirement, not treated as a reason to commit the raw file.

## Verify a restored file

PowerShell:

```powershell
Get-FileHash data\flywire_annotations.tsv -Algorithm SHA256
Get-FileHash data\2025_Completeness_783.csv -Algorithm SHA256
Get-FileHash data\2025_Connectivity_783.parquet -Algorithm SHA256
Get-FileHash data\benchmarks\41586_2024_7763_MOESM2_ESM.xlsx -Algorithm SHA256
```

Compare the result with the corresponding entry in
[source_manifest.json](source_manifest.json). The manifest checksum is a
provenance check for the project copy; upstream releases can change and must
be revalidated before being used as a replacement.

## Attribution and terms

FlyWire public release data is published under the FlyWire public-release
terms, currently CC BY-NC 4.0 according to its citing guidelines. Cite the
FlyWire Consortium and the relevant paper or data record when using it. The
Nature supplementary workbook remains subject to the publisher's terms and
should be cited with the article. Follow the upstream pages in
[DOWNLOADS.md](DOWNLOADS.md) for current terms.
