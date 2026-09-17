#!/usr/bin/env python
"""Build a versioned Shiu Table 3 public-data benchmark registry.

The generated registry is a retrospective model-vs-observed-response benchmark.
It intentionally stores the source row and the reported aggregate response;
it does not fabricate per-fly observations or call a zero response proof of
biological absence.  The source workbook must already be present locally and
its SHA-256 is recorded in the output.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from validate_shiu_benchmark_registry import _workbook_rows  # noqa: E402


WORKSHEET = "Sup Table 3 Predicted MN9 vs. o"
LOCATOR = "https://www.nature.com/articles/s41586-024-07763-9"
ARTIFACT_LOCATOR = (
    "https://media.springernature.com/original/springer-static/"
    "esm/art%3A10.1038%2Fs41586-024-07763-9/MediaObjects/41586_2024_7763_MOESM2_ESM.xlsx"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _number(value: str, *, default: float | None = None) -> float | None:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default


def _header_row(rows: dict[int, dict[int, str]]) -> int:
    for number, row in sorted(rows.items()):
        if row.get(1) == "MN9 Optogenetic Activation Rate" and row.get(4) == "10 Hz MN9_Left":
            return number
    raise ValueError("Table 3 header was not found")


def _build_cases(rows: dict[int, dict[int, str]], header: int) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for row_number, row in sorted(rows.items()):
        if row_number <= header or not row.get(0) or not row.get(1):
            continue
        observed = _number(row.get(1, ""))
        if observed is None:
            continue
        cell_type = row[0].strip()
        case_id = f"shiu_table3_row_{row_number:03d}"
        model_rates = {
            frequency: {
                "left": _number(row.get(start, "")),
                "right": _number(row.get(start + 1, "")),
            }
            for frequency, start in (
                ("10", 4), ("20", 6), ("30", 8), ("40", 10),
                ("50", 12), ("100", 14), ("150", 16), ("200", 18),
            )
        }
        model_sd = {
            frequency: {
                "left": _number(row.get(start, "")),
                "right": _number(row.get(start + 1, "")),
            }
            for frequency, start in (
                ("10", 21), ("20", 23), ("30", 25), ("40", 27),
                ("50", 29), ("100", 31), ("150", 33), ("200", 35),
            )
        }
        positive = observed > 0.0
        cases.append(
            {
                "case_id": case_id,
                "condition": f"mn9_optogenetic_activation:{cell_type}",
                "reference_label": "positive" if positive else "negative",
                "source": {
                    "locator": LOCATOR,
                    "artifact_locator": ARTIFACT_LOCATOR,
                    "label_basis": "Table 3 observed max activation rate > 0",
                    "label_semantics": (
                        "positive means the published aggregate reports at least one response; "
                        "it is not a significance test and not a causal absence label"
                    ),
                },
                "metadata": {
                    "source_section": "mn9_optogenetic_activation",
                    "assay": "proboscis_extension_observed_rate",
                    "stimulus": "cell_type_optogenetic_activation",
                    "intervention": "activation",
                    "readout": "published_observed_activation_rate",
                    "source_worksheet": WORKSHEET,
                    "source_excel_row": row_number,
                    "cell_type": cell_type,
                    "source_identifier": cell_type,
                    "driver_line_info": row.get(2, ""),
                    "observed_response_fraction": observed,
                    "model_mn9_rates_hz": model_rates,
                    "model_mn9_sd_hz": model_sd,
                    "shortest_path": _number(row.get(3, "")),
                    "case_group": f"source_row:{row_number}",
                    "upstream_exposure": "used_in_shiu_model_publication",
                },
            }
        )
    return cases


def _split(cases: list[dict[str, Any]], seed: int, held_out_fraction: float) -> tuple[list[str], list[str]]:
    if not 0 < held_out_fraction < 1:
        raise ValueError("held-out fraction must be between zero and one")
    rng = random.Random(seed)
    positives = [case for case in cases if case["reference_label"] == "positive"]
    negatives = [case for case in cases if case["reference_label"] == "negative"]
    rng.shuffle(positives)
    rng.shuffle(negatives)
    def take(values: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        count = max(1, round(len(values) * held_out_fraction))
        count = min(count, len(values) - 1)
        return values[count:], values[:count]
    development_pos, heldout_pos = take(positives)
    development_neg, heldout_neg = take(negatives)
    development = [case["case_id"] for case in development_pos + development_neg]
    held_out = [case["case_id"] for case in heldout_pos + heldout_neg]
    rng.shuffle(development)
    rng.shuffle(held_out)
    return development, held_out


def build_registry(
    workbook: Path,
    *,
    split_seed: int = 17092026,
    frozen_at: str = "",
    freeze_commit: str | None = None,
) -> dict[str, Any]:
    rows = _workbook_rows(workbook, WORKSHEET)
    header = _header_row(rows)
    cases = _build_cases(rows, header)
    if len(cases) < 100:
        raise ValueError(f"expected at least 100 Table 3 rows, found {len(cases)}")
    development, held_out = _split(cases, split_seed, 0.30)
    return {
        "protocol_id": "shiu-public-retrospective-v2-table3",
        "source": {
            "citation": "Shiu et al. (2024), Nature, Supplementary Table 3",
            "doi": "10.1038/s41586-024-07763-9",
            "locator": LOCATOR,
            "artifact_locator": ARTIFACT_LOCATOR,
            "artifact_sha256": _sha256(workbook),
            "worksheet": WORKSHEET,
            "status": "public_artifact_verified_locally",
        },
        "evaluation_contract": {
            "status": "RETROSPECTIVE_PUBLIC_DATA",
            "review_status": "COMPUTATIONAL_AUDIT_ONLY_HUMAN_REVIEW_PENDING",
            "target": "published_observed_activation_rate",
            "primary_endpoint": "precision_at_k",
            "bootstrap_samples": 10000,
            "required_case_fields": [
                "source_section", "assay", "stimulus", "intervention", "readout",
                "source_excel_row", "case_group",
            ],
            "unsupported_cases_must_be_reported_as": "unassessable",
        },
        "selection_rule": (
            "Use every numeric row in Table 3 with one published cell type and one "
            "observed aggregate activation rate; do not expand cell types, driver lines, "
            "frequencies, or hemispheres into independent biological cases."
        ),
        "frozen_at": str(frozen_at),
        "min_case_count": 100,
        "precision_at_k": 5,
        "freeze_status": "FROZEN" if frozen_at else "DRAFT",
        "label_policy": (
            "reference_label=positive iff the published observed aggregate activation rate is >0; "
            "this is a retrospective response-presence label, not a significance or causal label"
        ),
        "freeze_commit": freeze_commit,
        "split": {
            "seed": split_seed,
            "method": "stratified_source_row_split",
            "development_case_ids": development,
            "held_out_case_ids": held_out,
        },
        "notes": [
            "The source model and this public experiment were reported together; this is not upstream-independent validation.",
            "The 106 cases include a highly imbalanced response-presence label; report the exact prevalence.",
            "Thresholds and parameters must be calibrated on development cases only.",
            "The generated registry is a draft until its split and row mapping are reviewed and frozen.",
        ],
        "cases": cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--split-seed", type=int, default=17092026)
    parser.add_argument(
        "--frozen-at",
        default="",
        help="optional timestamp after the computational split audit; does not imply biological review",
    )
    parser.add_argument("--freeze-commit")
    args = parser.parse_args()
    registry = build_registry(
        args.workbook.resolve(),
        split_seed=args.split_seed,
        frozen_at=args.frozen_at,
        freeze_commit=args.freeze_commit,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(args.output.resolve()),
        "case_count": len(registry["cases"]),
        "positive_count": sum(case["reference_label"] == "positive" for case in registry["cases"]),
        "negative_count": sum(case["reference_label"] == "negative" for case in registry["cases"]),
        "development_case_count": len(registry["split"]["development_case_ids"]),
        "held_out_case_count": len(registry["split"]["held_out_case_ids"]),
        "status": registry["freeze_status"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
