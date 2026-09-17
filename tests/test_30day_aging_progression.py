"""Tests for 30-Day Longitudinal Aging Progression Pipeline."""

from pathlib import Path
import pytest

from drosophila_pd.perturbations import BrainDrivenPerturbation


def test_aging_series_files_exist_and_valid():
    bridge_dir = Path("data/bridge_scales/aging_series")
    assert bridge_dir.is_dir()

    days = [1, 5, 10, 15, 20, 25, 30]
    conditions = ["healthy", "pink1", "pink1_parkin_OE"]

    for cond in conditions:
        for day in days:
            f = bridge_dir / f"{cond}_day{day:02d}_bridge_scales.json"
            assert f.is_file(), f"Missing bridge scale file: {f}"

            pert = BrainDrivenPerturbation.from_json(f)
            assert pert.motor_scale > 0
            assert pert.coupling_scale > 0
            assert pert.biological_mechanism is not None


def test_pink1_decay_trajectory_ordering():
    bridge_dir = Path("data/bridge_scales/aging_series")

    p5 = BrainDrivenPerturbation.from_json(bridge_dir / "pink1_day05_bridge_scales.json")
    p15 = BrainDrivenPerturbation.from_json(bridge_dir / "pink1_day15_bridge_scales.json")
    p25 = BrainDrivenPerturbation.from_json(bridge_dir / "pink1_day25_bridge_scales.json")
    p30 = BrainDrivenPerturbation.from_json(bridge_dir / "pink1_day30_bridge_scales.json")

    # Early hyperexcitability > mid > late > terminal
    assert p5.motor_scale > p15.motor_scale > p25.motor_scale > p30.motor_scale

    # Rescue maintains higher motor scale than untreated mutant at 25 and 30 days
    r25 = BrainDrivenPerturbation.from_json(bridge_dir / "pink1_parkin_OE_day25_bridge_scales.json")
    r30 = BrainDrivenPerturbation.from_json(bridge_dir / "pink1_parkin_OE_day30_bridge_scales.json")

    assert r25.motor_scale > p25.motor_scale
    assert r30.motor_scale > p30.motor_scale
