#!/usr/bin/env python
"""Fail-closed no-peeking check for an owner-facing external-validation package.

The validator never opens validation_labels_sealed. Its scope is syntactic: it
can reject obvious label-bearing fields/files, but cannot prove semantic
blinding. An independent curator must still attest to package construction.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "configs/workbench/external_validation_access_policy_v1.json"
MANIFEST_NAME = "validation_manifest.json"
INPUT_DIR_NAME = "validation_input_package"
SEALED_LABELS_NAME = "validation_labels_sealed"
CHECKSUMS_NAME = "checksums.sha256"
SCHEMA_NAME = "input_schema.json"
CASES_NAME = "cases.jsonl"
MINIMUM_CASE_FIELDS = {
    "case_id",
    "assay_metadata",
    "intervention_metadata",
    "input_neuron_identity",
    "simulator_input",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _normalized_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _token_set(config: dict[str, Any], key: str) -> set[str]:
    values = config.get(key, [])
    if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
        raise ValueError(f"policy field {key} must be an array of strings")
    return {_normalized_key(item) for item in values}


def _contains_token(value: str, tokens: set[str]) -> str | None:
    normalized = _normalized_key(value)
    for token in sorted(tokens, key=len, reverse=True):
        if token and token in normalized:
            return token
    return None


def _walk_owner_files(root: Path, prohibited_filename_tokens: set[str]) -> tuple[list[Path], list[str]]:
    files: list[Path] = []
    errors: list[str] = []
    for current, dirnames, filenames in os.walk(root, followlinks=False):
        current_path = Path(current)
        for name in list(dirnames):
            path = current_path / name
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                errors.append(f"symlink is not allowed: {relative}")
                dirnames.remove(name)
                continue
            token = _contains_token(name, prohibited_filename_tokens)
            if token:
                errors.append(f"prohibited directory name: {relative}")
                dirnames.remove(name)
        for name in filenames:
            path = current_path / name
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                errors.append(f"symlink is not allowed: {relative}")
                continue
            token = _contains_token(name, prohibited_filename_tokens)
            if token:
                errors.append(f"prohibited filename: {relative}")
                continue
            files.append(path)
    return files, errors


def _scan_sensitive_keys(value: Any, path: str, tokens: set[str], errors: list[str]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if isinstance(key, str) and _contains_token(key, tokens):
                errors.append(f"prohibited field name in {path}")
            _scan_sensitive_keys(child, path, tokens, errors)
    elif isinstance(value, list):
        for child in value:
            _scan_sensitive_keys(child, path, tokens, errors)


def _scan_sensitive_values(value: Any, path: str, tokens: set[str], errors: list[str]) -> None:
    if isinstance(value, dict):
        for child in value.values():
            _scan_sensitive_values(child, path, tokens, errors)
    elif isinstance(value, list):
        for child in value:
            _scan_sensitive_values(child, path, tokens, errors)
    elif isinstance(value, str) and _contains_token(value, tokens):
        errors.append(f"outcome-like value in {path}")


def _safe_relative_path(raw: str) -> PurePosixPath:
    path = PurePosixPath(raw)
    if path.is_absolute() or ".." in path.parts or "\\" in raw or not raw:
        raise ValueError("checksum paths must be safe relative POSIX paths")
    return path


def _read_checksums(path: Path) -> tuple[dict[str, str], list[str]]:
    entries: dict[str, str] = {}
    errors: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return {}, ["checksums.sha256 is unreadable"]
    previous = ""
    for line_number, line in enumerate(lines, start=1):
        match = re.fullmatch(r"([0-9a-fA-F]{64})  (.+)", line)
        if not match:
            errors.append(f"invalid checksum record at line {line_number}")
            continue
        digest, raw_path = match.groups()
        try:
            safe_path = _safe_relative_path(raw_path).as_posix()
        except ValueError:
            errors.append(f"unsafe checksum path at line {line_number}")
            continue
        if safe_path in entries:
            errors.append(f"duplicate checksum path at line {line_number}")
            continue
        if previous and safe_path <= previous:
            errors.append("checksum records must be sorted by path")
        previous = safe_path
        entries[safe_path] = digest.lower()
    return entries, errors


def validate_package(package_root: Path, policy_path: Path = POLICY_PATH) -> list[str]:
    """Return safe diagnostics; never read a sealed-label directory."""
    errors: list[str] = []
    try:
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
        config = policy["no_peeking_validator"]
        prohibited_columns = _token_set(config, "prohibited_column_tokens")
        prohibited_filenames = _token_set(config, "prohibited_filename_tokens")
        prohibited_values = _token_set(config, "prohibited_value_tokens")
        allowed_extensions = set(config["allowed_input_extensions"])
        case_id_pattern = re.compile(config["case_id_pattern"])
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return ["no-peeking policy is missing or invalid"]

    if package_root.is_symlink():
        return ["package root must not be a symlink"]
    root = package_root.resolve()
    if not root.is_dir():
        return ["package root does not exist or is not a directory"]

    # Stop before directory traversal: presence alone is a policy violation;
    # the sealed package's filenames and bytes are deliberately not inspected.
    sealed_path = root / SEALED_LABELS_NAME
    if os.path.lexists(sealed_path):
        return ["sealed labels directory must not be present in owner workspace"]

    allowed_root_entries = {MANIFEST_NAME, INPUT_DIR_NAME, CHECKSUMS_NAME}
    try:
        root_entries = {entry.name for entry in root.iterdir()}
    except OSError:
        return ["package root cannot be listed"]
    for unexpected in sorted(root_entries - allowed_root_entries):
        errors.append(f"unexpected package-root entry: {unexpected}")
    for required in (MANIFEST_NAME, INPUT_DIR_NAME, CHECKSUMS_NAME):
        if not (root / required).exists():
            errors.append(f"required package item missing: {required}")
    if errors:
        return errors

    input_root = root / INPUT_DIR_NAME
    if not input_root.is_dir() or input_root.is_symlink():
        return ["validation_input_package must be a real directory"]

    files, walk_errors = _walk_owner_files(root, prohibited_filenames)
    errors.extend(walk_errors)
    relative_files = {path.relative_to(root).as_posix(): path for path in files}
    input_schema_rel = f"{INPUT_DIR_NAME}/{SCHEMA_NAME}"
    cases_rel = f"{INPUT_DIR_NAME}/{CASES_NAME}"
    for required in (input_schema_rel, cases_rel):
        if required not in relative_files:
            errors.append(f"required input file missing: {required}")

    for relative, path in sorted(relative_files.items()):
        if relative == CHECKSUMS_NAME:
            continue
        if relative != MANIFEST_NAME and not relative.startswith(f"{INPUT_DIR_NAME}/"):
            errors.append(f"file outside owner input package: {relative}")
            continue
        if path.suffix.casefold() not in allowed_extensions:
            errors.append(f"unsupported owner-input file extension: {relative}")

    manifest: dict[str, Any] = {}
    input_schema: dict[str, Any] = {}
    try:
        manifest_value = json.loads((root / MANIFEST_NAME).read_text(encoding="utf-8"))
        if not isinstance(manifest_value, dict):
            raise ValueError
        manifest = manifest_value
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
        errors.append("validation manifest is not a JSON object")

    try:
        schema_value = json.loads((input_root / SCHEMA_NAME).read_text(encoding="utf-8"))
        if not isinstance(schema_value, dict):
            raise ValueError
        input_schema = schema_value
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
        errors.append("input schema is not a JSON object")

    _scan_sensitive_keys(input_schema, input_schema_rel, prohibited_columns, errors)
    _scan_sensitive_values(input_schema, input_schema_rel, prohibited_values, errors)
    if manifest:
        required_manifest_fields = {
            "schema_version",
            "package_version",
            "case_count",
            "assay_type",
            "source_citation",
            "input_schema_version",
            "input_schema_sha256",
            "label_schema_sha256",
            "curator_identifier",
            "created_at_utc",
        }
        missing = required_manifest_fields - set(manifest)
        if missing:
            errors.append("manifest is missing required metadata fields")
        if set(manifest) - required_manifest_fields:
            errors.append("manifest contains undeclared metadata fields")
        if manifest.get("schema_version") != "external-validation-manifest-v1":
            errors.append("unsupported manifest schema version")
        if not isinstance(manifest.get("case_count"), int) or manifest.get("case_count", 0) < 1:
            errors.append("manifest case_count must be a positive integer")
        for field in ("input_schema_sha256", "label_schema_sha256"):
            if not isinstance(manifest.get(field), str) or not re.fullmatch(r"[0-9a-fA-F]{64}", manifest[field]):
                errors.append(f"manifest {field} must be a SHA-256 hex digest")
        if manifest.get("input_schema_version") != input_schema.get("schema_version"):
            errors.append("manifest and input schema versions do not match")
        try:
            datetime.fromisoformat(str(manifest.get("created_at_utc", "")).replace("Z", "+00:00"))
        except ValueError:
            errors.append("manifest created_at_utc is not an ISO-8601 timestamp")
        if any(not isinstance(manifest.get(field), str) or not manifest[field].strip() for field in ("assay_type", "source_citation", "curator_identifier")):
            errors.append("manifest assay/source/curator metadata must be non-empty strings")

    if input_schema:
        if input_schema.get("schema_version") != "external-validation-input-v1":
            errors.append("unsupported input schema version")
        required_fields = input_schema.get("required_fields")
        if not isinstance(required_fields, list) or not MINIMUM_CASE_FIELDS.issubset(set(required_fields)):
            errors.append("input schema must require all minimum input fields")
        if input_schema.get("case_id_pattern") != config.get("case_id_pattern"):
            errors.append("input schema must declare the configured anonymous case-ID pattern")

    cases: list[dict[str, Any]] = []
    cases_path = root / cases_rel
    if cases_path.is_file():
        try:
            for line_number, line in enumerate(cases_path.read_text(encoding="utf-8").splitlines(), start=1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    errors.append(f"invalid JSONL record at line {line_number}")
                    continue
                if not isinstance(record, dict):
                    errors.append(f"case record at line {line_number} is not an object")
                    continue
                cases.append(record)
                _scan_sensitive_keys(record, cases_rel, prohibited_columns, errors)
                _scan_sensitive_values(record, cases_rel, prohibited_values, errors)
                case_id = record.get("case_id")
                if not isinstance(case_id, str) or not case_id_pattern.fullmatch(case_id):
                    errors.append(f"non-anonymous case ID at line {line_number}")
                required = input_schema.get("required_fields", [])
                if isinstance(required, list) and any(field not in record for field in required):
                    errors.append(f"case record misses required input fields at line {line_number}")
        except (OSError, UnicodeError):
            errors.append("owner-facing cases file is unreadable")

    ids = [record.get("case_id") for record in cases]
    if len(ids) != len(set(ids)):
        errors.append("case IDs must be unique")
    if ids != sorted(ids):
        errors.append("case records must be ordered by neutral case ID")
    if manifest and isinstance(manifest.get("case_count"), int) and manifest["case_count"] != len(cases):
        errors.append("manifest case_count does not match owner input records")

    for relative, path in sorted(relative_files.items()):
        if relative in {MANIFEST_NAME, input_schema_rel, cases_rel} or relative == CHECKSUMS_NAME:
            continue
        if path.suffix.casefold() not in {".csv", ".tsv"}:
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                errors.append(f"additional owner input is not valid JSON: {relative}")
                continue
            _scan_sensitive_keys(value, relative, prohibited_columns, errors)
            _scan_sensitive_values(value, relative, prohibited_values, errors)
        else:
            delimiter = "\t" if path.suffix.casefold() == ".tsv" else ","
            try:
                with path.open("r", encoding="utf-8-sig", newline="") as stream:
                    reader = csv.DictReader(stream, delimiter=delimiter)
                    headers = reader.fieldnames or []
                    for header in headers:
                        if _contains_token(header, prohibited_columns):
                            errors.append(f"prohibited tabular column in {relative}")
                            break
                    for row in reader:
                        _scan_sensitive_values(row, relative, prohibited_values, errors)
            except (OSError, UnicodeError, csv.Error):
                errors.append(f"tabular owner input is unreadable: {relative}")

    if input_schema_rel in relative_files:
        if manifest.get("input_schema_sha256") != _sha256(relative_files[input_schema_rel]):
            errors.append("input schema SHA-256 does not match manifest")

    checksums_path = root / CHECKSUMS_NAME
    checksums, checksum_errors = _read_checksums(checksums_path)
    errors.extend(checksum_errors)
    expected_checksum_paths = set(relative_files) - {CHECKSUMS_NAME}
    if set(checksums) != expected_checksum_paths:
        errors.append("checksum manifest does not cover exactly the owner-facing files")
    for relative, expected_digest in checksums.items():
        path = root / Path(*PurePosixPath(relative).parts)
        if not path.is_file() or path.is_symlink():
            errors.append(f"checksummed file is missing or unsafe: {relative}")
        elif _sha256(path) != expected_digest:
            errors.append(f"SHA-256 mismatch: {relative}")

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package_root", type=Path, help="owner-facing receipt directory")
    parser.add_argument("--policy", type=Path, default=POLICY_PATH, help="access-policy JSON")
    args = parser.parse_args(argv)

    errors = validate_package(args.package_root, args.policy)
    if errors:
        print(f"NO_PEEKING_VALIDATION=FAIL ({len(errors)} issue(s))")
        for error in errors:
            print(f"- {error}")
        return 2
    print("NO_PEEKING_VALIDATION=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
