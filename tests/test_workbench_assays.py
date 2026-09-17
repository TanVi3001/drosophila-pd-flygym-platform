from __future__ import annotations

from drosophila_pd.workbench import LocomotionAssayAdapter, NeuralReadoutAssayAdapter


def test_locomotion_assay_does_not_rank_missing_readout_as_negative() -> None:
    assay = LocomotionAssayAdapter()
    missing = assay.evaluate({"overall_pass": True})
    assert missing.readout_available is False
    assert missing.qc_pass is False
    assert missing.status == "INSUFFICIENT_READOUT"

    comparison = assay.compare(
        {"derived_locomotion_metrics": {"speed": 1.0}},
        {"derived_locomotion_metrics": {"speed": 2.0}},
        primary_metric="speed",
    )
    assert comparison["status"] == "EXPLORATORY"
    assert comparison["absolute_delta"] == 1.0


def test_locomotion_assay_rejects_null_and_nonfinite_readouts() -> None:
    assay = LocomotionAssayAdapter()
    evaluation = assay.evaluate(
        {
            "derived_locomotion_metrics": {
                "speed": 1.0,
                "orientation": None,
                "turning": float("nan"),
            }
        }
    )

    assert evaluation.readout_available is True
    assert evaluation.qc_pass is False
    assert evaluation.status == "QC_FAIL"
    assert any("orientation=null" in warning for warning in evaluation.warnings)
    assert any("turning=non_finite" in warning for warning in evaluation.warnings)


def test_neural_assay_uses_explicit_nested_metric_path() -> None:
    assay = NeuralReadoutAssayAdapter()
    reference = {
        "status": "PASS",
        "metrics": {"firing_rate_hz_per_active_neuron": {"mean": 10.0}},
    }
    condition = {
        "status": "PASS",
        "metrics": {"firing_rate_hz_per_active_neuron": {"mean": 12.5}},
    }

    evaluation = assay.evaluate(reference)
    comparison = assay.compare(
        reference,
        condition,
        primary_metric="metrics.firing_rate_hz_per_active_neuron.mean",
    )

    assert evaluation.qc_pass is True
    assert comparison["status"] == "EXPLORATORY"
    assert comparison["absolute_delta"] == 2.5


def test_neural_assay_rejects_missing_readout() -> None:
    evaluation = NeuralReadoutAssayAdapter().evaluate(
        {"status": "PASS", "metrics": {"mean": None}}
    )

    assert evaluation.qc_pass is False
    assert evaluation.status == "QC_FAIL"
