"""Unit tests for the molecular-to-neural bridge module."""

from __future__ import annotations

import pytest

from drosophila_pd.parkinson.molecular_bridge import (
    compute_derived_bridge_parameters,
    mitochondrial_damage_to_coupling_scale,
    muddapu_energy_to_survival,
    ppl1_survival_to_motor_scale,
)


class TestMolecularBridge:
    def test_muddapu_energy_to_survival_boundaries(self) -> None:
        # 0% deficiency -> full survival (~1.0)
        s_0 = muddapu_energy_to_survival(0.0)
        assert s_0 > 0.99

        # 100% deficiency -> complete loss (~0.0)
        s_1 = muddapu_energy_to_survival(1.0)
        assert s_1 < 0.01

        # Half point at e_half (0.40) -> exactly 0.50
        s_half = muddapu_energy_to_survival(0.40)
        assert s_half == pytest.approx(0.50, abs=1e-5)

    def test_ppl1_survival_to_motor_scale_bounds(self) -> None:
        # Full survival -> motor_scale = 1.0
        m_full = ppl1_survival_to_motor_scale(1.0)
        assert m_full == pytest.approx(1.0, abs=1e-5)

        # Zero survival -> floor = 0.50
        m_zero = ppl1_survival_to_motor_scale(0.0)
        assert m_zero == pytest.approx(0.50, abs=1e-5)

        # Compensation boost
        m_boost = ppl1_survival_to_motor_scale(1.0, early_compensation_boost=0.15)
        assert m_boost == pytest.approx(1.15, abs=1e-5)

    def test_mitochondrial_damage_to_coupling_scale_bounds(self) -> None:
        c_intact = mitochondrial_damage_to_coupling_scale(0.0)
        assert c_intact == pytest.approx(1.0, abs=1e-5)

        c_severe = mitochondrial_damage_to_coupling_scale(1.0)
        assert c_severe == pytest.approx(0.40, abs=1e-5)

    def test_compute_derived_bridge_parameters(self) -> None:
        params = compute_derived_bridge_parameters(
            energy_deficiency=0.35,
            mitochondrial_disruption=0.50,
            early_compensation_boost=0.0,
            rescue_recovery=0.0,
        )
        assert "ppl1_survival_fraction" in params
        assert "motor_scale" in params
        assert "coupling_scale" in params
        assert 0.5 <= params["motor_scale"] <= 1.2
        assert 0.4 <= params["coupling_scale"] <= 1.1
