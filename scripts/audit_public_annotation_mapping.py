#!/usr/bin/env python
"""Audit public cell-type-name to FlyWire-root mapping coverage.

The audit is intentionally conservative.  It reports exact matches in a
versioned annotation table, but it never guesses a root ID from a prefix or
from a different connectome materialization.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping


def _load(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError("registry must be a JSON object")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _normalize(value: Any) -> str:
    text = re.sub(r"[_\-\s]+", "", str(value or "").strip().lower())
    return re.sub(r"[lr]$", "", text)


def audit(registry_path: Path, annotation_path: Path) -> dict[str, Any]:
    registry = _load(registry_path)
    cases = registry.get("cases", [])
    if not isinstance(cases, list):
        raise ValueError("registry cases must be a list")
    with annotation_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        rows = list(reader)
        fields = set(reader.fieldnames or ())
    candidate_fields = tuple(field for field in ("cell_type", "hemibrain_type", "primary_type") if field in fields)
    if not candidate_fields:
        raise ValueError("annotation file has no supported cell-type field")
    index: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        for field in candidate_fields:
            key = _normalize(row.get(field))
            if key:
                index.setdefault(key, []).append(row)
    matches: list[dict[str, Any]] = []
    for case in cases:
        metadata = case.get("metadata", {})
        name = str(metadata.get("cell_type", ""))
        rows_for_name = index.get(_normalize(name), [])
        root_ids = sorted({str(row.get("root_id", "")) for row in rows_for_name if row.get("root_id")})
        matches.append(
            {
                "case_id": case.get("case_id"),
                "cell_type": name,
                "status": "EXACT_UNIQUE" if len(root_ids) == 1 else "EXACT_AMBIGUOUS" if root_ids else "MISSING",
                "root_ids": root_ids,
                "annotation_fields": list(candidate_fields),
            }
        )
    counts = {
        status: sum(item["status"] == status for item in matches)
        for status in ("EXACT_UNIQUE", "EXACT_AMBIGUOUS", "MISSING")
    }
    return {
        "status": "READY" if counts["MISSING"] == 0 and counts["EXACT_AMBIGUOUS"] == 0 else "BLOCKED",
        "registry": str(registry_path),
        "registry_protocol_id": registry.get("protocol_id"),
        "annotation": str(annotation_path),
        "annotation_sha256": _sha256(annotation_path),
        "annotation_fields": list(candidate_fields),
        "case_count": len(matches),
        "counts": counts,
        "matches": matches,
        "limitations": [
            "Exact name matches are not proof of biological equivalence or driver-line specificity.",
            "Annotation release/materialization must match the model connectome before root IDs are used.",
            "Ambiguous and missing cases must remain unassessable in graph-null evaluation.",
        ],
        "scientific_scope": "Public annotation mapping audit only; no causal or biological validation claim.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--annotation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.registry.resolve(), args.annotation.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "counts": result["counts"], "output": str(args.output.resolve())}, indent=2))
    return 0 if result["status"] == "READY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
