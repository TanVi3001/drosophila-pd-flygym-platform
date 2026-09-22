#!/usr/bin/env python
"""Materialize one auditable degree-preserving null for a connectivity table.

The output is a new parquet file with only Postsynaptic_ID and
Postsynaptic_Index rewired.  All source-local edge attributes remain attached
to their original edge rows.  This prepares a real graph-null connectivity
input for the separate neural LIF runner; it does not produce biological
claims or infer source-to-model mappings.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from drosophila_pd.workbench import rewire_connectome_targets  # noqa: E402


REQUIRED_COLUMNS = (
    "Presynaptic_ID",
    "Postsynaptic_ID",
    "Presynaptic_Index",
    "Postsynaptic_Index",
    "Connectivity",
    "Excitatory",
    "Excitatory x Connectivity",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _array_sha256(values: Any) -> str:
    import numpy as np

    array = np.asarray(values)
    return hashlib.sha256(array.tobytes(order="C")).hexdigest()


def materialize(args: argparse.Namespace) -> dict[str, Any]:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError("materializing a connectivity null requires pyarrow") from exc

    source = args.connectivity.resolve()
    output = args.output.resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    if source == output:
        raise ValueError("output must be a new parquet path; the input is never overwritten")
    output.parent.mkdir(parents=True, exist_ok=True)

    table = pq.read_table(source)
    missing = [column for column in REQUIRED_COLUMNS if column not in table.column_names]
    if missing:
        raise ValueError(f"connectivity table is missing required columns: {missing}")
    source_ids = table["Presynaptic_ID"].to_numpy(zero_copy_only=False)
    target_ids = table["Postsynaptic_ID"].to_numpy(zero_copy_only=False)
    target_indices = table["Postsynaptic_Index"].to_numpy(zero_copy_only=False)
    strata = table["Excitatory"].to_numpy(zero_copy_only=False)

    result = dict(
        rewire_connectome_targets(
            source_ids,
            target_ids,
            target_indices,
            strata,
            seed=args.seed,
            swaps=args.swaps,
            max_attempts=args.max_attempts,
            forbid_self_loops=not args.allow_self_loops,
            check_duplicate_edges=not args.skip_duplicate_check,
        )
    )
    target_id_field = table.schema.field(table.schema.get_field_index("Postsynaptic_ID"))
    target_index_field = table.schema.field(table.schema.get_field_index("Postsynaptic_Index"))
    table = table.set_column(
        table.schema.get_field_index("Postsynaptic_ID"),
        target_id_field,
        pa.array(result.pop("target_ids"), type=target_id_field.type),
    )
    table = table.set_column(
        table.schema.get_field_index("Postsynaptic_Index"),
        target_index_field,
        pa.array(result.pop("target_indices"), type=target_index_field.type),
    )
    pq.write_table(table, output, compression=args.compression)

    manifest_path = args.manifest.resolve() if args.manifest else output.with_suffix(output.suffix + ".manifest.json")
    manifest = {
        "schema_version": "connectome-rewire-manifest-1",
        "status": result["status"],
        "created_at_utc": datetime.now(UTC).isoformat(),
        "input": {
            "path": str(source),
            "sha256": _sha256(source),
            "rows": int(table.num_rows),
            "columns": list(table.column_names),
        },
        "output": {
            "path": str(output),
            "sha256": _sha256(output),
            "size_bytes": output.stat().st_size,
        },
        "rewire": result,
        "input_arrays": {
            "source_ids_sha256": _array_sha256(source_ids),
            "target_ids_sha256": _array_sha256(target_ids),
            "strata_sha256": _array_sha256(strata),
        },
        "scientific_scope": (
            "Prepared structural-null connectivity only. A downstream LIF run "
            "must declare its own seeds, input/readout mapping, metrics and provenance."
        ),
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--connectivity", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--swaps", type=int, required=True)
    parser.add_argument("--max-attempts", type=int)
    parser.add_argument("--compression", default="zstd", choices=("snappy", "gzip", "brotli", "zstd", "lz4", "none"))
    parser.add_argument("--allow-self-loops", action="store_true")
    parser.add_argument("--skip-duplicate-check", action="store_true")
    args = parser.parse_args()
    if args.swaps < 0:
        parser.error("--swaps must be non-negative")
    if args.compression == "none":
        args.compression = None
    manifest = materialize(args)
    print(json.dumps({
        "status": manifest["status"],
        "output": manifest["output"]["path"],
        "manifest": str((args.manifest or args.output.with_suffix(args.output.suffix + ".manifest.json")).resolve()),
        "successful_swaps": manifest["rewire"]["successful_swaps"],
        "requested_swaps": manifest["rewire"]["requested_swaps"],
    }, indent=2))
    return 0 if manifest["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
