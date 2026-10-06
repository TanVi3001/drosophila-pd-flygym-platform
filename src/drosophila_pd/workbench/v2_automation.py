"""Guarded AI V2 workflow orchestration over existing Workbench services.

The automation layer deliberately exposes a fixed set of researcher-facing
operations. It does not grant a language model tools, shell access, approval
authority, or control over QC and ranking calculations.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import queue
import re
import sys
import tempfile
import threading
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from .models import JobStatus, stable_hash, utc_timestamp
from .service import WorkbenchService


_ZERO_HASH = "0" * 64
_SAFE_COMPONENT = re.compile(r"[^A-Za-z0-9._-]+")
_AUDIT_LOCKS: dict[str, Any] = {}
_AUDIT_LOCKS_GUARD = threading.Lock()


class WorkbenchV2Automation:
    """Fixed-tool workflow API with external tamper-evident audit records."""

    TOOL_ALLOWLIST = (
        "read_workflow_status",
        "assess_support",
        "record_human_approval",
        "submit_screening",
        "run_approved_jobs",
        "resume_failed_jobs",
        "generate_artifact_report",
    )
    MAX_JOBS = 100
    MAX_TIMEOUT_S = 3600.0
    CANCEL_JOIN_GRACE_S = 10.5

    def __init__(self, service: WorkbenchService, *, output_root: str | Path) -> None:
        self.service = service
        self.output_root = Path(output_root).expanduser().resolve()
        self.audit_path = self.output_root / "workflow_events.jsonl"
        self.reports_root = self.output_root / "reports"

    def status(self, study_id: str) -> dict[str, Any]:
        study = self.service.get_study(study_id)
        if study.metadata.get("workflow_contract") != "support-gated-1":
            raise ValueError("workflow_requires_support_gated_study")
        assessment = self.service.get_support_assessment(study_id)
        approval = self.service.store.get_support_approval(study_id)
        approval_valid = bool(
            assessment
            and approval
            and assessment.get("study_configuration_hash") == study.configuration_hash
            and approval.get("study_configuration_hash") == study.configuration_hash
            and approval.get("assessment_hash") == assessment.get("assessment_hash")
            and approval.get("status") == "FROZEN_FOR_COMPUTATIONAL_RUN"
            and assessment.get("run_allowed") is True
        )
        submission = self._read_submission(study_id, required=False)
        study_jobs = self.service.list_jobs(study_id=study_id)
        if submission is not None and isinstance(submission.get("job_ids"), list):
            submitted_ids = {str(item) for item in submission["job_ids"]}
            jobs = [job for job in study_jobs if job.job_id in submitted_ids]
        else:
            jobs = study_jobs
        counts = {status.value: 0 for status in JobStatus}
        for job in jobs:
            counts[job.status.value] += 1

        if assessment is None:
            state = "ASSESSMENT_REQUIRED"
        elif not assessment.get("run_allowed"):
            state = "BLOCKED_BY_SUPPORT_GATE"
        elif not approval_valid:
            state = "HUMAN_APPROVAL_REQUIRED"
        elif submission is None:
            state = "READY_TO_SUBMIT"
        elif counts[JobStatus.PENDING.value] or counts[JobStatus.RUNNING.value]:
            state = "READY_TO_RUN_OR_RESUME"
        else:
            state = "RUNS_RECORDED"

        allowed = ["read_workflow_status", "assess_support"]
        if assessment and assessment.get("run_allowed") and not approval_valid:
            allowed.append("record_human_approval")
        if approval_valid:
            allowed.extend(("submit_screening", "run_approved_jobs", "resume_failed_jobs"))
        allowed.append("generate_artifact_report")
        chain = self.verify_audit_chain()
        return {
            "schema_version": "workbench-v2-workflow-status-1",
            "study_id": study_id,
            "study_configuration_sha256": study.configuration_hash,
            "workflow_state": state,
            "assessment": {
                "status": assessment.get("status") if assessment else "NOT_CREATED",
                "run_allowed": bool(assessment and assessment.get("run_allowed")),
                "assessment_sha256": assessment.get("assessment_hash") if assessment else None,
            },
            "human_approval": {
                "valid": approval_valid,
                "status": approval.get("status") if approval else "NOT_APPROVED",
                "approval_sha256": stable_hash(approval) if approval else None,
            },
            "screening": {
                "submitted": submission is not None,
                "expected_job_count": submission.get("expected_job_count") if submission else 0,
                "status_counts": counts,
            },
            "allowed_tools": allowed,
            "tool_policy": {
                "allowlist": list(self.TOOL_ALLOWLIST),
                "automatic_retries": 0,
                "timeout_max_s": self.MAX_TIMEOUT_S,
                "resume_requires_explicit_job_ids": True,
                "arbitrary_shell_or_code": False,
                "ai_can_approve_or_change_study": False,
            },
            "audit_chain": chain,
            "scientific_scope": "Workflow state only; computational outputs are not biological validation.",
        }

    def assess(self, study_id: str, *, required_context: Mapping[str, Any] | None = None) -> dict[str, Any]:
        study = self.service.get_study(study_id)
        self._require_gated_study(study)
        context = dict(required_context or {})
        self._event("SUPPORT_ASSESSMENT_REQUESTED", study_id, {
            "study_configuration_sha256": study.configuration_hash,
            "required_context_sha256": stable_hash(context),
        })
        try:
            assessment = self.service.assess_support(study_id, required_context=context)
        except Exception as error:
            self._event("ACTION_REJECTED", study_id, {
                "action": "assess_support",
                "error_type": type(error).__name__,
            })
            raise
        self._event("SUPPORT_ASSESSMENT_COMPLETED", study_id, {
            "assessment_sha256": assessment.get("assessment_hash"),
            "assessment_status": assessment.get("status"),
            "run_allowed": bool(assessment.get("run_allowed")),
        })
        return assessment

    def approve(self, study_id: str, *, reviewer: str) -> dict[str, Any]:
        study = self.service.get_study(study_id)
        self._require_gated_study(study)
        if not isinstance(reviewer, str) or not reviewer.strip():
            raise ValueError("a human reviewer name is required")
        assessment = self.service.get_support_assessment(study_id)
        self._event("HUMAN_APPROVAL_REQUESTED", study_id, {
            "study_configuration_sha256": study.configuration_hash,
            "reviewer_sha256": hashlib.sha256(reviewer.strip().encode("utf-8")).hexdigest(),
            "assessment_sha256": assessment.get("assessment_hash") if assessment else None,
        })
        try:
            approval = self.service.approve_support_assessment(study_id, reviewer=reviewer)
        except Exception as error:
            self._event("ACTION_REJECTED", study_id, {
                "action": "record_human_approval",
                "error_type": type(error).__name__,
            })
            raise
        self._event("HUMAN_APPROVAL_RECORDED", study_id, {
            "approval_sha256": stable_hash(approval),
            "assessment_sha256": approval.get("assessment_hash"),
        })
        return approval

    def submit(
        self,
        study_id: str,
        *,
        seeds: Sequence[int | str],
        candidate_ids: Sequence[str] | None = None,
        base_config: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        study = self.service.get_study(study_id)
        self._require_frozen_approval(study)
        selected = list(candidate_ids) if candidate_ids is not None else [
            candidate.candidate_id for candidate in study.candidates
        ]
        seed_values = list(seeds)
        expected_jobs = len(selected) * len(seed_values)
        if expected_jobs < 1 or expected_jobs > self.MAX_JOBS:
            raise ValueError(f"screening job count must be between 1 and {self.MAX_JOBS}")
        self._event("SCREENING_SUBMISSION_REQUESTED", study_id, {
            "study_configuration_sha256": study.configuration_hash,
            "candidate_count": len(selected),
            "seed_count": len(seed_values),
            "seeds_sha256": stable_hash(seed_values),
            "candidate_ids_sha256": stable_hash(selected),
            "base_config_sha256": stable_hash(dict(base_config or {})),
            "expected_job_count": expected_jobs,
        })
        try:
            submission = self.service.submit_screening(
                study_id,
                seed_values,
                candidate_ids=selected,
                base_config=base_config,
            )
        except Exception as error:
            self._event("ACTION_REJECTED", study_id, {
                "action": "submit_screening",
                "error_type": type(error).__name__,
            })
            raise
        self._event("SCREENING_SUBMITTED", study_id, {
            "submission_sha256": stable_hash({
                "study_id": study_id,
                "candidate_ids": selected,
                "seeds": seed_values,
                "job_ids": submission.get("job_ids", []),
            }),
            "submitted_job_count": submission.get("submitted_job_count", 0),
            "status": submission.get("status"),
        })
        return submission

    def run(self, study_id: str, *, timeout_s: float = 600.0) -> dict[str, Any]:
        study = self.service.get_study(study_id)
        self._require_frozen_approval(study)
        timeout = self._validate_timeout(timeout_s)
        submission = self._read_submission(study_id, required=True)
        job_ids = submission.get("job_ids")
        if not isinstance(job_ids, list) or not job_ids or len(job_ids) > self.MAX_JOBS:
            raise ValueError("screening submission has no jobs or exceeds the workflow job limit")
        self._event("SCREENING_RUN_REQUESTED", study_id, {
            "submission_sha256": stable_hash({
                "study_id": study_id,
                "job_ids": job_ids,
                "candidate_ids": submission.get("candidate_ids", []),
                "seeds": submission.get("seeds", []),
            }),
            "job_count": len(job_ids),
            "timeout_s": timeout,
            "automatic_retries": 0,
        })

        deadline = time.monotonic() + timeout
        timed_out = False
        for raw_job_id in job_ids:
            job_id = str(raw_job_id)
            job = self.service.get_job(job_id)
            if job.study_id != study_id or job.backend != study.backend:
                raise ValueError("screening job scope does not match the frozen study")
            if job.status != JobStatus.PENDING:
                continue
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                break
            self._event("JOB_STARTED", study_id, {"job_id": job_id, "timeout_remaining_s": remaining})
            result_queue: queue.Queue[tuple[bool, Any]] = queue.Queue(maxsize=1)

            def execute(selected_job_id: str = job_id) -> None:
                try:
                    result_queue.put((True, self.service.run_job(selected_job_id)))
                except Exception as error:  # surfaced as a type only; raw error text may contain sensitive paths
                    result_queue.put((False, error))

            worker = threading.Thread(target=execute, name=f"workbench-v2-{job_id}", daemon=True)
            worker.start()
            worker.join(timeout=remaining)
            if worker.is_alive():
                timed_out = True
                self._event("JOB_TIMEOUT_REQUESTED", study_id, {"job_id": job_id})
                try:
                    self.service.cancel_job(job_id)
                except (KeyError, ValueError):
                    pass
                worker.join(timeout=self.CANCEL_JOIN_GRACE_S)
                self._event("JOB_TIMEOUT_HANDLED", study_id, {
                    "job_id": job_id,
                    "worker_stopped": not worker.is_alive(),
                })
                break
            succeeded, result = result_queue.get_nowait()
            self._event("JOB_FINISHED", study_id, {
                "job_id": job_id,
                "status": result.status.value if succeeded else "ERROR",
                "error_type": None if succeeded else type(result).__name__,
            })

        statuses = []
        for raw_job_id in job_ids:
            try:
                job = self.service.get_job(str(raw_job_id))
            except KeyError:
                statuses.append({"job_id": str(raw_job_id), "status": "MISSING"})
                continue
            statuses.append({"job_id": job.job_id, "status": job.status.value})
        completed = sum(item["status"] == JobStatus.COMPLETED.value for item in statuses)
        all_complete = completed == len(statuses)
        summary = {
            "schema_version": "workbench-v2-screening-run-1",
            "study_id": study_id,
            "status": "TIMED_OUT" if timed_out else ("COMPLETED" if all_complete else "PARTIAL"),
            "job_count": len(statuses),
            "completed_job_count": completed,
            "timed_out": timed_out,
            "automatic_retries": 0,
            "jobs": statuses,
            "resume_policy": "Failed or cancelled jobs require explicit resume by job ID.",
            "scientific_scope": "Computational runs only; these outputs are not biological validation.",
        }
        self._event("SCREENING_RUN_FINISHED", study_id, {
            "status": summary["status"],
            "job_count": len(statuses),
            "completed_job_count": completed,
            "timed_out": timed_out,
        })
        return summary

    def resume(self, study_id: str, *, job_ids: Sequence[str]) -> dict[str, Any]:
        study = self.service.get_study(study_id)
        self._require_frozen_approval(study)
        selected = list(job_ids)
        if not selected or len(selected) > self.MAX_JOBS or len(selected) != len(set(selected)):
            raise ValueError("resume requires 1 to 100 unique explicit job IDs")
        records = [self.service.get_job(job_id) for job_id in selected]
        if any(job.study_id != study_id for job in records):
            raise ValueError("resume job belongs to a different study")
        if any(job.status not in {JobStatus.FAILED, JobStatus.CANCELLED} for job in records):
            raise ValueError("only failed or cancelled jobs can be explicitly resumed")
        self._event("EXPLICIT_RESUME_REQUESTED", study_id, {
            "job_ids_sha256": stable_hash(selected),
            "job_count": len(selected),
        })
        resumed = []
        try:
            for job in records:
                job_id = job.job_id
                updated = self.service.resume_job(job_id)
                resumed.append({"job_id": updated.job_id, "status": updated.status.value})
        except Exception as error:
            self._event("ACTION_REJECTED", study_id, {
                "action": "resume_failed_jobs",
                "error_type": type(error).__name__,
                "resumed_count_before_rejection": len(resumed),
            })
            raise
        self._event("EXPLICIT_RESUME_RECORDED", study_id, {
            "resumed_job_count": len(resumed),
            "job_ids_sha256": stable_hash([item["job_id"] for item in resumed]),
        })
        return {
            "schema_version": "workbench-v2-resume-1",
            "study_id": study_id,
            "resumed_job_count": len(resumed),
            "jobs": resumed,
            "automatic_retries": 0,
        }

    def report(self, study_id: str) -> dict[str, Any]:
        study = self.service.get_study(study_id)
        self._require_gated_study(study)
        core_report = self.service.get_report(study_id)
        assessment = self.service.get_support_assessment(study_id)
        approval = self.service.store.get_support_approval(study_id)
        jobs = self.service.list_jobs(study_id=study_id)
        report_rows = {str(row.get("job_id")): row for row in core_report.get("results", [])}
        result_rows = []
        manifest_hashes = []
        for job in jobs:
            row = report_rows.get(job.job_id, {})
            result_rows.append({
                "job_id": job.job_id,
                "candidate_id": job.config.get("candidate_id"),
                "backend": job.backend,
                "status": job.status.value,
                "attempt": job.attempt,
                "metrics": row.get("metrics", {}),
                "qc": row.get("qc"),
                "candidate_configuration_sha256": job.config.get("candidate_configuration_hash"),
                "mapping_record_sha256": job.config.get("mapping_record_hash"),
            })
            if job.manifest_path:
                manifest_path = Path(job.manifest_path)
                if manifest_path.is_file():
                    manifest_hashes.append({
                        "job_id": job.job_id,
                        "manifest_sha256": _file_sha256(manifest_path),
                    })
        audit = self.verify_audit_chain()
        lineage = study.metadata.get("ai_draft_lineage")
        if not isinstance(lineage, Mapping):
            lineage = None
        payload: dict[str, Any] = {
            "schema_version": "workbench-v2-artifact-report-1",
            "report_id": f"v2-report-{uuid.uuid4().hex}",
            "generated_at": utc_timestamp(),
            "study_id": study_id,
            "study_configuration_sha256": study.configuration_hash,
            "assay": study.assay,
            "primary_metric": study.primary_metric,
            "backend": study.backend,
            "support_assessment_sha256": assessment.get("assessment_hash") if assessment else None,
            "human_approval_sha256": stable_hash(approval) if approval else None,
            "model_provider": "NOT_USED_FOR_WORKFLOW_EXECUTION_OR_METRIC_CALCULATION",
            "prompt_template_sha256": lineage.get("prompt_template_sha256") if lineage else None,
            "evidence_corpus_sha256": lineage.get("evidence_corpus_sha256") if lineage else None,
            "ai_draft_lineage": lineage,
            "retrieval_used_for_execution": False,
            "results": result_rows,
            "run_manifest_hashes": manifest_hashes,
            "core_decision_report_status": core_report.get("status"),
            "audit_chain": audit,
            "claim_boundary": [
                "This report summarizes checked Workbench artifacts and QC outputs.",
                "No AI-generated metrics, QC decisions, rankings, or biological conclusions are included.",
                "Computational completion does not establish biological or wet-lab validity.",
            ],
        }
        payload["report_sha256"] = stable_hash(payload)
        safe_study_id = _SAFE_COMPONENT.sub("_", study_id).strip("._") or "unnamed"
        target = self.reports_root / safe_study_id / f"{payload['report_id']}.json"
        _write_new_json(target, payload)
        self._event("ARTIFACT_REPORT_CREATED", study_id, {
            "report_sha256": payload["report_sha256"],
            "result_count": len(result_rows),
            "manifest_count": len(manifest_hashes),
        })
        payload["artifact_path"] = target.as_posix()
        return payload

    def verify_audit_chain(self) -> dict[str, Any]:
        lock = self._audit_lock()
        with lock:
            if not self.audit_path.exists():
                return {"status": "EMPTY", "event_count": 0, "head_sha256": _ZERO_HASH}
            previous_hash = _ZERO_HASH
            count = 0
            try:
                with self.audit_path.open("r", encoding="utf-8") as stream:
                    for line_number, line in enumerate(stream, 1):
                        if not line.strip():
                            continue
                        item = json.loads(line)
                        recorded_hash = item.pop("event_sha256", None)
                        if item.get("sequence") != count + 1 or item.get("previous_event_sha256") != previous_hash:
                            raise ValueError(f"audit chain sequence/link mismatch at line {line_number}")
                        actual_hash = stable_hash(item)
                        if recorded_hash != actual_hash:
                            raise ValueError(f"audit chain checksum mismatch at line {line_number}")
                        previous_hash = actual_hash
                        count += 1
            except (OSError, json.JSONDecodeError) as error:
                raise ValueError("workflow audit log is unreadable") from error
            return {"status": "VALID", "event_count": count, "head_sha256": previous_hash}

    def _event(self, event_type: str, study_id: str, details: Mapping[str, Any]) -> None:
        self.output_root.mkdir(parents=True, exist_ok=True)
        lock = self._audit_lock()
        with lock:
            chain = self.verify_audit_chain()
            event = {
                "sequence": chain["event_count"] + 1,
                "occurred_at": datetime.now(UTC).isoformat(),
                "event_type": event_type,
                "actor": "workbench_service_or_explicit_human",
                "study_id": study_id,
                "details": dict(details),
                "previous_event_sha256": chain["head_sha256"],
            }
            event["event_sha256"] = stable_hash(event)
            encoded = (json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
            descriptor = os.open(self.audit_path, os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
            try:
                with os.fdopen(descriptor, "ab") as stream:
                    stream.write(encoded)
                    stream.flush()
                    os.fsync(stream.fileno())
            except Exception:
                # fdopen owns the descriptor after entry; let the original error propagate.
                raise

    def _audit_lock(self) -> Any:
        key = str(self.audit_path)
        with _AUDIT_LOCKS_GUARD:
            return _AUDIT_LOCKS.setdefault(key, threading.RLock())

    def _require_frozen_approval(self, study: Any) -> None:
        self._require_gated_study(study)
        # Delegate the authoritative freshness/mapping check to the existing service gate.
        self.service._require_support_freeze(study)

    @staticmethod
    def _require_gated_study(study: Any) -> None:
        if study.metadata.get("workflow_contract") != "support-gated-1":
            raise ValueError("workflow_requires_support_gated_study")

    def _read_submission(self, study_id: str, *, required: bool) -> dict[str, Any] | None:
        safe_study_id = _SAFE_COMPONENT.sub("_", study_id).strip("._") or "unnamed"
        path = self.service.artifact_root / safe_study_id / "screening_submission.json"
        if not path.is_file():
            if required:
                raise ValueError("no screening submission exists for this study")
            return None
        try:
            result = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError("screening submission is not valid JSON") from error
        if not isinstance(result, dict) or result.get("study_id") != study_id:
            raise ValueError("screening submission does not match the selected study")
        return result

    @classmethod
    def _validate_timeout(cls, value: float) -> float:
        if isinstance(value, bool):
            raise ValueError("timeout_s must be a finite number between 0.01 and 3600")
        try:
            timeout = float(value)
        except (TypeError, ValueError) as error:
            raise ValueError("timeout_s must be a finite number between 0.01 and 3600") from error
        if not math.isfinite(timeout) or not 0.01 <= timeout <= cls.MAX_TIMEOUT_S:
            raise ValueError("timeout_s must be a finite number between 0.01 and 3600")
        return timeout


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_new_json(target: Path, value: Mapping[str, Any]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".workflow-report-", suffix=".tmp", dir=target.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, target)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


__all__ = ["WorkbenchV2Automation"]
