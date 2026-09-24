#!/usr/bin/env python
"""Run the locked Workbench score ablation on the development split only."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from drosophila_pd.workbench import (  # noqa: E402
    BenchmarkProtocol,
    apply_calibration,
    calibrate_threshold,
    compare_benchmark_systems,
    seeded_random_scores,
)
from drosophila_pd.workbench.score_lock import build_locked_scores  # noqa: E402


def _load_json(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError(f"JSON document must be an object: {path}")
    return value


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and abs(number) != float("inf") else None


def _load_mapping(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"mapping CSV is empty: {path}")
    return rows


def _load_rewire_scores(path: Path) -> dict[str, float]:
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = csv.DictReader(handle)
            scores: dict[str, float] = {}
            for row in rows:
                case_id = str(row.get("case_id", "")).strip()
                score = _finite(row.get("score_hz"))
                if not case_id or score is None:
                    raise ValueError(f"invalid rewire score row in {path}: {row}")
                scores[case_id] = score
            return scores
    raw = _load_json(path)
    values = raw.get("scores", raw)
    if not isinstance(values, Mapping):
        raise ValueError("rewire score document must be keyed by case_id or contain scores")
    scores = {}
    for case_id, value in values.items():
        score = _finite(value)
        if score is None:
            raise ValueError(f"rewire score is not finite: {case_id}")
        scores[str(case_id)] = score
    return scores


def _portable(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.name


def _write_score_table(path: Path, rows: list[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "case_id",
        "simulation_effect_hz",
        "published_uncertainty_mean_hz",
        "uncertainty_adjusted_score",
        "evidence_gate",
        "capability_gate",
        "full_workbench_score",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row[field] for field in fields})


def run(
    *,
    registry_path: Path,
    mapping_path: Path,
    rewire_scores_path: Path,
    score_spec_path: Path,
    output_path: Path,
    random_seed: int = 17092026,
) -> dict[str, Any]:
    protocol = BenchmarkProtocol.from_dict(_load_json(registry_path))
    score_spec = _load_json(score_spec_path)
    built = build_locked_scores(
        protocol,
        _load_mapping(mapping_path),
        _load_rewire_scores(rewire_scores_path),
        score_spec,
    )
    scores = dict(built["systems"])
    scores["random_reference"] = seeded_random_scores(
        list(protocol.development_case_ids), seed=int(random_seed)
    )

    calibrations: dict[str, Any] = {}
    predictions: dict[str, Mapping[str, Any]] = {}
    predictions_by_system: dict[str, Mapping[str, Any]] = {}
    for name, system_scores in scores.items():
        calibration = calibrate_threshold(protocol, system_scores)
        calibrations[name] = calibration
        predictions_by_system[name] = apply_calibration(
            protocol, system_scores, calibration, evaluation_split="development"
        )

    comparison = compare_benchmark_systems(
        protocol,
        predictions_by_system,
        evaluation_split="development",
    )
    metrics = comparison["metrics"]
    result = {
        "report_version": 1,
        "status": "DEVELOPMENT_ABLATION_COMPLETE",
        "score_lock": {
            "score_lock_id": score_spec.get("score_lock_id"),
            "score_lock_version": score_spec.get("score_lock_version"),
            "protocol_hash": protocol.protocol_hash,
            "spec_path": _portable(score_spec_path),
        },
        "protocol_hash": protocol.protocol_hash,
        "source_registry": _portable(registry_path),
        "source_mapping": _portable(mapping_path),
        "source_rewire_scores": _portable(rewire_scores_path),
        "evaluation_split": "development",
        "development_case_count": len(protocol.development_case_ids),
        "held_out_case_count": len(protocol.held_out_case_ids),
        "held_out_used_for_score_selection": False,
        "score_construction_audit": built["audit"],
        "score_table": built["rows"],
        "calibration_policy": "Each threshold is fitted on development labels and evaluated in-sample; ranking metrics are the primary ablation readout.",
        "calibrations": calibrations,
        "comparison": comparison,
        "primary_metrics": {
            name: {
                "precision_at_k": report.get("precision_at_k"),
                "average_precision": report.get("average_precision"),
                "coverage": report.get("coverage"),
            }
            for name, report in metrics.items()
        },
        "interpretation": {
            "evidence_and_capability": "These gates are required by the locked score, but their value is not identifiable in this registry because all 106 cases pass both gates.",
            "random_reference": "Seeded random ranking is a negative reference, not a tuned baseline.",
            "scientific_scope": "Development-only retrospective ranking ablation. It is not a held-out claim, biological validation, or wet-lab result.",
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_score_table(output_path.with_name("development_score_table.csv"), built["rows"])
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=ROOT / "configs/workbench/shiu_public_benchmark_v2.json")
    parser.add_argument("--mapping", type=Path, default=ROOT / "configs/workbench/shiu_v2_flywire630_mapping.csv")
    parser.add_argument("--rewire-scores", type=Path, required=True)
    parser.add_argument("--score-spec", type=Path, default=ROOT / "configs/workbench/shiu_workbench_score_v1.json")
    parser.add_argument("--random-seed", type=int, default=17092026)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(
        registry_path=args.registry.resolve(),
        mapping_path=args.mapping.resolve(),
        rewire_scores_path=args.rewire_scores.resolve(),
        score_spec_path=args.score_spec.resolve(),
        output_path=args.output.resolve(),
        random_seed=args.random_seed,
    )
    print(json.dumps({
        "status": result["status"],
        "output": _portable(args.output),
        "development_case_count": result["development_case_count"],
        "protocol_hash": result["protocol_hash"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
