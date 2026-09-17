"""Assay contracts and conservative v0.1 locomotion evaluation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping, Protocol


@dataclass(frozen=True)
class AssayEvaluation:
    assay: str
    status: str
    readout_available: bool
    qc_pass: bool
    metrics: Mapping[str, Any]
    warnings: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "assay": self.assay,
            "status": self.status,
            "readout_available": self.readout_available,
            "qc_pass": self.qc_pass,
            "metrics": dict(self.metrics),
            "warnings": list(self.warnings),
        }


class AssayAdapter(Protocol):
    name: str

    def evaluate(self, result: Mapping[str, Any]) -> AssayEvaluation:
        ...

    def compare(
        self,
        reference: Mapping[str, Any],
        condition: Mapping[str, Any],
        *,
        primary_metric: str,
    ) -> Mapping[str, Any]:
        ...


class LocomotionAssayAdapter:
    """Evaluate only the presence and finiteness of locomotion readouts.

    It intentionally does not convert a completed simulation into a biological
    conclusion, and it never makes missing readouts rank as negative results.
    """

    name = "locomotion"

    def evaluate(self, result: Mapping[str, Any]) -> AssayEvaluation:
        metrics = result.get("derived_locomotion_metrics", {})
        if not isinstance(metrics, Mapping) or not metrics:
            return AssayEvaluation(
                assay=self.name,
                status="INSUFFICIENT_READOUT",
                readout_available=False,
                qc_pass=False,
                metrics={},
                warnings=("derived_locomotion_metrics is missing or empty",),
            )
        warnings: list[str] = []
        if result.get("overall_pass") is False:
            warnings.append("backend report overall_pass is false")
        invalid: list[str] = []

        def inspect(value: Any, path: str) -> None:
            if value is None:
                invalid.append(f"{path}=null")
            elif isinstance(value, Mapping):
                for child_key, child_value in value.items():
                    inspect(child_value, f"{path}.{child_key}")
            elif isinstance(value, (list, tuple)):
                for index, child_value in enumerate(value):
                    inspect(child_value, f"{path}[{index}]")
            elif isinstance(value, (int, float)) and not isinstance(value, bool):
                if not math.isfinite(float(value)):
                    invalid.append(f"{path}=non_finite")

        for key, value in metrics.items():
            inspect(value, str(key))
        if invalid:
            warnings.append(f"invalid metric value(s): {', '.join(sorted(invalid))}")
        qc_pass = not warnings
        return AssayEvaluation(
            assay=self.name,
            status="PASS" if qc_pass else "QC_FAIL",
            readout_available=True,
            qc_pass=qc_pass,
            metrics=dict(metrics),
            warnings=tuple(warnings),
        )

    def compare(
        self,
        reference: Mapping[str, Any],
        condition: Mapping[str, Any],
        *,
        primary_metric: str,
    ) -> Mapping[str, Any]:
        reference_eval = self.evaluate(reference)
        condition_eval = self.evaluate(condition)
        if not reference_eval.qc_pass or not condition_eval.qc_pass:
            return {
                "status": "NOT_ELIGIBLE",
                "primary_metric": primary_metric,
                "reason": "reference or condition failed assay QC",
            }
        reference_value = reference_eval.metrics.get(primary_metric)
        condition_value = condition_eval.metrics.get(primary_metric)
        if not isinstance(reference_value, (int, float)) or not isinstance(condition_value, (int, float)):
            return {
                "status": "NOT_ELIGIBLE",
                "primary_metric": primary_metric,
                "reason": "primary metric is not available as a finite scalar",
            }
        return {
            "status": "EXPLORATORY",
            "primary_metric": primary_metric,
            "reference": reference_value,
            "condition": condition_value,
            "absolute_delta": condition_value - reference_value,
            "note": "No seed sensitivity, CI, or biological equivalence claim is made here.",
        }


class NeuralReadoutAssayAdapter:
    """Validate finite neural readouts without assigning biological meaning."""

    name = "neural"

    def evaluate(self, result: Mapping[str, Any]) -> AssayEvaluation:
        metrics = result.get("metrics", {})
        if not isinstance(metrics, Mapping) or not metrics:
            return AssayEvaluation(
                assay=self.name,
                status="INSUFFICIENT_READOUT",
                readout_available=False,
                qc_pass=False,
                metrics={},
                warnings=("metrics is missing or empty",),
            )
        warnings: list[str] = []
        if str(result.get("status", "PASS")).upper() in {"FAILED", "FAIL", "ERROR"}:
            warnings.append("backend report status is not PASS")
        invalid: list[str] = []
        finite_numeric_values = 0

        def inspect(value: Any, path: str) -> None:
            nonlocal finite_numeric_values
            if value is None:
                # Empty active-neuron summaries and time bounds are valid for
                # a completely silent computational condition.  The primary
                # metric comparison still rejects a missing scalar path.
                return
            elif isinstance(value, Mapping):
                for child_key, child_value in value.items():
                    inspect(child_value, f"{path}.{child_key}")
            elif isinstance(value, (list, tuple)):
                for index, child_value in enumerate(value):
                    inspect(child_value, f"{path}[{index}]")
            elif isinstance(value, (int, float)) and not isinstance(value, bool):
                if not math.isfinite(float(value)):
                    invalid.append(f"{path}=non_finite")
                else:
                    finite_numeric_values += 1

        for key, value in metrics.items():
            inspect(value, str(key))
        if invalid:
            warnings.append(f"invalid neural metric value(s): {', '.join(sorted(invalid))}")
        if finite_numeric_values == 0:
            warnings.append("metrics contains no finite numeric readout")
        qc_pass = not warnings
        return AssayEvaluation(
            assay=self.name,
            status="PASS" if qc_pass else "QC_FAIL",
            readout_available=True,
            qc_pass=qc_pass,
            metrics=dict(metrics),
            warnings=tuple(warnings),
        )

    def compare(
        self,
        reference: Mapping[str, Any],
        condition: Mapping[str, Any],
        *,
        primary_metric: str,
    ) -> Mapping[str, Any]:
        reference_eval = self.evaluate(reference)
        condition_eval = self.evaluate(condition)
        if not reference_eval.qc_pass or not condition_eval.qc_pass:
            return {
                "status": "NOT_ELIGIBLE",
                "primary_metric": primary_metric,
                "reason": "reference or condition failed neural assay QC",
            }
        reference_value = _read_scalar(reference, primary_metric)
        condition_value = _read_scalar(condition, primary_metric)
        if reference_value is None or condition_value is None:
            return {
                "status": "NOT_ELIGIBLE",
                "primary_metric": primary_metric,
                "reason": "primary neural metric is not available as a finite scalar",
            }
        return {
            "status": "EXPLORATORY",
            "primary_metric": primary_metric,
            "reference": reference_value,
            "condition": condition_value,
            "absolute_delta": condition_value - reference_value,
            "note": "No seed sensitivity, CI, or biological equivalence claim is made here.",
        }


def _read_scalar(result: Mapping[str, Any], path: str) -> float | None:
    """Resolve an explicit metric path from the report or its metrics map."""

    roots: list[Mapping[str, Any]] = [result]
    metrics = result.get("metrics")
    if isinstance(metrics, Mapping):
        roots.append(metrics)
    readouts = result.get("readouts")
    if isinstance(readouts, Mapping):
        roots.append(readouts)
    for root in roots:
        value: Any = root
        for part in str(path).split("."):
            if not isinstance(value, Mapping) or part not in value:
                value = None
                break
            value = value[part]
        if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)):
            return float(value)
    return None


__all__ = ["AssayAdapter", "AssayEvaluation", "LocomotionAssayAdapter", "NeuralReadoutAssayAdapter"]
