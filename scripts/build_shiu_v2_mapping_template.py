#!/usr/bin/env python
"""Build the conservative FlyWire-630 mapping sheet for the 106-case registry."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "configs/workbench/shiu_public_benchmark_v2.json"
DEFAULT_OUTPUT = ROOT / "configs/workbench/shiu_v2_flywire630_mapping.csv"
FIELDS = (
    "case_id",
    "cell_type",
    "source_section",
    "source_excel_row",
    "reference_label",
    "intervention",
    "mapping_status",
    "assay_comparable",
    "input_ids_json",
    "silence_ids_json",
    "readout_ids_json",
    "reviewer_1",
    "reviewer_2",
    "review_decision",
    "notes",
)


def _load(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping) or not isinstance(value.get("cases"), list):
        raise ValueError("benchmark registry must contain a cases list")
    return value


def build(registry_path: Path, output_path: Path) -> int:
    registry = _load(registry_path)
    rows: list[dict[str, str]] = []
    for case in registry["cases"]:
        metadata = case.get("metadata", {})
        if not isinstance(metadata, Mapping):
            raise ValueError(f"case metadata is not an object: {case.get('case_id')}")
        rows.append(
            {
                "case_id": str(case.get("case_id", "")),
                "cell_type": str(metadata.get("cell_type", "")),
                "source_section": str(metadata.get("source_section", "")),
                "source_excel_row": str(metadata.get("source_excel_row", "")),
                "reference_label": str(case.get("reference_label", "")),
                "intervention": str(metadata.get("intervention", "")),
                "mapping_status": "PENDING",
                "assay_comparable": "PENDING",
                "input_ids_json": "[]",
                "silence_ids_json": "[]",
                "readout_ids_json": "[]",
                "reviewer_1": "",
                "reviewer_2": "",
                "review_decision": "PENDING",
                "notes": "Fill only from source-grounded FlyWire-630 evidence; do not infer from cell_type name.",
            }
        )
    if len({row["case_id"] for row in rows}) != len(rows):
        raise ValueError("benchmark registry contains duplicate case IDs")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    count = build(args.registry.resolve(), args.output.resolve())
    print(json.dumps({"status": "TEMPLATE_CREATED", "case_count": count, "output": str(args.output.resolve())}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
