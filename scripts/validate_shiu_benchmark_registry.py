"""Validate the frozen Shiu public benchmark registry against its XLSX source.

The validator intentionally uses only the Python standard library for XLSX
reading. PyYAML is the only project dependency needed to read the registry.
It checks the source checksum, worksheet row locators, exact FlyWire IDs,
source labels, split coverage, and target-group leakage before a benchmark is
used for a paper-facing evaluation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


NS = {
    "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pr": "http://schemas.openxmlformats.org/package/2006/relationships",
}
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _column_number(reference: str) -> int:
    letters = "".join(char for char in reference if char.isalpha())
    number = 0
    for char in letters:
        number = number * 26 + ord(char.upper()) - ord("A") + 1
    return number - 1


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _portable_path(path: Path) -> str:
    """Return portable metadata instead of a machine-local checkout path."""

    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.name


def _workbook_rows(path: Path, worksheet_name: str) -> dict[int, dict[int, str]]:
    with zipfile.ZipFile(path) as archive:
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        relationship_map = {
            item.attrib["Id"]: item.attrib["Target"]
            for item in relationships
        }
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            shared_root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for shared_item in shared_root.findall("m:si", NS):
                shared_strings.append(
                    "".join(text.text or "" for text in shared_item.iter(f"{{{NS['m']}}}t"))
                )

        target_path: str | None = None
        sheets = workbook.find("m:sheets", NS)
        for sheet in () if sheets is None else sheets:
            if sheet.attrib.get("name") != worksheet_name:
                continue
            relation_id = sheet.attrib[f"{{{REL_NS}}}id"]
            target_path = relationship_map[relation_id].lstrip("/")
            if not target_path.startswith("xl/"):
                target_path = f"xl/{target_path}"
            break
        if target_path is None:
            raise ValueError(f"worksheet not found: {worksheet_name}")

        sheet_root = ET.fromstring(archive.read(target_path))
        rows: dict[int, dict[int, str]] = {}
        for row in sheet_root.findall(".//m:sheetData/m:row", NS):
            row_number = int(row.attrib["r"])
            values: dict[int, str] = {}
            for cell in row.findall("m:c", NS):
                value = cell.find("m:v", NS)
                if cell.attrib.get("t") == "inlineStr":
                    text = "".join(item.text or "" for item in cell.findall(".//m:t", NS))
                elif value is not None:
                    text = value.text or ""
                    if cell.attrib.get("t") == "s":
                        text = shared_strings[int(text)]
                else:
                    continue
                values[_column_number(cell.attrib.get("r", ""))] = text.strip()
            rows[row_number] = values
        return rows


def _find_header_column(
    rows: dict[int, dict[int, str]],
    source_row: int,
    column_name: str,
) -> tuple[int, int]:
    """Find the nearest section header containing the declared column name.

    The Shiu workbook stores multiple experiments in one worksheet. Their
    headers are repeated and the label column moves between sections, so a
    fixed Excel column is not a valid source locator.
    """

    wanted = str(column_name).strip()
    if not wanted:
        raise ValueError("source table_column is required")
    for header_row in range(int(source_row) - 1, 0, -1):
        row = rows.get(header_row, {})
        matches = [column for column, value in row.items() if str(value).strip() == wanted]
        if len(matches) == 1:
            return header_row, matches[0]
        if len(matches) > 1:
            raise ValueError(
                f"ambiguous source column {wanted!r} in worksheet row {header_row}"
            )
    raise ValueError(
        f"source column {wanted!r} has no preceding header for worksheet row {source_row}"
    )


def _load_registry(path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ImportError as error:  # pragma: no cover - environment diagnostic
        raise RuntimeError("PyYAML is required to load the benchmark registry") from error
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("benchmark registry must be a YAML mapping")
    return payload


def _validate_v2_table3(
    payload: dict[str, Any],
    registry_path: Path,
    workbook_path: Path,
    rows: dict[int, dict[int, str]],
    actual_hash: str,
) -> dict[str, Any]:
    """Validate the v2 Table 3 registry without applying the v1 schema.

    v1 is an ID/label registry for several sections of the supplementary
    workbook.  v2 is a Table 3 response-presence registry: column A contains
    the cell type and column B contains the published aggregate response
    fraction.  Keeping this branch explicit prevents a v1-only validator from
    silently accepting or misinterpreting the v2 contract.
    """

    source = payload["source"]
    worksheet = str(source.get("worksheet", "")).strip()
    if not worksheet:
        raise ValueError("v2 registry source.worksheet is required")
    required_case_fields = (payload.get("evaluation_contract") or {}).get(
        "required_case_fields", ()
    )
    if not isinstance(required_case_fields, list):
        raise ValueError("evaluation_contract.required_case_fields must be a list")
    cases = payload.get("cases", [])
    if not isinstance(cases, list):
        raise ValueError("registry cases must be a list")

    seen_ids: set[str] = set()
    seen_groups: set[str] = set()
    checked_cases: list[dict[str, Any]] = []
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("each benchmark case must be a mapping")
        case_id = str(case.get("case_id", ""))
        metadata = case.get("metadata")
        if not case_id or not isinstance(metadata, dict):
            raise ValueError(f"{case_id or '<missing>'}: metadata is required")
        missing_context = [
            str(field)
            for field in required_case_fields
            if metadata.get(str(field)) in (None, "")
        ]
        if missing_context:
            raise ValueError(
                f"{case_id}: required evaluation context is missing: "
                + ", ".join(missing_context)
            )
        if case_id in seen_ids:
            raise ValueError(f"duplicate case_id: {case_id}")
        seen_ids.add(case_id)
        source_row = int(metadata.get("source_excel_row", 0))
        row = rows.get(source_row)
        if row is None:
            raise ValueError(f"{case_id}: source Excel row not found: {source_row}")
        cell_type = str(metadata.get("cell_type", "")).strip()
        if not cell_type or row.get(0) != cell_type:
            raise ValueError(
                f"{case_id}: cell type mismatch at row {source_row}: "
                f"registry={cell_type!r}, source={row.get(0)!r}"
            )
        try:
            observed = float(row.get(1, ""))
            declared_observed = float(metadata.get("observed_response_fraction"))
        except (TypeError, ValueError) as error:
            raise ValueError(f"{case_id}: observed response is not numeric") from error
        if observed != declared_observed:
            raise ValueError(
                f"{case_id}: observed response mismatch at row {source_row}: "
                f"registry={declared_observed}, source={observed}"
            )
        expected_label = "positive" if observed > 0.0 else "negative"
        if str(case.get("reference_label", "")).lower() != expected_label:
            raise ValueError(f"{case_id}: reference_label does not match Table 3 response")
        group = str(metadata.get("case_group", "")).strip()
        if group:
            if group in seen_groups:
                raise ValueError(f"target group appears more than once: {group}")
            seen_groups.add(group)
        checked_cases.append(
            {
                "case_id": case_id,
                "source_excel_row": source_row,
                "cell_type": cell_type,
                "reference_label": expected_label,
                "observed_response_fraction": observed,
                "source_section": str(metadata.get("source_section", "")),
                "assay": str(metadata.get("assay", "")),
                "stimulus": str(metadata.get("stimulus", "")),
                "intervention": str(metadata.get("intervention", "")),
                "readout": str(metadata.get("readout", "")),
            }
        )

    split = payload.get("split") or {}
    development = {str(item) for item in split.get("development_case_ids", [])}
    held_out = {str(item) for item in split.get("held_out_case_ids", [])}
    case_ids = {item["case_id"] for item in checked_cases}
    if development & held_out:
        raise ValueError("development and held-out splits overlap")
    if development | held_out != case_ids:
        raise ValueError("development and held-out splits do not cover all cases")
    for name, selected in (("development", development), ("held_out", held_out)):
        labels = {item["reference_label"] for item in checked_cases if item["case_id"] in selected}
        if labels != {"positive", "negative"}:
            raise ValueError(f"{name} split does not contain both labels")
    if len(checked_cases) < 20:
        raise ValueError("benchmark must contain at least 20 cases")

    return {
        "status": "READY",
        "registry": _portable_path(registry_path),
        "workbook": _portable_path(workbook_path),
        "artifact_sha256": actual_hash,
        "worksheet": worksheet,
        "schema": "v2_table3_response_presence",
        "case_count": len(checked_cases),
        "development_case_count": len(development),
        "held_out_case_count": len(held_out),
        "positive_count": sum(item["reference_label"] == "positive" for item in checked_cases),
        "negative_count": sum(item["reference_label"] == "negative" for item in checked_cases),
        "checked_cases": checked_cases,
    }


def validate(registry_path: Path, workbook_path: Path) -> dict[str, Any]:
    payload = _load_registry(registry_path)
    source = payload.get("source")
    if not isinstance(source, dict):
        raise ValueError("registry source must be a mapping")
    expected_hash = str(source.get("artifact_sha256", "")).upper()
    actual_hash = _sha256(workbook_path)
    if expected_hash != actual_hash:
        raise ValueError(
            f"source checksum mismatch: registry={expected_hash}, workbook={actual_hash}"
        )

    worksheet = str(source.get("worksheet", "")).strip()
    evaluation_contract = payload.get("evaluation_contract") or {}
    required_case_fields = evaluation_contract.get("required_case_fields", ())
    if not isinstance(required_case_fields, list):
        raise ValueError("evaluation_contract.required_case_fields must be a list")
    rows = _workbook_rows(workbook_path, worksheet)
    cases = payload.get("cases", [])
    if not isinstance(cases, list):
        raise ValueError("registry cases must be a list")

    if str(payload.get("protocol_id", "")).endswith("v2-table3"):
        return _validate_v2_table3(payload, registry_path, workbook_path, rows, actual_hash)

    table_column = str(source.get("table_column", "")).strip()
    if not table_column:
        raise ValueError("registry source.table_column is required")

    seen_ids: set[str] = set()
    seen_groups: dict[str, str] = {}
    checked_cases: list[dict[str, Any]] = []
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("each benchmark case must be a mapping")
        case_id = str(case.get("case_id", ""))
        metadata = case.get("metadata")
        if not isinstance(metadata, dict):
            raise ValueError(f"{case_id}: metadata is required")
        missing_context = [
            str(field)
            for field in required_case_fields
            if metadata.get(str(field)) in (None, "")
        ]
        if missing_context:
            raise ValueError(
                f"{case_id}: required evaluation context is missing: "
                + ", ".join(missing_context)
            )
        section = str(metadata.get("source_section", "")).strip()
        condition = str(case.get("condition", "")).strip()
        if section and ":" in condition and condition.split(":", 1)[0] != section:
            raise ValueError(
                f"{case_id}: condition section does not match source_section: "
                f"condition={condition}, source_section={section}"
            )
        if case_id in seen_ids:
            raise ValueError(f"duplicate case_id: {case_id}")
        seen_ids.add(case_id)
        flywire_id = str(metadata.get("flywire_id", ""))
        source_row = int(metadata.get("source_excel_row", 0))
        source_label = int(metadata.get("source_label_numeric", -1))
        row = rows.get(source_row)
        if row is None:
            raise ValueError(f"{case_id}: source Excel row not found: {source_row}")
        if row.get(0) != flywire_id:
            raise ValueError(
                f"{case_id}: FlyWire ID mismatch at row {source_row}: "
                f"registry={flywire_id}, source={row.get(0)}"
            )
        if row.get(1, "") != str(metadata.get("neuron_name", "")):
            raise ValueError(f"{case_id}: neuron name mismatch at row {source_row}")
        header_row, label_column = _find_header_column(rows, source_row, table_column)
        declared_header_row = metadata.get("source_header_row")
        if declared_header_row is not None and int(declared_header_row) != header_row:
            raise ValueError(
                f"{case_id}: source header row mismatch: "
                f"registry={declared_header_row}, detected={header_row}"
            )
        if row.get(label_column) != str(source_label):
            raise ValueError(
                f"{case_id}: source label mismatch at row {source_row}: "
                f"registry={source_label}, source={row.get(label_column)} "
                f"(header_row={header_row}, column={label_column})"
            )
        expected_label = "positive" if source_label == 1 else "negative"
        if str(case.get("reference_label", "")).lower() != expected_label:
            raise ValueError(f"{case_id}: reference_label does not match source label")
        group = str(metadata.get("case_group", "")).strip()
        if group:
            previous = seen_groups.setdefault(group, case_id)
            if previous != case_id:
                raise ValueError(f"target group appears more than once: {group}")
        checked_cases.append(
            {
                "case_id": case_id,
                "source_excel_row": source_row,
                "flywire_id": flywire_id,
                "reference_label": expected_label,
                "source_header_row": header_row,
                "source_label_column": label_column,
                "source_section": section,
                "assay": str(metadata.get("assay", "")),
                "stimulus": str(metadata.get("stimulus", "")),
                "intervention": str(metadata.get("intervention", "")),
                "readout": str(metadata.get("readout", "")),
            }
        )

    split = payload.get("split") or {}
    development = {str(item) for item in split.get("development_case_ids", [])}
    held_out = {str(item) for item in split.get("held_out_case_ids", [])}
    case_ids = {item["case_id"] for item in checked_cases}
    if development & held_out:
        raise ValueError("development and held-out splits overlap")
    if development | held_out != case_ids:
        raise ValueError("development and held-out splits do not cover all cases")
    for name, selected in (("development", development), ("held_out", held_out)):
        labels = {item["reference_label"] for item in checked_cases if item["case_id"] in selected}
        if labels != {"positive", "negative"}:
            raise ValueError(f"{name} split does not contain both labels")
    if len(checked_cases) < 20:
        raise ValueError("benchmark must contain at least 20 cases")

    return {
        "status": "READY",
        "registry": _portable_path(registry_path),
        "workbook": _portable_path(workbook_path),
        "artifact_sha256": actual_hash,
        "worksheet": worksheet,
        "case_count": len(checked_cases),
        "development_case_count": len(development),
        "held_out_case_count": len(held_out),
        "positive_count": sum(item["reference_label"] == "positive" for item in checked_cases),
        "negative_count": sum(item["reference_label"] == "negative" for item in checked_cases),
        "checked_cases": checked_cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--workbook", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate(args.registry.resolve(), args.workbook.resolve())
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
