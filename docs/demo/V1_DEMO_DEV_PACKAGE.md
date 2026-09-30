# V1 advisor demo: isolated DEVELOPMENT package

## Purpose and boundary

This step creates a physically separate package for the project's locked
74-case DEVELOPMENT membership. It does not run simulations or benchmarks and
does not create a Workbench StudySpec. The package includes only exact
allowlist-derived case paths and a reduced, label-free summary of existing LIF
artifacts. A computational run's target IDs are not, by themselves, a
scientifically reviewed mapping.

The membership is verified with the canonical SHA-256
`3f9b39c1b6e91d766e85eaa0347f79243553a9b73a51442e944b7d8135713467`.
The package builder checks a fixed set of filenames for each ID. It does not
list, search, glob, or recurse through the source results directory.

## Prior boundary incident

The aborted demo-harness attempt exposed case-directory names from a mixed
results directory through a file-listing operation. No labels, outcome values,
or result files were opened in that attempt. The project-wide current-32
classification remains `POST_FREEZE_POTENTIALLY_EXPOSED_EVALUATION_SET`; this
record does not relabel that set as pristine.

```text
MIXED_DIRECTORY_NAMES_EXPOSED = TRUE
HELDOUT_LABELS_READ = FALSE
HELDOUT_OUTCOMES_READ = FALSE
CURRENT_32_CLASSIFICATION = POST_FREEZE_POTENTIALLY_EXPOSED_EVALUATION_SET
```

Since the D0 package task began, source artifacts have been accessed only at
the exact paths derived from the 74-ID DEVELOPMENT allowlist. The builder and
tests are designed not to enumerate any directory.

## Build and verify

From the V1 demo worktree root, after the runtime source artifacts are
available at their configured location:

```powershell
python scripts/build_v1_demo_dev_package.py
```

Optional explicit paths:

```powershell
python scripts/build_v1_demo_dev_package.py `
  --source-root 'E:\research-\external\Drosophila_brain_model\results\workbench_shiu_v2_rewired_lif_run02' `
  --package-root 'E:\research-\.workbench\v1-demo-dev-package-v1'
```

The package is written outside the source results directory. The builder
refuses to overwrite an existing package root. It records missing exact-path
artifacts as `MISSING_EXPECTED_ARTIFACT`; it never searches for alternatives.

## Package contents

- `manifest.json`: source identities and hashes, builder/source revisions,
  exact DEVELOPMENT membership, artifact availability, and package digest.
- `checksums.sha256`: hashes for the manifest and all generated package files.
- `demo_case_readiness.json`: only technical availability flags; no labels,
  outcome classes, or ranking performance.
- `cases/<DEV_CASE_ID>/`: selected input metadata, recorded execution target
  IDs with an explicit unreviewed status, reduced control/condition LIF output,
  source data-audit summary, provenance, and StudySpec availability status.
- `shared/v1_development_case_allowlist_v1.json`: the 74 IDs and split hash.

The package's readiness means its 74-case membership, schema/content audit,
and checksums pass. It does not mean every case is ready for a complete live
advisor demo: the readiness index separately reports whether a reviewed V1
mapping record and a frozen Workbench StudySpec actually exist.

No AI model, AI V2 code/output, retraining, simulation, benchmark evaluation,
or external validation is used by this builder.
