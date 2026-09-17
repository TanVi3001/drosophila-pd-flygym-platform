from __future__ import annotations

import pytest

from drosophila_pd.workbench import CandidateSpec, JobRecord, JobStatus, StudySpec, WorkbenchStore


def _study() -> StudySpec:
    return StudySpec(
        name="store test",
        hypothesis="h",
        falsifiable_prediction="p",
        assay="locomotion",
        primary_metric="speed",
        candidates=(CandidateSpec("control", "Control"),),
    )


def test_store_persists_studies_jobs_and_events(tmp_path) -> None:
    store = WorkbenchStore(tmp_path / "state.sqlite3")
    study = _study()
    store.create_study(study)
    job = JobRecord("job-1", study.study_id, study.backend, config={"candidate_id": "control"})
    store.create_job(job)

    loaded = store.get_job("job-1")
    loaded.status = JobStatus.FAILED
    loaded.error = "test failure"
    store.update_job(loaded, event="failed")

    assert store.get_study(study.study_id).configuration_hash == study.configuration_hash
    assert store.list_jobs(study_id=study.study_id)[0].status == JobStatus.FAILED
    assert [event["event_type"] for event in store.events("job", "job-1")] == ["submitted", "failed"]


def test_store_claim_is_atomic_for_pending_jobs(tmp_path) -> None:
    store = WorkbenchStore(tmp_path / "state.sqlite3")
    study = _study()
    store.create_study(study)
    job = JobRecord("job-claim", study.study_id, study.backend, config={"candidate_id": "control"})
    store.create_job(job)

    job.status = JobStatus.RUNNING
    store.claim_job(job)
    assert store.get_job(job.job_id).status == JobStatus.RUNNING

    duplicate = store.get_job(job.job_id)
    duplicate.status = JobStatus.RUNNING
    with pytest.raises(ValueError, match="no longer pending"):
        store.claim_job(duplicate)
