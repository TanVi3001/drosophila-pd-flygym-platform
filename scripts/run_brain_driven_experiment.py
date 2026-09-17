#!/usr/bin/env python
"""Run a brain-driven locomotion experiment (Gap 3).

Reads a bridge_scales.json from the fly-brain brain_body_bridge.py, creates a
BrainDrivenPerturbation, and runs the paired baseline vs perturbed locomotion
experiment on NeuroMechFly.

Usage:
    py scripts/run_brain_driven_experiment.py \
        --scales-json ../fly-brain/data/results/pd/pink1_bridge_scales.json \
        --baseline-config configs/experiments/healthy_baseline.yaml \
        --model-name pink1 \
        --output results/brain_driven/pink1_locomotion.json

If FlyGym/MuJoCo is not installed, the script reports the error and writes
a failure JSON report (same pattern as run_perturbation_experiment.py).
"""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path
import sys
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from drosophila_pd.anatomy.audit import write_json_report  # noqa: E402
from drosophila_pd.experiments.healthy_baseline import (  # noqa: E402
    load_healthy_baseline_config,
)
from drosophila_pd.experiments.perturbation_experiment import (  # noqa: E402
    build_perturbation_unavailable_report,
    run_paired_perturbation_experiment,
)
from drosophila_pd.perturbations import BrainDrivenPerturbation  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a brain-driven locomotion experiment from bridge scales."
    )
    parser.add_argument(
        "--scales-json",
        type=Path,
        required=True,
        help="Path to bridge_scales.json from fly-brain brain_body_bridge.py.",
    )
    parser.add_argument(
        "--baseline-config",
        type=Path,
        default=REPO_ROOT / "configs" / "experiments" / "healthy_baseline.yaml",
        help="Path to the unperturbed baseline YAML configuration.",
    )
    parser.add_argument(
        "--model-name",
        type=str,
        default=None,
        help="Override the model name from scales_json. Default: from JSON.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path for the paired JSON report.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        help="Override the validated baseline random_seed explicitly.",
    )
    parser.add_argument(
        "--override-json",
        type=str,
        help="JSON object of strict dotted-path baseline parameter overrides.",
    )
    parser.add_argument(
        "--motor-scale",
        type=float,
        help="Override the isotropic and bilateral motor scales from scales_json.",
    )
    parser.add_argument(
        "--coupling-scale",
        type=float,
        help="Override the CPG coupling scale from scales_json.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    perturbation = BrainDrivenPerturbation.from_json(
        args.scales_json,
        name=f"brain_driven_{args.model_name or ''}".strip("_"),
    )
    if args.motor_scale is not None:
        perturbation = replace(
            perturbation,
            motor_scale=args.motor_scale,
            left_motor_scale=args.motor_scale,
            right_motor_scale=args.motor_scale,
        )
    if args.coupling_scale is not None:
        perturbation = replace(perturbation, coupling_scale=args.coupling_scale)
    baseline_config = load_healthy_baseline_config(args.baseline_config)
    if args.seed is not None:
        baseline_config = baseline_config.with_random_seed(args.seed)
    if args.override_json is not None:
        baseline_config = baseline_config.with_overrides(json.loads(args.override_json))

    print("Brain-driven locomotion experiment (Gap 3)")
    print(f"Scales JSON:  {args.scales_json}")
    print(f"Baseline:     {args.baseline_config}")
    print(f"Model:        {perturbation.model}")
    print(f"motor_scale:  {perturbation.motor_scale}")
    print(f"coupling_scale: {perturbation.coupling_scale}")
    print(f"Perturbation: {perturbation.perturbation_type} / {perturbation.name}")

    try:
        report = run_paired_perturbation_experiment(
            baseline_config=baseline_config,
            perturbation=perturbation,
            repo_root=REPO_ROOT,
        )
    except Exception as exc:
        report = build_perturbation_unavailable_report(
            exc,
            baseline_config=baseline_config,
            perturbation=perturbation,
            repo_root=REPO_ROOT,
        )
        print("\nLOCAL EXECUTION = NOT VERIFIED")
        print(f"{type(exc).__name__}: {exc}")
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            write_json_report(report, args.output)
            print(f"\nWrote JSON report: {args.output}")
        return 2

    print("\nChecks:")
    for name, check in report["checks"].items():
        status = "PASS" if check["pass"] else "FAIL"
        print(f"  {status} {name}: observed={check['observed']} expected={check['expected']}")

    comparison = report["comparison"]["scalars"]
    print("\nComparison (baseline vs brain-driven):")
    for name in (
        "planar_displacement_mm",
        "mean_planar_speed_mm_s",
        "heading_yaw_change_rad",
    ):
        delta = comparison[name]["absolute_delta"]
        print(f"  {name} absolute_delta: {delta}")

    overall_status = "PASS" if report["overall_pass"] else "FAIL"
    print(f"\nOverall: {overall_status}")
    print(report["scientific_scope"])

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        write_json_report(report, args.output)
        print(f"\nWrote JSON report: {args.output}")

    return 0 if report["overall_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
