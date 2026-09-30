# External validation package specification — v1

## Purpose and status

This defines a two-custodian handoff. It contains no selected dataset or real case data. `EXTERNAL_VALIDATION_DATASET = NOT_SELECTED`; the independent curator must select and assess any future source outside the owner/Codex development workspace.

The owner-facing receipt has this shape:

```text
owner_receipt/
├── validation_manifest.json
├── checksums.sha256
└── validation_input_package/
    ├── input_schema.json
    ├── cases.jsonl
    └── optional input-only JSON/JSONL/CSV/TSV assets
```

The curator keeps a separate, access-controlled vault:

```text
curator_vault/
├── label_schema.json
├── curator_checksums.sha256
└── validation_labels_sealed/
    └── labels.jsonl
```

The sealed directory and label schema are not copied to the owner receipt. The manifest contains only the SHA-256 of the label schema; it contains no label values or label-column names. The owner-side validator refuses a receipt if `validation_labels_sealed/` is present at its root and never opens that directory.

## Owner-facing files

### `validation_input_package/`

`cases.jsonl` has one JSON object per case. Each object uses a neutral `case_id` matching `^EXTVAL_[0-9]{4,}$` and only input-side fields, such as declared assay/intervention metadata, input neuron identity, mapping provenance and simulator inputs. It must contain no label, outcome, phenotype, response-class, reference-label or other result-like field/value.

`input_schema.json` declares `schema_version`, required input fields and the neutral ID pattern. It must describe inputs only. Optional assets may be JSON, JSONL, CSV or TSV and are subject to the same no-peeking checks. This v1 validator does not accept binary or executable assets.

### `validation_manifest.json`

Required metadata fields:

- `schema_version`: `external-validation-manifest-v1`
- `package_version`
- `case_count`
- `assay_type`
- `source_citation`
- `input_schema_version`
- `input_schema_sha256`
- `label_schema_sha256` (hash of curator-held schema only)
- `curator_identifier`
- `created_at_utc` (ISO-8601)

It must not contain individual case IDs, outcomes, labels, or an outcome-derived ordering. A schema hash is an integrity reference, not permission to retrieve the schema before reveal.

### `checksums.sha256`

Use sorted lines in standard form `64-lowercase-hex-digits␠␠relative/path`. Cover exactly the manifest and all files under `validation_input_package/`; exclude the checksum file itself and all curator-vault files. Paths must be relative POSIX paths without traversal.

## Curator-held files

`label_schema.json` documents the outcome type, allowed encodings and any predeclared transformations; it contains no observations. `validation_labels_sealed/labels.jsonl` pairs neutral IDs with measured outcomes. Keep both in curator-controlled storage with separate credentials and an audit log. Only the independent evaluator receives the sealed labels after the prediction-freeze and label-release gates pass.

The curator also maintains `curator_checksums.sha256` inside the vault, covering exactly `label_schema.json` and `validation_labels_sealed/labels.jsonl`. This checksum file is curator/evaluator-only and must never be copied into the owner receipt. Verify it at label release; record the verified digest in the evaluator's restricted audit record.

The curator must verify that label IDs join one-to-one with input IDs, but must not pass join diagnostics, label counts by class, outcome-derived filenames, or label ordering to the owner before freeze. The owner-facing `case_count` is permitted; class balance is not.

## Anonymization and ordering

Use IDs such as `EXTVAL_0001`; never encode genotype, response direction, phenotype, group, case rank, source row, or expected result in IDs, filenames, directory names, free-text descriptions, metadata, or ordering. Keep owner cases sorted by neutral ID. Retain the private mapping from neutral IDs to source records only in the curator vault. Do not use source row order as the owner-facing order.

## Validation and limitations

Before receipt, run:

```powershell
python scripts/validate_external_validation_package.py <owner_receipt-directory>
```

The validator checks package structure, schema basics, prohibited names/fields/value tokens, neutral IDs, case count, absence of the sealed-label directory and SHA-256 integrity. `PASS` is a syntactic gate, not proof that a curator has not leaked information through semantics or prior knowledge. A signed curator attestation and independent owner receipt review remain required.

The package does not define or choose external metrics. Once input schema and assay are known, the owner/statistician must freeze an endpoint and analysis plan before any label is revealed. Do not automatically reuse the internal `k=5`/P@5 contract for a different or small assay.
