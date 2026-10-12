"""Explicit human-gated connection from an AI draft to Workbench execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from drosophila_pd.workbench.service import WorkbenchService
from drosophila_pd.workbench.models import StudySpec

from .contracts import AIStudySpec


@dataclass
class AIV2WorkbenchWorkflow:
    """Thin orchestration facade; every consequential transition is explicit.

    Creating a draft assesses support but does not approve or run it. Approval,
    job submission, and execution are separate calls to existing Workbench gates.
    """

    service: WorkbenchService

    def create_draft(self, draft: AIStudySpec) -> dict[str, Any]:
        if not isinstance(draft, AIStudySpec) or draft.approval_status != "DRAFT":
            raise ValueError("AI may submit only an unapproved AIStudySpec draft")
        metadata = dict(draft.study.metadata)
        metadata["ai_v2_provenance"] = {
            "schema_version": "ai-v2-provenance-1",
            "evidence_ids": list(draft.evidence_ids),
            "evidence_ids_sha256": _stable_hash(list(draft.evidence_ids)),
            **dict(draft.provenance or {}),
        }
        source_study = draft.study
        study_with_provenance = StudySpec(
            name=source_study.name,
            hypothesis=source_study.hypothesis,
            falsifiable_prediction=source_study.falsifiable_prediction,
            assay=source_study.assay,
            primary_metric=source_study.primary_metric,
            candidates=source_study.candidates,
            controls=source_study.controls,
            sources=source_study.sources,
            run_plan=source_study.run_plan,
            backend=source_study.backend,
            study_id=source_study.study_id,
            created_at=source_study.created_at,
            metadata=metadata,
        )
        study = self.service.create_research_study(study_with_provenance)
        assessment = self.service.get_support_assessment(study.study_id)
        return {
            "study": study.as_dict(),
            "support_assessment": assessment,
            "workflow_status": self.status(study.study_id),
        }

    def approve(self, study_id: str, *, reviewer: str) -> dict[str, Any]:
        return self.service.approve_support_assessment(study_id, reviewer=reviewer)

    def submit(self, study_id: str, *, candidate_id: str) -> dict[str, Any]:
        job = self.service.submit_job(study_id, {"candidate_id": candidate_id})
        return {"job": job.as_dict(), "workflow_status": self.status(study_id)}

    def run(self, job_id: str) -> dict[str, Any]:
        job = self.service.run_job(job_id)
        return {"job": job.as_dict(), "workflow_status": self.status(job.study_id)}

    def cancel(self, job_id: str) -> dict[str, Any]:
        job = self.service.cancel_job(job_id)
        return {"job": job.as_dict(), "workflow_status": self.status(job.study_id)}

    def resume(self, job_id: str) -> dict[str, Any]:
        job = self.service.resume_job(job_id)
        return {"job": job.as_dict(), "workflow_status": self.status(job.study_id)}

    def status(self, study_id: str) -> dict[str, Any]:
        study = self.service.get_study(study_id)
        assessment = self.service.get_support_assessment(study_id)
        approval = self.service.store.get_support_approval(study_id)
        jobs = self.service.list_jobs(study_id=study_id)
        if assessment is None:
            stage = "DRAFT_NOT_ASSESSED"
        elif not assessment.get("run_allowed"):
            stage = str(assessment.get("status", "BLOCKED"))
        elif approval is None:
            stage = "AWAITING_HUMAN_APPROVAL"
        elif not jobs:
            stage = "APPROVED_AWAITING_SUBMISSION"
        elif any(job.status.value in {"PENDING", "RUNNING"} for job in jobs):
            stage = "RUNS_IN_PROGRESS"
        elif any(job.status.value == "FAILED" for job in jobs):
            stage = "RUN_FAILED_OR_PARTIAL"
        else:
            stage = "RUNS_COMPLETED"
        report = self.service.get_report(study_id) if jobs else None
        return {
            "schema_version": "ai-v2-workflow-status-1",
            "study_id": study_id,
            "study_configuration_hash": study.configuration_hash,
            "stage": stage,
            "support_status": None if assessment is None else assessment.get("status"),
            "support_assessment_hash": None if assessment is None else assessment.get("assessment_hash"),
            "approval": approval,
            "jobs": [job.as_dict() for job in jobs],
            "report": report,
            "requires_human_decision": True,
            "scientific_scope": "Workflow and computational QC only; not biological validation.",
        }


def _stable_hash(value: Any) -> str:
    from drosophila_pd.workbench.models import stable_hash

    return stable_hash(value)


__all__ = ["AIV2WorkbenchWorkflow"]
