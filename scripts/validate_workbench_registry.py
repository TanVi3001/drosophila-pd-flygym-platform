#!/usr/bin/env python
"""Validate a Workbench public-data registry and its source artifact.

This validator checks computational integrity and split discipline only.  A
READY result never means that a domain scientist has approved the biological
mapping.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


def _load(path: Path) -> Mapping[str, Any]:
    if path.suffix.lower() in {".yaml", ".yml"}:
        import yaml

        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    else:
        value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError("registry must be a mapping")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def validate(registry_path: Path, artifact_path: Path) -> dict[str, Any]:
    registry = _load(registry_path)
    source = registry.get("source")
    cases = registry.get("cases")
    split = registry.get("split")
    if not isinstance(source, Mapping) or not isinstance(cases, list) or not isinstance(split, Mapping):
        raise ValueError("registry requires source, cases and split mappings")
    errors: list[str] = []
    expected_hash = str(source.get("artifact_sha256", "")).upper()
    actual_hash = _sha256(artifact_path)
    if expected_hash != actual_hash:
        errors.append(f"source_checksum_mismatch:{expected_hash}!={actual_hash}")
    ids = [str(case.get("case_id", "")) for case in cases if isinstance(case, Mapping)]
    if len(ids) != len(set(ids)) or any(not case_id for case_id in ids):
        errors.append("case_ids_not_unique_or_empty")
    labels = [str(case.get("reference_label", "")).lower() for case in cases if isinstance(case, Mapping)]
    if set(labels) != {"positive", "negative"}:
        errors.append("both_reference_labels_required")
    development = {str(value) for value in split.get("development_case_ids", [])}
    held_out = {str(value) for value in split.get("held_out_case_ids", [])}
    known = set(ids)
    if development & held_out:
        errors.append("development_and_held_out_overlap")
    if development | held_out != known:
        errors.append("development_and_held_out_do_not_cover_registry")
    by_id = {str(case["case_id"]): case for case in cases if isinstance(case, Mapping)}
    for name, selected in (("development", development), ("held_out", held_out)):
        selected_labels = {str(by_id[item].get("reference_label", "")).lower() for item in selected if item in by_id}
        if selected_labels != {"positive", "negative"}:
            errors.append(f"{name}_must_contain_both_labels")
    groups: dict[str, str] = {}
    for case in cases:
        if not isinstance(case, Mapping):
            errors.append("case_is_not_mapping")
            continue
        metadata = case.get("metadata")
        source_case = case.get("source")
        if not isinstance(metadata, Mapping) or not isinstance(source_case, Mapping):
            errors.append(f"{case.get('case_id')}:metadata_or_source_missing")
            continue
        group = str(metadata.get("case_group", "")).strip()
        if not group:
            errors.append(f"{case.get('case_id')}:case_group_missing")
        elif group in groups and groups[group] != str(case.get("case_id")):
            errors.append(f"group_leakage:{group}")
        else:
            groups[group] = str(case.get("case_id"))
        for required in ("locator", "label_basis"):
            if not source_case.get(required):
                errors.append(f"{case.get('case_id')}:source_{required}_missing")
    return {
        "status": "READY" if not errors else "BLOCKED",
        "registry": str(registry_path),
        "artifact": str(artifact_path),
        "artifact_sha256": actual_hash,
        "protocol_id": registry.get("protocol_id"),
        "freeze_status": registry.get("freeze_status"),
        "review_status": (registry.get("evaluation_contract") or {}).get("review_status"),
        "case_count": len(ids),
        "positive_count": sum(label == "positive" for label in labels),
        "negative_count": sum(label == "negative" for label in labels),
        "development_case_count": len(development),
        "held_out_case_count": len(held_out),
        "errors": errors,
        "scientific_scope": "Computational public-data integrity only; no domain-scientist approval is inferred.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate(args.registry.resolve(), args.artifact.resolve())
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if result["status"] == "READY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
