#!/usr/bin/env python
"""Freeze and audit a completed Shiu v2 rewired-LIF batch.

The freeze is deliberately separate from the simulation runner.  It records
the exact 106 case outputs, hashes every file in the batch, audits zero-score
cases, and records the source hashes used by the benchmark.  A zero score is
treated as a computationally silent readout under this protocol; it is never
interpreted as biological absence.
"""

from __future__ import annotations

import argparse
import csv
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


READOUT_IDS = ("720575940645521262", "720575940660219265")
EXPECTED_BATCH_STATUS = "COMPLETE"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError(f"JSON document must be an object: {path}")
    return value


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _finite_number(value: Any, *, label: str) -> float:
    number = float(value)
    if number != number or abs(number) == float("inf"):
        raise ValueError(f"{label} is not finite")
    return number


def _metrics(path: Path, *, case_id: str, state: str) -> dict[str, Any]:
    document = _load_json(path)
    if str(document.get("status", "")).upper() != "PASS":
        raise ValueError(f"{case_id} {state} metrics are not PASS: {path}")
    metrics = document.get("metrics")
    if not isinstance(metrics, Mapping):
        raise ValueError(f"{case_id} {state} metrics has no metrics object: {path}")
    rates = metrics.get("readout_rates_hz")
    if not isinstance(rates, Mapping):
        raise ValueError(f"{case_id} {state} metrics has no readout_rates_hz: {path}")
    readout_rates = {
        readout_id: _finite_number(rates[readout_id], label=f"{case_id} {state} {readout_id}")
        for readout_id in READOUT_IDS
    }
    active = metrics.get("active_neurons_per_trial", {})
    if not isinstance(active, Mapping):
        active = {}
    return {
        "spike_count_total": int(metrics.get("spike_count_total", 0)),
        "trial_count": int(metrics.get("trial_count", 0)),
        "active_neurons_mean": _finite_number(active.get("mean", 0.0), label=f"{case_id} {state} active mean"),
        "readout_rates_hz": readout_rates,
        "readout_rate_mean_hz": sum(readout_rates.values()) / len(readout_rates),
        "metrics_sha256": _sha256(path),
        "status_sha256": _sha256(path.parent / "status.json"),
    }


def _relative_files(root: Path) -> list[Path]:
    return sorted(
        (path for path in root.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(root).as_posix(),
    )


def _case_rows(batch_root: Path, summary: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    scores = summary.get("scores")
    if not isinstance(scores, Mapping):
        raise ValueError("batch summary scores must be an object")
    rows: list[dict[str, Any]] = []
    zero_rows: list[dict[str, Any]] = []
    for case_id in sorted((str(key) for key in scores), key=lambda value: int(value.rsplit("_", 1)[-1])):
        case_root = batch_root / case_id
        if not case_root.is_dir():
            raise ValueError(f"missing case directory: {case_root}")
        control = _metrics(case_root / "control" / "metrics.json", case_id=case_id, state="control")
        condition = _metrics(case_root / "condition" / "metrics.json", case_id=case_id, state="condition")
        for state in ("control", "condition"):
            status = _load_json(case_root / state / "status.json")
            if str(status.get("status", "")).upper() != "PASS":
                raise ValueError(f"{case_id} {state} status is not PASS")
        score = _finite_number(scores[case_id], label=f"{case_id} score")
        row = {
            "case_id": case_id,
            "score_hz": score,
            "control_readout_rate_hz": control["readout_rate_mean_hz"],
            "condition_readout_rate_hz": condition["readout_rate_mean_hz"],
            "delta_readout_rate_hz": condition["readout_rate_mean_hz"] - control["readout_rate_mean_hz"],
            "control_spike_count_total": control["spike_count_total"],
            "condition_spike_count_total": condition["spike_count_total"],
            "control_active_neurons_mean": control["active_neurons_mean"],
            "condition_active_neurons_mean": condition["active_neurons_mean"],
            "control_readout_rates_hz_json": json.dumps(control["readout_rates_hz"], sort_keys=True),
            "condition_readout_rates_hz_json": json.dumps(condition["readout_rates_hz"], sort_keys=True),
            "control_metrics_sha256": control["metrics_sha256"],
            "condition_metrics_sha256": condition["metrics_sha256"],
            "zero_score": score == 0.0,
        }
        rows.append(row)
        if score == 0.0:
            if condition["readout_rate_mean_hz"] == 0.0 and control["readout_rate_mean_hz"] == 0.0:
                classification = "control_and_condition_silent"
            elif condition["readout_rate_mean_hz"] == 0.0:
                classification = "condition_silent_control_active"
            else:
                classification = "zero_score_with_nonzero_readout"
            zero_rows.append({**row, "zero_score_classification": classification})
    return rows, zero_rows


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("\n", encoding="utf-8")
        return
    fields = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def freeze_batch(
    *,
    batch_root: Path,
    output_root: Path,
    protocol: Path,
    mapping: Path,
    connectivity: Path,
    benchmark_report: Path,
) -> dict[str, Any]:
    batch_root = batch_root.resolve()
    output_root = output_root.resolve()
    source_paths = {
        "protocol": protocol.resolve(),
        "mapping": mapping.resolve(),
        "connectivity": connectivity.resolve(),
        "benchmark_report": benchmark_report.resolve(),
    }
    for path in (batch_root / "batch_summary.json", *source_paths.values()):
        if not path.is_file():
            raise FileNotFoundError(path)
    if output_root == batch_root or batch_root in output_root.parents:
        raise ValueError("freeze output must not be inside the simulation batch root")
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"freeze output must be new and empty: {output_root}")
    summary = _load_json(batch_root / "batch_summary.json")
    if str(summary.get("status", "")).upper() != EXPECTED_BATCH_STATUS:
        raise ValueError(f"batch is not complete: {summary.get('status')!r}")
    rows, zero_rows = _case_rows(batch_root, summary)
    if len(rows) != 106:
        raise ValueError(f"expected exactly 106 frozen cases, found {len(rows)}")

    output_root.mkdir(parents=True, exist_ok=True)
    _write_csv(output_root / "per_case_scores.csv", rows)
    _write_csv(output_root / "zero_score_audit.csv", zero_rows)
    _write_json(
        output_root / "zero_score_audit.json",
        {
            "status": "AUDITED",
            "scientific_interpretation": (
                "A zero score means the declared computational readout produced zero under this "
                "protocol. It is not evidence of biological absence or non-existence of the pathway."
            ),
            "zero_score_count": len(zero_rows),
            "zero_score_case_ids": [row["case_id"] for row in zero_rows],
            "class_counts": {
                label: sum(row["zero_score_classification"] == label for row in zero_rows)
                for label in sorted({row["zero_score_classification"] for row in zero_rows})
            },
            "rows": zero_rows,
        },
    )

    batch_files = []
    for path in _relative_files(batch_root):
        batch_files.append({"path": path.relative_to(batch_root).as_posix(), "sha256": _sha256(path)})
    source_hashes = {
        name: {"path": str(path), "sha256": _sha256(path)}
        for name, path in source_paths.items()
    }
    checksums_path = output_root / "checksums.sha256"
    with checksums_path.open("w", encoding="utf-8", newline="") as handle:
        for item in batch_files:
            handle.write(f"{item['sha256']}  batch/{item['path']}\n")
        for name in sorted(source_hashes):
            handle.write(f"{source_hashes[name]['sha256']}  source/{name}\n")

    manifest = {
        "schema_version": "shiu-v2-rewired-lif-freeze-v1",
        "status": "FROZEN",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "batch_root": str(batch_root),
        "batch_summary_sha256": _sha256(batch_root / "batch_summary.json"),
        "batch_status": summary.get("status"),
        "case_count": len(rows),
        "zero_score_count": len(zero_rows),
        "zero_score_case_ids": [row["case_id"] for row in zero_rows],
        "source_hashes": source_hashes,
        "batch_file_count": len(batch_files),
        "checksums_file": str(checksums_path),
        "checksums_scope": "Every file under batch_root plus the four declared source artifacts; freeze files are excluded to avoid circular checksums.",
        "score_contract": summary.get("score_contract", {}),
        "scientific_scope": (
            "Frozen computational evidence for retrospective benchmark ranking. The output does not "
            "establish biological causality, disease validity, or wet-lab replication."
        ),
        "second_operator": {
            "status": "PENDING_HUMAN_RUN",
            "claim_eligible": False,
            "reason": "The current machine run is an automated computational reproduction; Tuấn must execute the frozen subset from a clean environment for an independent-operator claim.",
        },
    }
    _write_json(output_root / "freeze_manifest.json", manifest)
    (output_root / "README.md").write_text(
        "# Frozen Shiu v2 rewired-LIF batch\n\n"
        "This directory freezes the completed 106-case computational batch.\n\n"
        "- `freeze_manifest.json`: batch identity, source hashes, and scope.\n"
        "- `checksums.sha256`: checksums for every batch file and declared source artifact.\n"
        "- `per_case_scores.csv`: all 106 scores and readout summaries.\n"
        "- `zero_score_audit.csv/json`: explicit audit of score-zero cases.\n\n"
        "A zero score means the declared readout was silent under this computational protocol. It is not a biological absence claim. The second-operator gate remains pending until a separate human runs the frozen subset from a clean environment.\n",
        encoding="utf-8",
    )
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--connectivity", type=Path, required=True)
    parser.add_argument("--benchmark-report", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    manifest = freeze_batch(
        batch_root=args.batch_root,
        output_root=args.output_root,
        protocol=args.protocol,
        mapping=args.mapping,
        connectivity=args.connectivity,
        benchmark_report=args.benchmark_report,
    )
    # Windows PowerShell may expose a legacy cp1252 stdout.  Keep the CLI
    # diagnostic portable; the UTF-8 manifest itself is already on disk.
    print(json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
