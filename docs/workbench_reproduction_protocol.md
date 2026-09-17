# Reproduction protocol

This protocol is a release gate, not a claim that the current worktree has
already been reproduced by a second person.

## Operator separation

An independent-operator claim is available only when a genuinely separate
human starts from a clean checkout or a fresh isolated environment. A project
owner, script, or AI may still run the same protocol, but that result is
recorded as computational reproduction and does not close the independent-
operator gate. The actor receives only the tagged source, locked dependency export,
public input locators/checksums, this protocol, and the frozen study configs.
They do not edit thresholds, labels, candidate order, or the held-out split.

## Required run

1. Install the platform and neural environments separately with Python 3.12.
2. Verify both repositories, interpreter paths, dependency versions, and public input checksums.
3. Run one declared success case and one declared failure/QC case.
4. Run the frozen subset with the exact screening seed list supplied in the manifest.
5. Save the SQLite/job records, `RunManifest`, report, logs, and failure artifacts.
6. Compare code/data/config/environment hashes and numerical outputs against the primary archive.
7. Record any discrepancy before looking at or changing the implementation.

## Pass criteria

The completed manifest must set `status: PASS`, set
`environment.clean_install: true`, include both success and failure cases, and
record manifest/provenance/output comparisons plus declared tolerances. A
separate human may additionally set `operator_role: second_operator`; this is
never inferred from the name or from a clean environment. Any unexplained
discrepancy is a release blocker. A successful rerun does not establish
biological validity.

The machine-readable starting point is
`configs/workbench/reproduction_manifest.template.yaml`.

After the second operator has produced both campaign manifests, the verifier
can be run without importing either neural package:

```powershell
python scripts/verify_workbench_reproduction.py `
  --reference-manifest path/to/primary/campaign_manifest.json `
  --replica-manifest path/to/second-operator/campaign_manifest.json `
  --failure-reference-manifest path/to/primary/failure_manifest.json `
  --failure-replica-manifest path/to/second-operator/failure_manifest.json `
  --operator-name ACTOR_NAME `
  --operator-role second_operator `
  --clean-install `
  --lockfile-or-export requirements/lif-runtime-py312.lock `
  --output reproduction_manifest.json
```

Omitting either failure manifest, or omitting `--clean-install`, intentionally
leaves the result `BLOCKED`. The verifier compares the declared config hashes,
job keys, run provenance and `lif_condition/metrics.json` values; it does not
turn a same-machine rerun, an AI run, or a self-declared name into independent
evidence.
