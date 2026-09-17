"""Auditable evidence bundles and lab handoff dossiers.

This module only packages information already present in a study, its run
manifests, and explicit user-supplied metadata. Missing fields stay ``null``
or ``not_provided``; the builder never guesses a driver line, effect size, or
biological interpretation.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from .models import CandidateSpec, StudySpec, jsonable, stable_hash, utc_timestamp


REVIEW_DECISIONS = frozenset({"pending", "approved", "rejected", "needs_revision"})


@dataclass(frozen=True)
class LabHandoff:
    """One candidate's computational-to-experimental handoff record."""

    study_id: str
    candidate_id: str
    generated_at: str
    hypothesis: str
    falsifiable_prediction: str
    target: str | None
    cell_type: str | None
    connectome_version: str | None
    simulated_intervention: Mapping[str, Any]
    proposed_real_intervention: Mapping[str, Any] | None
    assay: str
    controls: tuple[Mapping[str, Any], ...]
    confounds: tuple[Any, ...]
    primary_metric: str
    predicted_effect: Mapping[str, Any]
    uncertainty: Mapping[str, Any]
    model_limitations: tuple[str, ...]
    driver_line: Mapping[str, Any] | None
    validation_plan: tuple[Any, ...]
    evidence: tuple[Mapping[str, Any], ...]
    computation: Mapping[str, Any]
    reviewer: Mapping[str, Any]
    decision: str
    handoff_status: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "handoff_version": 1,
            "study_id": self.study_id,
            "candidate_id": self.candidate_id,
            "generated_at": self.generated_at,
            "hypothesis": self.hypothesis,
            "falsifiable_prediction": self.falsifiable_prediction,
            "target": self.target,
            "cell_type": self.cell_type,
            "connectome_version": self.connectome_version,
            "simulated_intervention": jsonable(self.simulated_intervention),
            "proposed_real_intervention": jsonable(self.proposed_real_intervention),
            "assay": self.assay,
            "controls": jsonable(self.controls),
            "confounds": jsonable(self.confounds),
            "primary_metric": self.primary_metric,
            "predicted_effect": jsonable(self.predicted_effect),
            "uncertainty": jsonable(self.uncertainty),
            "model_limitations": list(self.model_limitations),
            "driver_line": jsonable(self.driver_line),
            "validation_plan": jsonable(self.validation_plan),
            "evidence": jsonable(self.evidence),
            "computation": jsonable(self.computation),
            "reviewer": jsonable(self.reviewer),
            "decision": self.decision,
            "handoff_status": self.handoff_status,
        }

    def to_markdown(self) -> str:
        data = self.as_dict()
        return "\n".join(
            [
                f"# Lab handoff: `{data['candidate_id']}`",
                "",
                f"- Study: `{data['study_id']}`",
                f"- Handoff status: **{data['handoff_status']}**",
                f"- Reviewer decision: **{data['decision']}**",
                "",
                "## Question and prediction",
                "",
                f"- Hypothesis: {data['hypothesis']}",
                f"- Falsifiable prediction: {data['falsifiable_prediction']}",
                f"- Primary metric: `{data['primary_metric']}`",
                "",
                "## Target and intervention",
                "",
                f"- Target: `{data['target'] or 'not_provided'}`",
                f"- Cell type: `{data['cell_type'] or 'not_provided'}`",
                f"- Connectome version: `{data['connectome_version'] or 'not_provided'}`",
                f"- Simulated intervention: `{_compact(data['simulated_intervention'])}`",
                f"- Proposed real intervention: `{_compact(data['proposed_real_intervention'])}`",
                f"- Driver line: `{_compact(data['driver_line'])}`",
                "",
                "## Design and interpretation",
                "",
                f"- Assay: `{data['assay']}`",
                f"- Controls: `{_compact(data['controls'])}`",
                f"- Confounds: `{_compact(data['confounds'])}`",
                f"- Predicted effect: `{_compact(data['predicted_effect'])}`",
                f"- Uncertainty: `{_compact(data['uncertainty'])}`",
                f"- Additional validation: `{_compact(data['validation_plan'])}`",
                "",
                "## Model limits",
                "",
                *[f"- {item}" for item in data["model_limitations"]],
                "",
                "## Evidence and computation",
                "",
                f"- Computation: `{_compact(data['computation'])}`",
                f"- Ranking review: `{_compact(data['computation'].get('ranking', {}))}`",
                *[f"- Source: {_compact(item)}" for item in data["evidence"]],
                "",
                "## Review",
                "",
                f"- Reviewer: `{_compact(data['reviewer'])}`",
                "- This dossier is a computational handoff and does not establish biological validation.",
                "",
            ]
        )


@dataclass(frozen=True)
class EvidenceBundle:
    study_id: str
    generated_at: str
    status: str
    ai_policy: str
    study: Mapping[str, Any]
    decision_report: Mapping[str, Any]
    run_manifests: tuple[Mapping[str, Any], ...]
    dossiers: tuple[LabHandoff, ...]
    review: Mapping[str, Any]
    limitations: tuple[str, ...]
    ranking_report: Mapping[str, Any] = field(default_factory=dict)
    ranking_review: Mapping[str, Any] = field(default_factory=dict)
    confirmation_submission: Mapping[str, Any] = field(default_factory=dict)
    confirmation_run: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "evidence_bundle_version": 2,
            "study_id": self.study_id,
            "generated_at": self.generated_at,
            "status": self.status,
            "ai_policy": self.ai_policy,
            "study": jsonable(self.study),
            "decision_report": jsonable(self.decision_report),
            "run_manifests": jsonable(self.run_manifests),
            "dossiers": [dossier.as_dict() for dossier in self.dossiers],
            "review": jsonable(self.review),
            "limitations": list(self.limitations),
            "ranking_report": jsonable(self.ranking_report),
            "ranking_review": jsonable(self.ranking_review),
            "confirmation_submission": jsonable(self.confirmation_submission),
            "confirmation_run": jsonable(self.confirmation_run),
            "scientific_scope": (
                "Evidence packaging for human review; not biological validation "
                "and not an autonomous research decision."
            ),
        }


def build_evidence_bundle(
    study: StudySpec,
    decision_report: Mapping[str, Any],
    run_manifests: Sequence[Mapping[str, Any]],
    *,
    review: Mapping[str, Any] | None = None,
    ranking_report: Mapping[str, Any] | None = None,
    confirmation_submission: Mapping[str, Any] | None = None,
    confirmation_run: Mapping[str, Any] | None = None,
) -> EvidenceBundle:
    current_review = dict(review or default_review())
    decision = str(current_review.get("decision", "pending"))
    if decision not in REVIEW_DECISIONS:
        raise ValueError(f"unsupported review decision: {decision}")
    current_ranking = dict(ranking_report or {})
    current_submission = dict(confirmation_submission or {})
    current_run = dict(confirmation_run or {})
    dossiers = tuple(
        _build_dossier(
            study,
            candidate,
            decision_report,
            run_manifests,
            current_review,
            current_ranking,
            current_submission,
            current_run,
        )
        for candidate in study.candidates
    )
    status = "APPROVED_FOR_AI_SUMMARY" if decision == "approved" else "DRAFT_UNREVIEWED"
    if decision in {"rejected", "needs_revision"}:
        status = "REVIEW_BLOCKED"
    return EvidenceBundle(
        study_id=study.study_id,
        generated_at=utc_timestamp(),
        status=status,
        ai_policy=(
            "AI may summarize only this approved bundle, with citations and explicit gaps; "
            "AI must not modify source data, QC labels, ranking, or reviewer decision."
        ),
        study=study.as_dict(),
        decision_report=dict(decision_report),
        run_manifests=tuple(dict(item) for item in run_manifests),
        dossiers=dossiers,
        review=current_review,
        ranking_report=current_ranking,
        ranking_review=_ranking_review(current_ranking, current_review),
        confirmation_submission=current_submission,
        confirmation_run=current_run,
        limitations=(
            "A computationally completed run is not biological validation.",
            "Seed variation does not represent biological replication or all model-form uncertainty.",
            "Missing readouts and failed QC are not negative biological findings.",
        ),
    )


def default_review() -> dict[str, Any]:
    return {
        "reviewer": None,
        "decision": "pending",
        "comments": "",
        "reviewed_at": None,
        "study_configuration_hash": None,
        "ranking_report_hash": None,
    }


def write_evidence_bundle(bundle: EvidenceBundle, target: str | Path) -> Path:
    """Write a readable directory or a ZIP bundle with checksums."""

    target_path = Path(target)
    if target_path.suffix.lower() == ".zip":
        with tempfile.TemporaryDirectory(prefix="fly_workbench_bundle_") as temporary:
            staging = Path(temporary) / "evidence_bundle"
            _write_bundle_directory(bundle, staging)
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(target_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(staging.rglob("*")):
                    if path.is_file():
                        archive.write(path, path.relative_to(staging).as_posix())
        return target_path
    _write_bundle_directory(bundle, target_path)
    return target_path


def _build_dossier(
    study: StudySpec,
    candidate: CandidateSpec,
    decision_report: Mapping[str, Any],
    run_manifests: Sequence[Mapping[str, Any]],
    review: Mapping[str, Any],
    ranking_report: Mapping[str, Any],
    confirmation_submission: Mapping[str, Any],
    confirmation_run: Mapping[str, Any],
) -> LabHandoff:
    metadata = dict(candidate.metadata)
    study_metadata = dict(study.metadata)
    candidate_runs = tuple(
        dict(row)
        for row in decision_report.get("results", ())
        if row.get("candidate_id") in {None, candidate.candidate_id}
    )
    candidate_manifests = tuple(
        dict(manifest)
        for manifest in run_manifests
        if manifest.get("job_id") in {row.get("job_id") for row in candidate_runs}
    )
    evidence = tuple(
        {"scope": "study", **dict(source)} for source in study.sources
    ) + tuple({"scope": "candidate", **dict(source)} for source in candidate.sources)
    model_limitations = tuple(
        str(item)
        for item in (
            study_metadata.get("model_limitations", ()),
            metadata.get("model_limitations", ()),
            decision_report.get("limitations", ()),
        )
        for item in (item if isinstance(item, (list, tuple)) else (item,))
        if item
    )
    computation = {
        "candidate_id": candidate.candidate_id,
        "run_count": len(candidate_runs),
        "runs": candidate_runs,
        "run_manifests": candidate_manifests,
        "report_status": decision_report.get("status"),
        "ranking_eligible": decision_report.get("ranking_eligible", False),
        "ranking": _candidate_ranking(ranking_report, candidate.candidate_id),
        "confirmation_submission": {
            "status": confirmation_submission.get("status", "NOT_SUBMITTED"),
            "job_ids": confirmation_submission.get("job_ids", ()),
        },
        "confirmation_run": {
            "status": confirmation_run.get("status", "NOT_RUN"),
            "completed_job_count": confirmation_run.get("completed_job_count", 0),
        },
    }
    reviewer = dict(review)
    decision = str(reviewer.get("decision", "pending"))
    return LabHandoff(
        study_id=study.study_id,
        candidate_id=candidate.candidate_id,
        generated_at=utc_timestamp(),
        hypothesis=study.hypothesis,
        falsifiable_prediction=study.falsifiable_prediction,
        target=candidate.target or metadata.get("target"),
        cell_type=metadata.get("cell_type") or study_metadata.get("cell_type"),
        connectome_version=(
            metadata.get("connectome_version")
            or study_metadata.get("connectome_version")
        ),
        simulated_intervention=candidate.intervention,
        proposed_real_intervention=metadata.get("proposed_real_intervention"),
        assay=study.assay,
        controls=tuple(dict(item) for item in study.controls),
        confounds=tuple(study.run_plan.get("confounds", ())),
        primary_metric=study.primary_metric,
        predicted_effect={
            "metric": study.primary_metric,
            "direction": candidate.expected_direction,
            "magnitude": metadata.get("predicted_effect"),
            "source": metadata.get("predicted_effect_source"),
        },
        uncertainty={
            "report": decision_report.get("uncertainty", {}),
            "minimum_effect_threshold": study.run_plan.get("minimum_effect_threshold"),
            "sensitivity_plan": study.run_plan.get("sensitivity", ()),
        },
        model_limitations=model_limitations or ("No model limitation was provided in the study spec.",),
        driver_line=metadata.get("driver_line"),
        validation_plan=tuple(
            metadata.get("validation_plan", study.run_plan.get("validation_plan", ()))
        ),
        evidence=evidence,
        computation=computation,
        reviewer=reviewer,
        decision=decision,
        handoff_status="READY_FOR_REVIEW" if decision == "pending" else "REVIEWED",
    )


def _candidate_ranking(ranking_report: Mapping[str, Any], candidate_id: str) -> dict[str, Any]:
    if not ranking_report:
        return {
            "status": "NOT_AVAILABLE",
            "candidate_id": candidate_id,
            "reason": "no persisted ranking report for this study",
        }
    ranking = ranking_report.get("ranking", {})
    if not isinstance(ranking, Mapping):
        return {
            "status": "INVALID_REPORT",
            "candidate_id": candidate_id,
            "reason": "ranking field is not an object",
        }
    for section in ("ranked_candidates", "not_ranked"):
        candidates = ranking.get(section, ())
        if isinstance(candidates, Sequence) and not isinstance(candidates, (str, bytes)):
            for candidate in candidates:
                if isinstance(candidate, Mapping) and candidate.get("candidate_id") == candidate_id:
                    return {"section": section, **dict(candidate)}
    return {
        "status": "NOT_PRESENT",
        "candidate_id": candidate_id,
        "reason": "candidate has no ranking record",
    }


def _ranking_review(
    ranking_report: Mapping[str, Any],
    review: Mapping[str, Any],
) -> dict[str, Any]:
    decision = str(review.get("decision", "pending"))
    if not ranking_report:
        return {
            "status": "NOT_AVAILABLE",
            "ranking_eligible": False,
            "requires_human_review": True,
            "can_be_used_for_handoff_priority": False,
        }
    collection = ranking_report.get("collection", {})
    ranking = ranking_report.get("ranking", {})
    current_ranking_hash = stable_hash(ranking_report)
    reviewed_ranking_hash = review.get("ranking_report_hash")
    if not isinstance(collection, Mapping) or collection.get("status") != "READY":
        status = "INCOMPLETE_COLLECTION"
        eligible = False
    elif not isinstance(ranking, Mapping) or not bool(ranking.get("ranking_eligible")):
        status = "NOT_RANKED"
        eligible = False
    elif decision == "approved":
        if reviewed_ranking_hash != current_ranking_hash:
            status = "STALE_REVIEW"
            eligible = False
        else:
            status = "APPROVED_FOR_HANDOFF"
            eligible = True
    elif decision in {"rejected", "needs_revision"}:
        status = "REVIEW_BLOCKED"
        eligible = True
    else:
        status = "PENDING_HUMAN_REVIEW"
        eligible = True
    return {
        "status": status,
        "ranking_eligible": eligible,
        "review_decision": decision,
        "reviewed_ranking_report_hash": reviewed_ranking_hash,
        "current_ranking_report_hash": current_ranking_hash,
        "requires_human_review": True,
        "can_be_used_for_handoff_priority": status == "APPROVED_FOR_HANDOFF",
    }


def _write_bundle_directory(bundle: EvidenceBundle, root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "dossiers").mkdir(exist_ok=True)
    (root / "reports").mkdir(exist_ok=True)
    (root / "manifests").mkdir(exist_ok=True)
    (root / "checksums").mkdir(exist_ok=True)
    _write_json(root / "bundle.json", bundle.as_dict())
    _write_json(root / "reports" / "decision_report.json", bundle.decision_report)
    if bundle.ranking_report:
        _write_json(root / "reports" / "ranking_report.json", bundle.ranking_report)
    if bundle.confirmation_submission:
        _write_json(
            root / "reports" / "confirmation_submission.json",
            bundle.confirmation_submission,
        )
    if bundle.confirmation_run:
        _write_json(root / "reports" / "confirmation_run.json", bundle.confirmation_run)
    (root / "handoff.md").write_text(
        "\n\n".join(dossier.to_markdown() for dossier in bundle.dossiers) + "\n",
        encoding="utf-8",
    )
    for dossier in bundle.dossiers:
        _write_json(root / "dossiers" / f"{_safe_name(dossier.candidate_id)}.json", dossier.as_dict())
    for index, manifest in enumerate(bundle.run_manifests):
        job_id = _safe_name(str(manifest.get("job_id", f"run-{index}")))
        _write_json(root / "manifests" / f"{job_id}.json", manifest)
    checksums = {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.parent.name != "checksums"
    }
    _write_json(root / "checksums" / "sha256.json", checksums)


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(jsonable(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in "._-" else "_" for char in value).strip("._") or "unnamed"


def _compact(value: Any) -> str:
    return json.dumps(jsonable(value), sort_keys=True, ensure_ascii=False)


__all__ = [
    "EvidenceBundle",
    "LabHandoff",
    "REVIEW_DECISIONS",
    "build_evidence_bundle",
    "default_review",
    "write_evidence_bundle",
]
