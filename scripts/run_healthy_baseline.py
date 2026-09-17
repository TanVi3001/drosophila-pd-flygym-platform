#!/usr/bin/env python
"""Run Milestone C unperturbed locomotion baseline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from drosophila_pd.experiments.healthy_baseline import (  # noqa: E402
    build_healthy_baseline_unavailable_report,
    load_healthy_baseline_config,
    run_healthy_baseline,
    write_json_report,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Milestone C unperturbed locomotion baseline."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=REPO_ROOT / "configs" / "experiments" / "healthy_baseline.yaml",
        help="Path to the healthy baseline YAML configuration.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help=(
            "Optional path for the JSON report, for example "
            "results/baseline/healthy_baseline.json."
        ),
    )
    parser.add_argument(
        "--seed",
        type=int,
        help="Override the validated configuration random_seed explicitly.",
    )
    parser.add_argument(
        "--override-json",
        type=str,
        help="JSON object of strict dotted-path parameter overrides.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = load_healthy_baseline_config(args.config)
    if args.seed is not None:
        config = config.with_random_seed(args.seed)
    if args.override_json is not None:
        overrides = json.loads(args.override_json)
        config = config.with_overrides(overrides)
    print("Milestone C unperturbed locomotion baseline")
    print(f"Config: {args.config}")
    try:
        report = run_healthy_baseline(config, repo_root=REPO_ROOT)
    except Exception as exc:
        report = build_healthy_baseline_unavailable_report(
            exc, config=config, repo_root=REPO_ROOT
        )
        print("\nLOCAL EXECUTION = NOT VERIFIED")
        print(f"{type(exc).__name__}: {exc}")
        if args.output is not None:
            write_json_report(report, args.output)
            print(f"\nWrote JSON report: {args.output}")
        return 2

    print("\nSimulation summary:")
    simulation = report["simulation_summary"]
    print(f"  steps: {simulation['step_count']}")
    print(f"  timestep_s: {simulation['timestep_s']}")
    print(f"  executed_duration_s: {simulation['executed_duration_s']}")

    metrics = report["derived_locomotion_metrics"]
    print("\nDerived metrics:")
    print(f"  planar_displacement_mm: {metrics['planar_displacement_mm']}")
    print(f"  mean_planar_speed_mm_s: {metrics['mean_planar_speed_mm_s']}")
    print(f"  heading_yaw_change_rad: {metrics['heading_yaw_change_rad']}")

    print("\nChecks:")
    for name, check in report["checks"].items():
        status = "PASS" if check["pass"] else "FAIL"
        print(f"  {status} {name}: observed={check['observed']} expected={check['expected']}")

    overall_status = "PASS" if report["overall_pass"] else "FAIL"
    print(f"\nOverall: {overall_status}")
    print(report["scientific_scope"])

    if args.output is not None:
        write_json_report(report, args.output)
        print(f"\nWrote JSON report: {args.output}")

    return 0 if report["overall_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
