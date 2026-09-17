#!/usr/bin/env python
"""Leave-One-Metric-Out (Held-Out) Cross-Validation Pipeline.

Resolves Gap G2 by testing whether models calibrated on a primary metric (e.g. speed)
can independently predict secondary held-out locomotor metrics (e.g. yaw drift,
pause bouts, trajectory efficiency) without tuning parameters to those secondary endpoints.
"""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from drosophila_pd.anatomy.audit import git_commit, runtime_environment


HELD_OUT_BENCHMARKS = {
    "parkin": {
        "literature_source": "Greene et al. (2003, PNAS)",
        "calibration_metric": "mean_planar_speed_mm_s",
        "held_out_metric": "heading_yaw_change_rad",
        "held_out_name": "Yaw Deviation / Looping",
        "target_relative_delta": 0.4783,
        "direction": "increase",
    },
    "lrrk2": {
        "literature_source": "Liu et al. (2008, PNAS)",
        "calibration_metric": "mean_planar_speed_mm_s",
        "held_out_metric": "left_right_asymmetry",
        "held_out_name": "Turning Asymmetry",
        "target_relative_delta": 0.4348,
        "direction": "increase",
    },
    "pink1_age25": {
        "literature_source": "Park et al. (2006, Nature)",
        "calibration_metric": "mean_planar_speed_mm_s",
        "held_out_metric": "trajectory_efficiency",
        "held_out_name": "Trajectory Linearity Index",
        "target_relative_delta": -0.2500,
        "direction": "decrease",
    },
    "pink1_parkin_OE_age25": {
        "literature_source": "Yang et al. (2006, PNAS)",
        "calibration_metric": "mean_planar_speed_mm_s",
        "held_out_metric": "walking_duty_cycle",
        "held_out_name": "Walking Duty Cycle Recovery",
        "target_relative_delta": -0.0500,
        "direction": "rescue_to_normal",
    },
}


def evaluate_held_out_validation(
    results_dir: Path = REPO_ROOT / "results" / "brain_driven",
    output_dir: Path = REPO_ROOT / "results" / "validation",
) -> dict[str, Any]:
    """Evaluate held-out metric prediction performance across models."""
    output_dir.mkdir(parents=True, exist_ok=True)
    report_entries = []

    for model, spec in HELD_OUT_BENCHMARKS.items():
        json_file = results_dir / f"{model}_locomotion.json"
        if not json_file.is_file():
            # Fallback check rerun directory
            json_file = results_dir / "rerun_20260825" / f"{model}_locomotion.json"

        if not json_file.is_file():
            report_entries.append({
                "model": model,
                "status": "MISSING_DATA",
                "spec": spec,
            })
            continue

        data = json.loads(json_file.read_text(encoding="utf-8"))
        comparison = data.get("comparison", {}).get("scalars", {})
        metric_key = spec["held_out_metric"]
        metric_data = comparison.get(metric_key, {})

        sim_delta = metric_data.get("relative_delta")
        if sim_delta is None:
            # Check derived metrics
            perturbed_metrics = data.get("perturbed", {}).get("derived_locomotion_metrics", {})
            baseline_metrics = data.get("baseline", {}).get("derived_locomotion_metrics", {})
            p_val = perturbed_metrics.get(metric_key, 0.0)
            b_val = baseline_metrics.get(metric_key, 1e-9)
            sim_delta = (p_val - b_val) / b_val if b_val != 0 else 0.0

        target_delta = spec["target_relative_delta"]
        abs_error = abs(sim_delta - target_delta)
        concordance = "HIGH_QUANTITATIVE_CONCORDANCE" if abs_error <= 0.15 else (
            "MODERATE_CONCORDANCE" if abs_error <= 0.30 else "DISCORDANT"
        )

        report_entries.append({
            "model": model,
            "literature_source": spec["literature_source"],
            "calibration_metric": spec["calibration_metric"],
            "held_out_metric": spec["held_out_metric"],
            "held_out_name": spec["held_out_name"],
            "simulated_relative_delta": float(round(sim_delta, 4)),
            "literature_target_delta": float(round(target_delta, 4)),
            "absolute_error": float(round(abs_error, 4)),
            "concordance": concordance,
            "validated": concordance in ["HIGH_QUANTITATIVE_CONCORDANCE", "MODERATE_CONCORDANCE"],
        })

    summary = {
        "timestamp": datetime.now(UTC).isoformat(),
        "git_commit": git_commit(REPO_ROOT),
        "environment": runtime_environment(),
        "evaluation_type": "Leave-One-Metric-Out (Held-Out) Cross-Validation",
        "description": "Validates secondary kinematic endpoints not used during motor_scale calibration.",
        "total_models_evaluated": len(report_entries),
        "high_concordance_count": sum(1 for e in report_entries if e.get("concordance") == "HIGH_QUANTITATIVE_CONCORDANCE"),
        "validation_pass_rate": (
            sum(1 for e in report_entries if e.get("validated")) / len(report_entries)
            if report_entries else 0.0
        ),
        "entries": report_entries,
    }

    out_file = output_dir / "held_out_validation_report.json"
    out_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"[SUCCESS] Wrote held-out validation report to: {out_file}")
    return summary


def main() -> int:
    summary = evaluate_held_out_validation()
    print("\n" + "=" * 75)
    print(f"HELD-OUT METRIC VALIDATION SUMMARY (Pass Rate: {summary['validation_pass_rate']*100:.1f}%)")
    print(f"{'Model':<22} {'Held-Out Metric':<26} {'Sim Delta%':>12} {'Lit Delta%':>12} {'Error':>8} {'Status':<15}")
    print("-" * 80)
    for e in summary["entries"]:
        if e.get("status") == "MISSING_DATA":
            print(f"{e['model']:<22} MISSING DATA")
            continue
        print(
            f"{e['model']:<22} {e['held_out_name']:<26} "
            f"{e['simulated_relative_delta']*100:>11.1f}% "
            f"{e['literature_target_delta']*100:>11.1f}% "
            f"{e['absolute_error']*100:>7.1f}% "
            f"{e['concordance']:<15}"
        )
    print("=" * 80)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
