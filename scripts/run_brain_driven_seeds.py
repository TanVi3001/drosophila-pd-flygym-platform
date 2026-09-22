#!/usr/bin/env python
"""Multi-seed statistical replication for brain-driven locomotion experiments.

Runs each model (baseline + 7 PD mutants) with N=5 random seeds to support
formal statistical testing (Wilcoxon signed-rank test) and report mean ± SD
for each locomotion metric.

Addresses:
  - MT4/KQ4 mâu thuẫn (đề cương NCKH): thay tuyên bố "p<0.05 với N=1"
    bằng "Wilcoxon p<0.05 với N=5 seeds mỗi điều kiện".
  - Ablation Abl-3: phân biệt nhóm bệnh vs. nhóm cứu vãn qua bộ chỉ số mới.

Usage on Colab:
    xvfb-run -a python scripts/run_brain_driven_seeds.py \\
        --baseline-config configs/experiments/healthy_baseline.yaml \\
        --bridge-dir data/bridge_scales \\
        --output-dir results/brain_driven/seed_analysis \\
        --duration 5.0 \\
        --seeds 42 123 456 789 2026

Output:
    results/brain_driven/seed_analysis/
        multi_seed_raw.json         -- raw metrics for every seed × model
        multi_seed_summary.csv      -- mean ± SD per metric per model
        multi_seed_wilcoxon.json    -- p-values: baseline vs. perturbed
        multi_seed_ablation3.json   -- expanded vs. basic metric comparison
"""

from __future__ import annotations

import argparse
import csv
from copy import deepcopy
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
from drosophila_pd.experiments.healthy_baseline import (
    HealthyBaselineConfig,
    _actuator_summary,
    _apply_action_perturbation,
    _body_segment_index,
    _collect_thorax_state,
    _controller_transformation_snapshot,
    build_official_cpg_controller,
    check_locomotion_pass_criteria,
    load_healthy_baseline_config,
)
from drosophila_pd.metrics.locomotion import compute_locomotion_metrics
from drosophila_pd.perturbations import (
    BrainDrivenPerturbation,
    ControllerPerturbationContext,
    Perturbation,
    summarize_action_transformation,
    summarize_controller_transformation,
)

# ---------------------------------------------------------------------------
# Core metrics reported for statistical comparison
# ---------------------------------------------------------------------------
BASIC_METRICS = [
    "mean_planar_speed_mm_s",
    "planar_displacement_mm",
    "body_height_mean_mm",
    "heading_yaw_change_rad",
    "trajectory_efficiency",
]
EXPANDED_METRICS = [
    "walking_duty_cycle",
    "pause_bout_count",
    "left_right_asymmetry",
    "cumulative_turning_rad",
]
ALL_METRICS = BASIC_METRICS + EXPANDED_METRICS


# ---------------------------------------------------------------------------
# Single-seed locomotion run (no video)
# ---------------------------------------------------------------------------

def _run_single_seed(
    config: HealthyBaselineConfig,
    *,
    seed: int,
    perturbation: Perturbation | None = None,
    condition_id: str = "unperturbed",
    duration_s: float | None = None,
) -> dict[str, Any]:
    """Run one locomotion simulation with a specific random seed.

    Returns a dict containing ``derived_locomotion_metrics`` and
    ``overall_pass``.
    """
    config = deepcopy(config)
    config.data["simulation"]["random_seed"] = seed

    if duration_s is not None and duration_s > 0:
        config.data["simulation"]["duration_s"] = float(duration_s)

    np.random.seed(seed)

    from flygym import Simulation
    from flygym.compose import FlatGroundWorld
    from flygym.utils.math import Rotation3D
    from flygym_demo.complex_terrain import (
        LocomotionAction,
        apply_locomotion_action,
        make_locomotion_fly,
    )

    fly = make_locomotion_fly(
        name=config.fly["name"],
        joint_stiffness=float(config.fly["joint_stiffness"]),
        joint_damping=float(config.fly["joint_damping"]),
        passive_tarsus_stiffness=float(config.fly["passive_tarsus_stiffness"]),
        passive_tarsus_damping=float(config.fly["passive_tarsus_damping"]),
        actuator_gain=float(config.actuators["gain"]),
        actuator_forcerange=tuple(float(v) for v in config.actuators["forcerange"]),
        add_adhesion=bool(config.fly["add_adhesion"]),
        adhesion_gain=float(config.fly["adhesion_gain"]),
        colorize=bool(config.fly["colorize"]),
    )
    dof_order = fly.get_actuated_jointdofs_order(config.actuators["type"])

    world = FlatGroundWorld()
    world.add_fly(
        fly,
        spawn_position=config.spawn_position_mm,
        spawn_rotation=Rotation3D("quat", config.spawn_orientation_quat.tolist()),
        add_ground_contact_sensors=bool(config.world["add_ground_contact_sensors"]),
    )
    sim = Simulation(world, timestep=config.timestep_s)
    sim.reset()

    controller, preprogrammed_steps = build_official_cpg_controller(
        timestep=sim.timestep,
        random_seed=seed,
        output_dof_order=dof_order,
        config=config.controller,
    )
    if perturbation is not None:
        controller = perturbation.apply_to_controller(
            controller,
            ControllerPerturbationContext(
                condition_id=condition_id,
                timestep_s=float(sim.timestep),
                random_seed=seed,
                expected_joint_angle_count=len(dof_order),
            ),
        )

    initial_action = LocomotionAction(
        joint_angles=preprogrammed_steps.default_pose_by_dof_order(dof_order),
        adhesion_onoff=(
            np.ones(6, dtype=bool) if bool(config.fly["add_adhesion"]) else None
        ),
    )
    apply_locomotion_action(sim, fly.name, initial_action)
    if config.warmup_duration_s > 0:
        sim.warmup(duration_s=config.warmup_duration_s)

    thorax_index = _body_segment_index(fly, "c_thorax")
    step_count = config.expected_step_count()
    thorax_positions = np.full((step_count + 1, 3), np.nan, dtype=float)
    thorax_quaternions = np.full((step_count + 1, 4), np.nan, dtype=float)
    controller_joint_angle_actions = np.full(
        (step_count, len(dof_order)), np.nan, dtype=float
    )
    joint_angle_actions = np.full((step_count, len(dof_order)), np.nan, dtype=float)
    adhesion_onoff = (
        np.zeros((step_count, 6), dtype=bool)
        if bool(config.fly["add_adhesion"])
        else None
    )
    controller_adhesion_onoff = (
        np.zeros((step_count, 6), dtype=bool)
        if bool(config.fly["add_adhesion"])
        else None
    )

    _collect_thorax_state(sim, fly.name, thorax_index, thorax_positions, thorax_quaternions, 0)

    for step_index in range(step_count):
        controller_action = controller.step()
        action = _apply_action_perturbation(
            controller_action,
            perturbation=perturbation,
            condition_id=condition_id,
            step_index=step_index,
            timestep_s=float(sim.timestep),
            random_seed=seed,
            expected_joint_angle_count=len(dof_order),
        )
        apply_locomotion_action(sim, fly.name, action)
        sim.step()

        controller_joint_angle_actions[step_index] = controller_action.joint_angles
        if controller_adhesion_onoff is not None:
            controller_adhesion_onoff[step_index] = controller_action.adhesion_onoff
        joint_angle_actions[step_index] = action.joint_angles
        if adhesion_onoff is not None:
            adhesion_onoff[step_index] = action.adhesion_onoff

        _collect_thorax_state(
            sim, fly.name, thorax_index, thorax_positions, thorax_quaternions, step_index + 1
        )

    metrics = compute_locomotion_metrics(
        thorax_positions=thorax_positions,
        thorax_quaternions=thorax_quaternions,
        joint_angle_actions=joint_angle_actions,
        adhesion_onoff=adhesion_onoff,
        timestep_s=sim.timestep,
        requested_duration_s=config.duration_s,
        instability_height_floor_mm=float(
            config.pass_criteria["minimum_body_height_mm"]
        ),
    )
    actuator_summary = _actuator_summary(fly, sim)
    checks = check_locomotion_pass_criteria(
        metrics=metrics,
        expected_step_count=step_count,
        expected_actuated_dofs=int(config.actuators["expected_actuated_dofs"]),
        observed_actuated_dofs=actuator_summary["position_actuator_count"],
        expected_adhesion_actuators=config.expected_adhesion_actuator_count(),
        observed_adhesion_actuators=actuator_summary["adhesion_actuator_count"],
        deterministic_seed_recorded=True,
    )

    sim.close()
    return {
        "seed": seed,
        "condition_id": condition_id,
        "overall_pass": all(c["pass"] for c in checks.values()),
        "derived_locomotion_metrics": metrics,
    }


# ---------------------------------------------------------------------------
# Statistical aggregation
# ---------------------------------------------------------------------------

def _aggregate_seeds(
    seed_results: list[dict[str, Any]],
    metric_keys: list[str] | None = None,
) -> dict[str, dict[str, float]]:
    """Compute mean, std, and N for each metric across seeds.

    Returns {metric_name: {"mean": ..., "std": ..., "n": ..., "values": [...]}}
    """
    if metric_keys is None:
        metric_keys = ALL_METRICS
    agg: dict[str, dict[str, Any]] = {}
    for key in metric_keys:
        values = []
        for r in seed_results:
            v = r["derived_locomotion_metrics"].get(key)
            if v is not None and not (isinstance(v, float) and np.isnan(v)):
                values.append(float(v))
        if values:
            agg[key] = {
                "mean": float(np.mean(values)),
                "std": float(np.std(values, ddof=1) if len(values) > 1 else 0.0),
                "n": len(values),
                "values": values,
            }
        else:
            agg[key] = {"mean": float("nan"), "std": float("nan"), "n": 0, "values": []}
    return agg


def _wilcoxon_test(
    baseline_agg: dict[str, dict],
    perturbed_agg: dict[str, dict],
    metric_keys: list[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Paired Wilcoxon signed-rank test: baseline vs. perturbed per metric.

    Requires scipy. Falls back to descriptive stats if not available.
    Returns {metric: {"statistic": ..., "p_value": ..., "significant_0.05": bool,
                       "delta_mean": ..., "delta_pct": ...}}.
    """
    if metric_keys is None:
        metric_keys = ALL_METRICS
    results: dict[str, dict[str, Any]] = {}

    try:
        from scipy.stats import wilcoxon as _wilcoxon
        scipy_available = True
    except ImportError:
        scipy_available = False

    for key in metric_keys:
        b_vals = baseline_agg.get(key, {}).get("values", [])
        p_vals = perturbed_agg.get(key, {}).get("values", [])
        b_mean = baseline_agg.get(key, {}).get("mean", float("nan"))
        p_mean = perturbed_agg.get(key, {}).get("mean", float("nan"))

        delta_mean = p_mean - b_mean
        delta_pct = (delta_mean / b_mean * 100.0) if b_mean and b_mean != 0 else float("nan")

        entry: dict[str, Any] = {
            "baseline_mean": b_mean,
            "baseline_std": baseline_agg.get(key, {}).get("std", float("nan")),
            "perturbed_mean": p_mean,
            "perturbed_std": perturbed_agg.get(key, {}).get("std", float("nan")),
            "delta_mean": delta_mean,
            "delta_pct": delta_pct,
            "n_seeds": len(b_vals),
        }

        if len(b_vals) >= 2 and len(p_vals) >= 2 and len(b_vals) == len(p_vals):
            # Paired test: each seed i treated as a pair (baseline_i, perturbed_i).
            # Handle an all-zero paired sample before checking SciPy so the
            # deterministic conclusion remains available in the lightweight
            # test/runtime dependency profile as well.
            differences = np.asarray(p_vals, dtype=float) - np.asarray(b_vals, dtype=float)
            if np.all(differences == 0.0):
                # scipy warns for an all-zero signed-rank sample. The exact
                # descriptive conclusion is unambiguous: no paired change,
                # statistic 0, and two-sided p=1.
                entry["statistic"] = 0.0
                entry["p_value"] = 1.0
                entry["significant_0.05"] = False
                entry["significant_0.10"] = False
                entry["test_method"] = "wilcoxon_signed_rank_constant_zero"
            elif scipy_available:
                try:
                    stat, pval = _wilcoxon(b_vals, p_vals, alternative="two-sided")
                    entry["test_method"] = "wilcoxon_signed_rank"
                    entry["statistic"] = float(stat)
                    entry["p_value"] = float(pval)
                    entry["significant_0.05"] = bool(pval < 0.05)
                    entry["significant_0.10"] = bool(pval < 0.10)
                except Exception as e:
                    entry["statistic"] = None
                    entry["p_value"] = None
                    entry["significant_0.05"] = None
                    entry["test_error"] = str(e)
                    entry["test_method"] = "wilcoxon_failed"
            else:
                entry["statistic"] = None
                entry["p_value"] = None
                entry["significant_0.05"] = None
                entry["test_method"] = "descriptive_only"
        else:
            entry["statistic"] = None
            entry["p_value"] = None
            entry["significant_0.05"] = None
            entry["test_method"] = "descriptive_only" if not scipy_available else "insufficient_n"

        results[key] = entry
    return results


def _ablation3_comparison(
    wilcoxon_results: dict[str, dict],
) -> dict[str, Any]:
    """Abl-3: compare discrimination power of basic vs. expanded metrics.

    Returns summary showing whether expanded metrics (bout/turning) provide
    additional differentiation beyond basic speed/displacement metrics.
    """
    basic_sig = {
        k: wilcoxon_results[k]
        for k in BASIC_METRICS
        if k in wilcoxon_results
    }
    expanded_sig = {
        k: wilcoxon_results[k]
        for k in EXPANDED_METRICS
        if k in wilcoxon_results
    }

    def _count_significant(metrics_dict: dict) -> int:
        return sum(
            1 for v in metrics_dict.values()
            if v.get("significant_0.05") is True
        )

    return {
        "ablation": "Abl-3",
        "description": (
            "Compare discrimination power of basic metrics (speed/displacement) "
            "vs. expanded metrics (bout/turning) in detecting perturbed vs. baseline."
        ),
        "basic_metrics_count": len(BASIC_METRICS),
        "expanded_metrics_count": len(EXPANDED_METRICS),
        "basic_significant_count": _count_significant(basic_sig),
        "expanded_significant_count": _count_significant(expanded_sig),
        "basic_metrics_detail": {
            k: {
                "p_value": v.get("p_value"),
                "significant_0.05": v.get("significant_0.05"),
                "delta_pct": v.get("delta_pct"),
            }
            for k, v in basic_sig.items()
        },
        "expanded_metrics_detail": {
            k: {
                "p_value": v.get("p_value"),
                "significant_0.05": v.get("significant_0.05"),
                "delta_pct": v.get("delta_pct"),
            }
            for k, v in expanded_sig.items()
        },
        "conclusion": (
            "EXPANDED_ADDS_VALUE"
            if _count_significant(expanded_sig) > 0
            else "BASIC_SUFFICIENT"
        ),
    }


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------

def _write_summary_csv(
    all_model_stats: dict[str, dict],
    output_path: Path,
) -> None:
    """Write mean ± SD summary table to CSV.

    Columns: model, condition, metric, mean, std, n.
    """
    rows = []
    for model, conditions in all_model_stats.items():
        for condition, agg in conditions.items():
            for metric, stats in agg.items():
                rows.append({
                    "model": model,
                    "condition": condition,
                    "metric": metric,
                    "mean": stats.get("mean", ""),
                    "std": stats.get("std", ""),
                    "n": stats.get("n", ""),
                })
    if not rows:
        return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["model", "condition", "metric", "mean", "std", "n"])
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Multi-seed statistical replication for brain-driven locomotion. "
            "Runs N seeds per model, computes mean ± SD, and applies "
            "Wilcoxon signed-rank test (baseline vs. perturbed)."
        )
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=["pink1", "parkin", "lrrk2", "dj1", "complexI",
                 "pink1_age25", "pink1_parkin_OE_age25"],
    )
    parser.add_argument(
        "--baseline-config",
        type=Path,
        default=REPO_ROOT / "configs" / "experiments" / "healthy_baseline.yaml",
    )
    parser.add_argument(
        "--bridge-dir",
        type=Path,
        default=REPO_ROOT / "data" / "bridge_scales",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "results" / "brain_driven" / "seed_analysis",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=5.0,
        help="Simulation duration in seconds per seed (default: 5.0s).",
    )
    parser.add_argument(
        "--seeds",
        nargs="+",
        type=int,
        default=[42, 123, 456, 789, 1024, 2026],
        help="Random seeds to use (default: 6 seeds to allow two-sided Wilcoxon p < 0.05).",
    )
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    baseline_config = load_healthy_baseline_config(args.baseline_config)

    n_seeds = len(args.seeds)
    n_models = len(args.models)
    total_runs = (n_models + 1) * n_seeds  # +1 for baseline

    print("=" * 70)
    print("MULTI-SEED STATISTICAL REPLICATION PIPELINE")
    print(f"  Seeds: {args.seeds}  (N={n_seeds})")
    print(f"  Models: {args.models}")
    print(f"  Duration per seed: {args.duration}s")
    print(f"  Total simulation runs: {total_runs}")
    print(f"  Output: {args.output_dir}")
    print("=" * 70)

    # ------------------------------------------------------------------
    # 1. Baseline seeds
    # ------------------------------------------------------------------
    print(f"\n[1/{n_models + 1}] Baseline (wild-type) - {n_seeds} seeds...")
    baseline_seed_results: list[dict] = []
    for seed in args.seeds:
        print(f"    seed={seed} ... ", end="", flush=True)
        result = _run_single_seed(
            baseline_config,
            seed=seed,
            condition_id="baseline",
            duration_s=args.duration,
        )
        baseline_seed_results.append(result)
        status = "PASS" if result["overall_pass"] else "FAIL"
        speed = result["derived_locomotion_metrics"].get("mean_planar_speed_mm_s", float("nan"))
        print(f"[{status}] speed={speed:.2f} mm/s")

    baseline_agg = _aggregate_seeds(baseline_seed_results)

    # ------------------------------------------------------------------
    # 2. Model seeds
    # ------------------------------------------------------------------
    raw_data: dict[str, dict] = {"baseline": {
        "seed_results": baseline_seed_results,
        "aggregated": baseline_agg,
    }}
    model_stats: dict[str, dict] = {"baseline": {"baseline": baseline_agg}}
    wilcoxon_reports: dict[str, dict] = {}
    ablation3_reports: dict[str, dict] = {}

    for m_idx, model in enumerate(args.models, start=2):
        scales_json = args.bridge_dir / f"{model}_bridge_scales.json"
        if not scales_json.is_file():
            print(f"\n[{m_idx}/{n_models + 1}] SKIP {model}: {scales_json} not found")
            continue

        perturbation = BrainDrivenPerturbation.from_json(scales_json, name=f"brain_driven_{model}")
        print(
            f"\n[{m_idx}/{n_models + 1}] {model} "
            f"(motor={perturbation.motor_scale:.4f}, "
            f"coupling={perturbation.coupling_scale:.4f}) - {n_seeds} seeds..."
        )

        perturbed_seed_results: list[dict] = []
        for seed in args.seeds:
            print(f"    seed={seed} ... ", end="", flush=True)
            result = _run_single_seed(
                baseline_config,
                seed=seed,
                perturbation=perturbation,
                condition_id="perturbed",
                duration_s=args.duration,
            )
            perturbed_seed_results.append(result)
            status = "PASS" if result["overall_pass"] else "FAIL"
            speed = result["derived_locomotion_metrics"].get("mean_planar_speed_mm_s", float("nan"))
            print(f"[{status}] speed={speed:.2f} mm/s")

        perturbed_agg = _aggregate_seeds(perturbed_seed_results)
        wilcoxon = _wilcoxon_test(baseline_agg, perturbed_agg)
        ablation3 = _ablation3_comparison(wilcoxon)

        raw_data[model] = {
            "perturbation": perturbation.metadata(),
            "seed_results": perturbed_seed_results,
            "aggregated": perturbed_agg,
        }
        model_stats[model] = {"baseline": baseline_agg, "perturbed": perturbed_agg}
        wilcoxon_reports[model] = wilcoxon
        ablation3_reports[model] = ablation3

        # Quick summary
        sig_count = sum(
            1 for v in wilcoxon.values() if v.get("significant_0.05") is True
        )
        speed_w = wilcoxon.get("mean_planar_speed_mm_s", {})
        print(
            f"    -> speed Delta={speed_w.get('delta_pct', float('nan')):.1f}%  "
            f"p={speed_w.get('p_value', 'N/A')}  "
            f"[{sig_count}/{len(ALL_METRICS)} metrics significant]"
        )
        print(f"    -> Abl-3: {ablation3['conclusion']}")

    # ------------------------------------------------------------------
    # 3. Export results
    # ------------------------------------------------------------------
    timestamp = datetime.now(UTC).isoformat()

    # multi_seed_raw.json
    raw_path = args.output_dir / "multi_seed_raw.json"
    raw_path.write_text(
        json.dumps({
            "timestamp": timestamp,
            "git_commit": git_commit(REPO_ROOT),
            "environment": runtime_environment(),
            "seeds": args.seeds,
            "duration_s": args.duration,
            "models": args.models,
            "data": raw_data,
        }, indent=2),
        encoding="utf-8",
    )
    print(f"\n[SAVE] Raw data: {raw_path.name}")

    # multi_seed_wilcoxon.json
    wilcoxon_path = args.output_dir / "multi_seed_wilcoxon.json"
    wilcoxon_path.write_text(
        json.dumps({
            "timestamp": timestamp,
            "seeds": args.seeds,
            "n_seeds": n_seeds,
            "metrics_tested": ALL_METRICS,
            "basic_metrics": BASIC_METRICS,
            "expanded_metrics": EXPANDED_METRICS,
            "models": wilcoxon_reports,
        }, indent=2),
        encoding="utf-8",
    )
    print(f"[SAVE] Wilcoxon results: {wilcoxon_path.name}")

    # multi_seed_ablation3.json
    abl3_path = args.output_dir / "multi_seed_ablation3.json"
    abl3_path.write_text(
        json.dumps({
            "timestamp": timestamp,
            "seeds": args.seeds,
            "ablation": "Abl-3",
            "description": (
                "Expanded (bout/turning) metrics vs. basic (speed/displacement) "
                "metrics: which set better discriminates disease from baseline?"
            ),
            "models": ablation3_reports,
        }, indent=2),
        encoding="utf-8",
    )
    print(f"[SAVE] Ablation-3 report: {abl3_path.name}")

    # multi_seed_summary.csv
    csv_path = args.output_dir / "multi_seed_summary.csv"
    _write_summary_csv(model_stats, csv_path)
    print(f"[SAVE] Summary CSV: {csv_path.name}")

    # Final summary table
    print("\n" + "=" * 70)
    print(f"STATISTICAL SUMMARY (mean +- SD, N={n_seeds} seeds)")
    print(f"{'Model':<30} {'Speed base':>12} {'Speed pert':>12} {'Delta%':>8} {'p-val':>8}")
    print("-" * 70)
    for model, w_report in wilcoxon_reports.items():
        entry = w_report.get("mean_planar_speed_mm_s", {})
        b = entry.get("baseline_mean", float("nan"))
        p = entry.get("perturbed_mean", float("nan"))
        d = entry.get("delta_pct", float("nan"))
        pval = entry.get("p_value", "N/A")
        pval_str = f"{pval:.4f}" if isinstance(pval, float) else str(pval)
        print(f"  {model:<28} {b:>12.2f} {p:>12.2f} {d:>8.1f}% {pval_str:>8}")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
