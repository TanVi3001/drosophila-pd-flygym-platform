#!/usr/bin/env python
"""Build the conservative FlyWire-630 mapping sheet for the 106-case registry."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import pickle
import re
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "configs/workbench/shiu_public_benchmark_v2.json"
DEFAULT_OUTPUT = ROOT / "configs/workbench/shiu_v2_flywire630_mapping.csv"
DEFAULT_UPSTREAM_PICKLE = ROOT.parent / "external/Drosophila_brain_model/sez_neurons.pickle"
DEFAULT_COMPLETENESS = ROOT.parent / "external/Drosophila_brain_model/2023_03_23_completeness_630_final.csv"
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
    "reviewer_1_decision",
    "reviewer_2_decision",
    "review_decision",
    "notes",
)


def _load(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping) or not isinstance(value.get("cases"), list):
        raise ValueError("benchmark registry must contain a cases list")
    return value


def _normalize(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).strip().lower())


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_upstream(path: Path) -> tuple[dict[str, list[str]], dict[str, str]]:
    with path.open("rb") as handle:
        value = pickle.load(handle)
    if not isinstance(value, dict):
        raise ValueError("upstream neuron mapping must be a dictionary")
    result: dict[str, list[str]] = {}
    canonical_labels: dict[str, str] = {}
    for label, raw_ids in value.items():
        if not isinstance(raw_ids, (list, tuple)) or not raw_ids:
            raise ValueError(f"upstream mapping for {label!r} must be a non-empty list")
        ids: list[str] = []
        for raw_id in raw_ids:
            text = str(raw_id).strip()
            if not text.isdigit() or text in ids:
                raise ValueError(f"invalid or duplicate neuron ID for {label!r}: {raw_id!r}")
            ids.append(text)
        key = _normalize(label)
        if not key or key in result:
            raise ValueError(f"duplicate or empty normalized upstream label: {label!r}")
        result[key] = ids
        canonical_labels[key] = str(label)
    return result, canonical_labels


def _verify_completeness(ids: list[str], path: Path) -> None:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        first_line = handle.readline()
    if not first_line:
        raise ValueError(f"completeness inventory is empty: {path}")
    inventory = {part.strip().strip('"') for part in first_line.split(",")}
    # The completeness CSV stores neuron IDs as its first column and is too
    # large to load through the standard library for every generated row.
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        next(handle)
        for line in handle:
            first = line.split(",", 1)[0].strip().strip('"')
            if first:
                inventory.add(first)
    missing = sorted(set(ids).difference(inventory))
    if missing:
        raise ValueError(f"upstream IDs are absent from completeness inventory: {missing[:10]}")


def build(
    registry_path: Path,
    output_path: Path,
    *,
    upstream_pickle: Path | None = None,
    readout_ids: list[str] | None = None,
    completeness_path: Path | None = None,
    reviewer_1: str = "",
    reviewer_2: str = "",
) -> int:
    registry = _load(registry_path)
    upstream: dict[str, list[str]] | None = None
    canonical_labels: dict[str, str] = {}
    if upstream_pickle is not None:
        upstream, canonical_labels = _load_upstream(upstream_pickle)
    declared_readouts = readout_ids or []
    if upstream_pickle is not None and completeness_path is None:
        raise ValueError("completeness_path is required when upstream_pickle is supplied")
    if upstream is not None:
        all_ids = [neuron_id for values in upstream.values() for neuron_id in values]
        _verify_completeness(all_ids, completeness_path)  # type: ignore[arg-type]
    evidence_note = None
    if upstream_pickle is not None:
        evidence_note = (
            "AI pre-review: exact name-to-ID mapping from upstream sez_neurons.pickle "
            f"(sha256={_sha256(upstream_pickle)}); IDs verified against FlyWire-630 completeness. "
            "Human review is still required for assay comparability and sign-off."
        )
    rows: list[dict[str, str]] = []
    for case in registry["cases"]:
        metadata = case.get("metadata", {})
        if not isinstance(metadata, Mapping):
            raise ValueError(f"case metadata is not an object: {case.get('case_id')}")
        source_cell_type = str(metadata.get("cell_type", ""))
        normalized_cell_type = _normalize(source_cell_type)
        input_ids = [] if upstream is None else upstream.get(normalized_cell_type, [])
        if upstream is not None and not input_ids:
            raise ValueError(f"no upstream neuron mapping for benchmark cell type: {source_cell_type!r}")
        cell_type = canonical_labels.get(normalized_cell_type, source_cell_type)
        rows.append(
            {
                "case_id": str(case.get("case_id", "")),
                "cell_type": cell_type,
                "source_section": str(metadata.get("source_section", "")),
                "source_excel_row": str(metadata.get("source_excel_row", "")),
                "reference_label": str(case.get("reference_label", "")),
                "intervention": str(metadata.get("intervention", "")),
                "mapping_status": "PENDING",
                "assay_comparable": "PENDING",
                "input_ids_json": json.dumps(input_ids, separators=(",", ":")),
                "silence_ids_json": "[]",
                "readout_ids_json": json.dumps(declared_readouts, separators=(",", ":")),
                "reviewer_1": reviewer_1,
                "reviewer_2": reviewer_2,
                "reviewer_1_decision": "PENDING",
                "reviewer_2_decision": "PENDING",
                "review_decision": "PENDING",
                "notes": evidence_note or "Fill only from source-grounded FlyWire-630 evidence; do not infer from cell_type name.",
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
    parser.add_argument("--upstream-pickle", type=Path, default=None)
    parser.add_argument("--completeness", type=Path, default=None)
    parser.add_argument("--readout-id", action="append", default=[])
    parser.add_argument("--reviewer-1", default="")
    parser.add_argument("--reviewer-2", default="")
    args = parser.parse_args()
    count = build(
        args.registry.resolve(),
        args.output.resolve(),
        upstream_pickle=None if args.upstream_pickle is None else args.upstream_pickle.resolve(),
        completeness_path=None if args.completeness is None else args.completeness.resolve(),
        readout_ids=[str(value).strip() for value in args.readout_id],
        reviewer_1=str(args.reviewer_1).strip(),
        reviewer_2=str(args.reviewer_2).strip(),
    )
    print(json.dumps({"status": "TEMPLATE_CREATED", "case_count": count, "output": str(args.output.resolve())}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
