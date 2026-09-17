#!/usr/bin/env python
"""Batch: run brain-driven locomotion experiments for all PD models.

Reads each model's bridge_scales.json from fly-brain, creates a
BrainDrivenPerturbation, and runs the paired baseline vs perturbed
locomotion experiment on NeuroMechFly.

Usage:
    py scripts/run_brain_driven_all.py \
        --baseline-config configs/experiments/healthy_baseline.yaml \
        --bridge-dir ../fly-brain/data/results/pd

    # Specify models explicitly
    py scripts/run_brain_driven_all.py --models pink1 parkin --t-run 1 --drive p9
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run brain-driven locomotion for all PD models (batch)."
    )
    parser.add_argument(
        "--models", nargs="+",
        default=["healthy", "pink1", "parkin", "lrrk2", "dj1", "complexI"],
        help="Models to run.",
    )
    parser.add_argument(
        "--baseline-config", type=Path,
        default=REPO_ROOT / "configs" / "experiments" / "healthy_baseline.yaml",
    )
    parser.add_argument(
        "--bridge-dir", type=Path,
        default=REPO_ROOT.parent / "fly-brain" / "data" / "results" / "pd",
        help="Directory containing <model>_bridge_scales.json files.",
    )
    parser.add_argument(
        "--output-dir", type=Path,
        default=REPO_ROOT / "results" / "brain_driven",
    )
    args = parser.parse_args()

    baseline_config = load_healthy_baseline_config(args.baseline_config)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("BRAIN-DRIVEN LOCOMOTION — BATCH")
    print(f"  models: {args.models}")
    print(f"  bridge_dir: {args.bridge_dir}")
    print(f"  output_dir: {args.output_dir}")
    print("=" * 60)

    for model in args.models:
        scales_json = args.bridge_dir / f"{model}_bridge_scales.json"
        output_json = args.output_dir / f"{model}_locomotion.json"

        if model == "healthy":
            print(f"  {model}: skipping (healthy = baseline, no perturbation)")
            continue

        if not scales_json.is_file():
            print(f"  SKIP {model}: missing {scales_json}")
            continue

        print(f"\n  {model}: scales={scales_json.name}")
        perturbation = BrainDrivenPerturbation.from_json(
            scales_json,
            name=f"brain_driven_{model}",
        )
        print(f"    motor_scale={perturbation.motor_scale} "
              f"coupling_scale={perturbation.coupling_scale}")

        try:
            report = run_paired_perturbation_experiment(
                baseline_config=baseline_config,
                perturbation=perturbation,
                repo_root=REPO_ROOT,
            )
            status = "PASS" if report["overall_pass"] else "FAIL"
            print(f"    {status}")
        except Exception as exc:
            report = build_perturbation_unavailable_report(
                exc,
                baseline_config=baseline_config,
                perturbation=perturbation,
                repo_root=REPO_ROOT,
            )
            print(f"    NOT VERIFIED: {type(exc).__name__}: {exc}")

        write_json_report(report, output_json)
        print(f"    -> {output_json}")

    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
