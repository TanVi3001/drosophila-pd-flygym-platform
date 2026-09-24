#!/usr/bin/env python
"""Audit readiness for the final held-out evaluation without scoring it.

This command checks that the frozen protocol, locked score, mapping, and
rewired score artifact are complete for the 32 held-out cases. It deliberately
does not call the benchmark evaluator and does not emit held-out metrics.
"""

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

from drosophila_pd.workbench import BenchmarkProtocol  # noqa: E402
from drosophila_pd.workbench.score_lock import build_locked_scores  # noqa: E402


def _load_json(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError(f"JSON document must be an object: {path}")
    return value


def _load_mapping(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"mapping CSV is empty: {path}")
    return rows


def _load_scores(path: Path) -> dict[str, float]:
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = csv.DictReader(handle)
            scores: dict[str, float] = {}
            for row in rows:
                case_id = str(row.get("case_id", "")).strip()
                raw = row.get("score_hz")
                if not case_id or raw in {None, ""}:
                    raise ValueError(f"invalid score row: {row}")
                scores[case_id] = float(raw)
            return scores
    raw = _load_json(path)
    values = raw.get("scores", raw)
    if not isinstance(values, Mapping):
        raise ValueError("score JSON must be keyed by case_id or contain scores")
    return {str(case_id): float(value) for case_id, value in values.items()}


def _portable(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.name


def audit(
    *,
    registry_path: Path,
    mapping_path: Path,
    rewire_scores_path: Path,
    score_spec_path: Path,
    benchmark_report_path: Path | None = None,
) -> dict[str, Any]:
    protocol = BenchmarkProtocol.from_dict(_load_json(registry_path))
    score_spec = _load_json(score_spec_path)
    mapping_rows = _load_mapping(mapping_path)
    rewire_scores = _load_scores(rewire_scores_path)
    built = build_locked_scores(protocol, mapping_rows, rewire_scores, score_spec)
    held_out_ids = set(protocol.held_out_case_ids)
    held_out_scores = {
        case_id: built["systems"]["full_workbench_locked"][case_id]
        for case_id in held_out_ids
    }

    checks = [
        {
            "name": "protocol_frozen_and_valid",
            "status": protocol.freeze_validation()["status"],
            "detail": protocol.freeze_validation(),
        },
        {
            "name": "score_spec_matches_protocol",
            "status": "PASS" if score_spec.get("protocol_hash") == protocol.protocol_hash else "FAIL",
            "detail": {"protocol_hash": protocol.protocol_hash},
        },
        {
            "name": "development_only_score_lock",
            "status": "PASS" if score_spec.get("evaluation_split") == "development" else "FAIL",
            "detail": {"evaluation_split": score_spec.get("evaluation_split")},
        },
        {
            "name": "complete_held_out_score_coverage",
            "status": "PASS" if len(held_out_scores) == len(held_out_ids) else "FAIL",
            "detail": {
                "expected": len(held_out_ids),
                "finite_locked_scores": len(held_out_scores),
            },
        },
        {
            "name": "label_blind_score_construction",
            "status": "PASS" if built["audit"]["label_blind_score_construction"] else "FAIL",
            "detail": {
                "forbidden_score_inputs": built["audit"]["forbidden_score_inputs"],
            },
        },
    ]

    baseline_detail: dict[str, Any] = {"status": "NOT_SUPPLIED"}
    if benchmark_report_path is not None:
        report = _load_json(benchmark_report_path)
        comparison = report.get("comparison", {})
        metrics = comparison.get("metrics", {}) if isinstance(comparison, Mapping) else {}
        available = sorted(str(name) for name in metrics) if isinstance(metrics, Mapping) else []
        required = [
            "degree_preserving_rewire",
            "effect_only",
            "heuristic",
            "original_model",
            "random",
            "workbench",
        ]
        baseline_detail = {
            "status": "PASS" if set(required).issubset(available) else "PARTIAL",
            "available_systems": available,
            "missing_systems": sorted(set(required) - set(available)),
            "note": "Availability only; no held-out metrics are copied into this preflight report.",
        }
    checks.append({"name": "baseline_availability", "status": baseline_detail["status"], "detail": baseline_detail})

    passed = all(check["status"] in {"PASS", "READY"} for check in checks)
    return {
        "report_version": 1,
        "status": "READY_FOR_FINAL_HELDOUT_EVALUATION" if passed else "BLOCKED",
        "evaluation_performed": False,
        "held_out_metrics_emitted": False,
        "held_out_labels_used_for_decision": False,
        "protocol_hash": protocol.protocol_hash,
        "source_registry": _portable(registry_path),
        "source_mapping": _portable(mapping_path),
        "source_rewire_scores": _portable(rewire_scores_path),
        "source_score_spec": _portable(score_spec_path),
        "development_case_count": len(protocol.development_case_ids),
        "held_out_case_count": len(protocol.held_out_case_ids),
        "checks": checks,
        "score_construction_audit": built["audit"],
        "baseline_availability": baseline_detail,
        "scientific_scope": "Readiness audit only; run the final held-out evaluator only after score/reproduction review is complete.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=ROOT / "configs/workbench/shiu_public_benchmark_v2.json")
    parser.add_argument("--mapping", type=Path, default=ROOT / "configs/workbench/shiu_v2_flywire630_mapping.csv")
    parser.add_argument("--rewire-scores", type=Path, required=True)
    parser.add_argument("--score-spec", type=Path, default=ROOT / "configs/workbench/shiu_workbench_score_v1.json")
    parser.add_argument("--benchmark-report", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(
        registry_path=args.registry.resolve(),
        mapping_path=args.mapping.resolve(),
        rewire_scores_path=args.rewire_scores.resolve(),
        score_spec_path=args.score_spec.resolve(),
        benchmark_report_path=args.benchmark_report.resolve() if args.benchmark_report else None,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "output": _portable(args.output)}, indent=2))
    return 0 if result["status"] == "READY_FOR_FINAL_HELDOUT_EVALUATION" else 2


if __name__ == "__main__":
    raise SystemExit(main())
