#!/usr/bin/env python
"""Build a human-review packet for the frozen v2 public benchmark.

The packet copies source-grounded context into CSV/Markdown forms and leaves
all scientific decisions blank. It never infers biological comparability or
creates reviewer sign-off.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from drosophila_pd.workbench import BenchmarkProtocol  # noqa: E402


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("registry must be a JSON object")
    return value


def build_packet(registry_path: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    registry = _load(registry_path)
    protocol = BenchmarkProtocol.from_dict(registry)
    rows = registry.get("cases")
    if not isinstance(rows, list) or not rows:
        raise ValueError("registry cases must be a non-empty list")
    development = set((registry.get("split") or {}).get("development_case_ids", []))
    held_out = set((registry.get("split") or {}).get("held_out_case_ids", []))
    packet_rows: list[dict[str, str]] = []
    for case in sorted(rows, key=lambda item: int(item["metadata"]["source_excel_row"])):
        metadata = case["metadata"]
        case_id = str(case["case_id"])
        split = "development" if case_id in development else "held_out" if case_id in held_out else "unknown"
        packet_rows.append(
            {
                "case_id": case_id,
                "split": split,
                "source_excel_row": str(metadata.get("source_excel_row", "")),
                "cell_type": str(metadata.get("cell_type", "")),
                "reference_label": str(case.get("reference_label", "")),
                "observed_response_fraction": str(metadata.get("observed_response_fraction", "")),
                "source_section": str(metadata.get("source_section", "")),
                "assay": str(metadata.get("assay", "")),
                "stimulus": str(metadata.get("stimulus", "")),
                "intervention": str(metadata.get("intervention", "")),
                "readout": str(metadata.get("readout", "")),
                "driver_line_info": str(metadata.get("driver_line_info", "")),
                "mapping_review_status": "PENDING",
                "comparability_review_status": "PENDING",
                "reviewer_1": "",
                "reviewer_2": "",
                "reviewer_notes": "",
            }
        )
    summary = {
        "packet_schema": "workbench-scientific-review-packet-v1",
        "status": "PENDING_HUMAN_REVIEW",
        "registry": registry_path.relative_to(ROOT).as_posix(),
        "protocol_id": registry.get("protocol_id"),
        "protocol_hash": protocol.protocol_hash,
        "artifact_sha256": (registry.get("source") or {}).get("artifact_sha256"),
        "case_count": len(packet_rows),
        "development_case_count": sum(row["split"] == "development" for row in packet_rows),
        "held_out_case_count": sum(row["split"] == "held_out" for row in packet_rows),
        "positive_count": sum(row["reference_label"] == "positive" for row in packet_rows),
        "negative_count": sum(row["reference_label"] == "negative" for row in packet_rows),
        "review_decisions_are_not_inferred": True,
    }
    return summary, packet_rows


def write_packet(
    summary: dict[str, Any],
    rows: list[dict[str, str]],
    csv_path: Path,
    markdown_path: Path,
    json_path: Path,
) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0])
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    lines = [
        "# Shiu v2 scientific review packet",
        "",
        "Status: `PENDING_HUMAN_REVIEW`",
        "",
        "This packet is source-grounded context for two human reviewers. Blank review fields are intentional; no mapping or assay comparability decision was inferred.",
        "",
        f"- Protocol: `{summary['protocol_id']}`",
        f"- Protocol hash: `{summary['protocol_hash']}`",
        f"- Source artifact SHA256: `{summary['artifact_sha256']}`",
        f"- Cases: `{summary['case_count']}` ({summary['development_case_count']} development, {summary['held_out_case_count']} held-out)",
        f"- Labels: `{summary['positive_count']}` positive, `{summary['negative_count']}` negative",
        "",
        "## Required reviewer decisions",
        "",
        "For every row, reviewers should independently record whether the source assay/readout is comparable to the declared Workbench score, whether the case is assessable, and any mapping limitation. Do not change labels, split membership, thresholds, or candidate scores in this packet.",
        "",
        f"The row-level CSV is at `{csv_path.relative_to(ROOT).as_posix()}`.",
    ]
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    json_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=ROOT / "configs/workbench/shiu_public_benchmark_v2.json")
    parser.add_argument("--csv", type=Path, default=ROOT / "reports/workbench/shiu_v2_scientific_review_packet.csv")
    parser.add_argument("--markdown", type=Path, default=ROOT / "reports/workbench/shiu_v2_scientific_review_packet.md")
    parser.add_argument("--json", type=Path, default=ROOT / "reports/workbench/shiu_v2_scientific_review_packet.json")
    args = parser.parse_args()
    summary, rows = build_packet(args.registry.resolve())
    write_packet(summary, rows, args.csv.resolve(), args.markdown.resolve(), args.json.resolve())
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
