"""Opt-in synthetic backend for internal staging smoke tests only."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Mapping

from .adapters import BackendRunContext, BackendRunResult
from .assays import AssayEvaluation
from .models import CapabilityDescriptor
from .service import WorkbenchService
from .support import MappingRecord


class SyntheticStagingBackend:
    name = "staging_fixture"
    result_path = Path("result.json")

    def describe(self) -> CapabilityDescriptor:
        return CapabilityDescriptor(
            name=self.name,
            display_name="Synthetic staging fixture (not a biological simulator)",
            ready=True,
            supported_assays=("synthetic_demo",),
            supported_interventions=("none", "activation"),
            limitations=("Synthetic arbitrary values only; not FlyWire, MN9, or biological evidence.",),
        )

    def validate(self, study: Any, config: Mapping[str, Any]) -> tuple[str, ...]:
        errors = []
        if study.assay != "synthetic_demo":
            errors.append("staging fixture supports only synthetic_demo")
        if not config.get("candidate_id"):
            errors.append("candidate_id is required")
        return tuple(errors)

    def run(self, context: BackendRunContext) -> BackendRunResult:
        context.artifact_dir.mkdir(parents=True, exist_ok=True)
        candidate = next(
            item for item in context.study.candidates
            if item.candidate_id == context.job.config.get("candidate_id")
        )
        value = 1.25 if candidate.intervention.get("type") == "activation" else 1.0
        (context.artifact_dir / self.result_path).write_text(
            json.dumps({
                "status": "SYNTHETIC_ONLY",
                "notice": "Arbitrary fixture values. Not biological data or a simulator output.",
                "metrics": {"response": value},
            }, sort_keys=True),
            encoding="utf-8",
        )
        context.log_path.write_text("Synthetic staging fixture; no biological simulator called.\n", encoding="utf-8")
        return BackendRunResult(
            command=("synthetic-staging-fixture",),
            interpreter=sys.executable,
            repo_root=Path(__file__).resolve().parents[3].as_posix(),
            exit_code=0,
        )


class SyntheticStagingAssay:
    name = "synthetic_demo"

    def evaluate(self, result: Mapping[str, Any]) -> AssayEvaluation:
        metrics = result.get("metrics", {})
        valid = (
            result.get("status") == "SYNTHETIC_ONLY"
            and isinstance(metrics, Mapping)
            and isinstance(metrics.get("response"), (int, float))
        )
        return AssayEvaluation(
            assay=self.name,
            status="SYNTHETIC_FIXTURE_PASS" if valid else "FAIL",
            readout_available=valid,
            qc_pass=valid,
            metrics=dict(metrics) if isinstance(metrics, Mapping) else {},
        )

    def compare(self, reference: Mapping[str, Any], condition: Mapping[str, Any], *, primary_metric: str) -> dict[str, Any]:
        return {"status": "SYNTHETIC_ONLY", "primary_metric": primary_metric}


def install_staging_fixture(service: WorkbenchService) -> None:
    """Install an explicit synthetic backend and its visibly non-biological map."""

    service.adapters[SyntheticStagingBackend.name] = SyntheticStagingBackend()
    service.assays[SyntheticStagingAssay.name] = SyntheticStagingAssay()
    mapping = MappingRecord(
        mapping_id="synthetic-staging-map-v1",
        version="1",
        biological_target="synthetic target",
        backend="staging_fixture",
        id_namespace="synthetic_id",
        dataset_id="synthetic_dataset",
        intervention_type="activation",
        target_ids=("SYNTHETIC_TARGET_ID",),
        readout_ids=("SYNTHETIC_READOUT_ID",),
        sources=({"citation": "Synthetic staging fixture; not a scientific source.", "locator": "built-in smoke-test contract"},),
        review_status="COMPUTATIONALLY_REVIEWED",
        context={},
        reviewer="fixture-contract-only; not a biological reviewer",
        reviewed_at="2026-10-06T00:00:00Z",
        limitations=("Synthetic-only mapping for API smoke tests; not a Drosophila neuron mapping.",),
    )
    existing = service.list_mapping_records().get(mapping.mapping_id)
    if existing is None:
        service.register_mapping_record(mapping)
    elif MappingRecord.from_dict(existing).record_hash != mapping.record_hash:
        raise RuntimeError("reserved synthetic staging mapping ID conflicts with stored content")


__all__ = ["SyntheticStagingBackend", "SyntheticStagingAssay", "install_staging_fixture"]
