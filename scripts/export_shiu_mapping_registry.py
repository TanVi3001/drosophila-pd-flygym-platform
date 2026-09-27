#!/usr/bin/env python
"""Export Shiu Table 3 neuron sets as an auditable, review-pending registry."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import pickle
import re
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL_ROOT = ROOT.parent / "external" / "Drosophila_brain_model"
DEFAULT_PROTOCOL = ROOT / "configs/workbench/shiu_public_benchmark_v2.json"
DEFAULT_OUTPUT = ROOT / "configs/workbench/shiu_table3_neuron_mapping_v1.json"
UPSTREAM_NOTEBOOK = "https://github.com/philshiu/Drosophila_brain_model/blob/main/figures.ipynb"
UPSTREAM_MAPPING = "https://github.com/philshiu/Drosophila_brain_model/blob/main/sez_neurons.pickle"
PUBLICATION = "Shiu et al. (2024), Nature, Supplementary Table 3"


class _DataOnlyUnpickler(pickle.Unpickler):
    """Load only builtin pickle values; refuse executable/global objects."""

    def find_class(self, module: str, name: str) -> Any:
        raise ValueError(f"mapping source contains unsupported pickle global {module}.{name}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_mapping_pickle(path: Path) -> dict[str, list[str]]:
    value = _DataOnlyUnpickler(io.BytesIO(path.read_bytes())).load()
    if not isinstance(value, Mapping):
        raise ValueError("upstream neuron-set source must be an object")
    result: dict[str, list[str]] = {}
    for key, raw_ids in value.items():
        if not isinstance(key, str) or not isinstance(raw_ids, (list, tuple)):
            raise ValueError("upstream mapping must contain string keys and ID lists")
        identifiers = [_normalize_id(item) for item in raw_ids]
        result[key] = identifiers
    return result


def load_inventory(path: Path) -> set[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        next(reader, None)
        ids = {_normalize_id(row[0]) for row in reader if row and row[0].strip()}
    if not ids:
        raise ValueError("FlyWire completeness inventory is empty")
    return ids


def _normalize_id(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError("neuron IDs must be decimal strings or integers")
    text = str(value).strip()
    if not text.isdigit():
        raise ValueError(f"neuron ID is not a decimal identifier: {value!r}")
    return text


def build_registry(
    protocol: Mapping[str, Any],
    upstream_sets: Mapping[str, list[str]],
    inventory: set[str],
    *,
    source_sha256: str,
    dataset_id: str = "flywire-630-2023-03-23",
) -> dict[str, Any]:
    if not re.fullmatch(r"[0-9a-fA-F]{64}", source_sha256):
        raise ValueError("source sha256 is required")
    cases = protocol.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("benchmark protocol must include cases")
    casefold_keys: dict[str, list[str]] = {}
    for key in upstream_sets:
        casefold_keys.setdefault(key.casefold(), []).append(key)

    records: list[dict[str, Any]] = []
    exact = aliases = missing = invalid = 0
    for case in cases:
        if not isinstance(case, Mapping):
            raise ValueError("benchmark case must be an object")
        metadata = case.get("metadata", {})
        cell_type = metadata.get("cell_type") if isinstance(metadata, Mapping) else None
        if not isinstance(cell_type, str) or not cell_type.strip():
            raise ValueError(f"case {case.get('case_id')} has no cell_type")
        if cell_type in upstream_sets:
            source_key = cell_type
            match_status = "EXACT"
            exact += 1
        else:
            candidates = casefold_keys.get(cell_type.casefold(), [])
            if len(candidates) == 1:
                source_key = candidates[0]
                match_status = "CASEFOLD_ALIAS_REQUIRES_REVIEW"
                aliases += 1
            else:
                source_key = None
                match_status = "MISSING" if not candidates else "AMBIGUOUS_ALIAS"
                missing += 1

        target_ids = [] if source_key is None else [_normalize_id(value) for value in upstream_sets[source_key]]
        invalid_ids = not target_ids or len(target_ids) != len(set(target_ids)) or any(item not in inventory for item in target_ids)
        mapping_status = match_status
        if source_key is not None and invalid_ids:
            mapping_status = "INVALID_SOURCE_ID_SET"
            invalid += 1
        case_id = str(case["case_id"])
        label_key = re.sub(r"[^A-Za-z0-9_.-]+", "_", cell_type).strip("._") or "target"
        records.append(
            {
                "mapping_id": f"shiu-table3-{label_key}-{case_id}-flywire630-v1",
                "version": "1",
                "case_id": case_id,
                "biological_target": cell_type,
                "source_mapping_key": source_key,
                "mapping_status": mapping_status,
                "backend": "lif_2024",
                "id_namespace": "flywire_root_id",
                "dataset_id": dataset_id,
                "intervention_type": "activation",
                "target_ids": target_ids,
                "sources": [
                    {"citation": PUBLICATION, "locator": "Supplementary Table 3; source row in frozen benchmark registry"},
                    {"citation": "Upstream Shiu model neuron-set mapping", "locator": UPSTREAM_MAPPING, "sha256": source_sha256},
                    {"citation": "Upstream model Figure 2 notebook", "locator": UPSTREAM_NOTEBOOK},
                ],
                "review_status": "PENDING_SCIENTIFIC_REVIEW",
                "context": {"assay": "proboscis_extension", "readout": "MN9", "source_section": "mn9_optogenetic_activation"},
                "reviewer": None,
                "reviewed_at": None,
                "limitations": [
                    "Source neuron sets are an upstream computational mapping, not proof of driver-line specificity or biological equivalence.",
                    "Human scientific review is required before the mapping can be prioritized.",
                    "An exact name match does not establish an experimentally validated perturbation.",
                ],
                "source_sha256": source_sha256,
                "invalid_source_ids": sorted(set(target_ids).difference(inventory)),
            }
        )

    return {
        "schema_version": "shiu-table3-mapping-registry-1",
        "dataset_id": dataset_id,
        "benchmark_protocol_id": protocol.get("protocol_id"),
        "benchmark_protocol_hash": protocol.get("protocol_hash"),
        "source_artifact": {"locator": UPSTREAM_MAPPING, "sha256": source_sha256},
        "review_status": "PENDING_SCIENTIFIC_REVIEW",
        "case_count": len(records),
        "exact_match_count": exact,
        "casefold_alias_count": aliases,
        "missing_count": missing,
        "invalid_id_set_count": invalid,
        "mapping_records": records,
        "scientific_scope": "Public-source neuron-set traceability only; all imported mappings require human review.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-root", type=Path, default=DEFAULT_MODEL_ROOT)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    model_root = args.model_root.resolve()
    mapping_path = model_root / "sez_neurons.pickle"
    inventory_path = model_root / "2023_03_23_completeness_630_final.csv"
    protocol = json.loads(args.protocol.resolve().read_text(encoding="utf-8"))
    registry = build_registry(
        protocol,
        load_mapping_pickle(mapping_path),
        load_inventory(inventory_path),
        source_sha256=sha256_file(mapping_path),
    )
    target = args.output.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: registry[key] for key in ("case_count", "exact_match_count", "casefold_alias_count", "missing_count", "invalid_id_set_count", "review_status")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
