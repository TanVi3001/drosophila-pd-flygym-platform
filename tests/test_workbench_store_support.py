from __future__ import annotations

from drosophila_pd.workbench.store import WorkbenchStore
from drosophila_pd.workbench.models import CandidateSpec, StudySpec
from drosophila_pd.workbench.support import MappingRecord


def _mapping():
    return MappingRecord(
        mapping_id="test-v1",
        biological_target="target",
        backend="lif_2024",
        id_namespace="flywire_root_id",
        dataset_id="flywire-630",
        intervention_type="activation",
        target_ids=("123",),
        sources=({"citation": "paper", "locator": "figure 1"},),
    )


def test_store_persists_immutable_mapping_records(tmp_path):
    store = WorkbenchStore(tmp_path / "state.sqlite3")

    assert store.register_mapping(_mapping().as_dict()) == _mapping().as_dict()
    assert store.get_mapping("test-v1") == _mapping().as_dict()
    assert store.list_mappings() == {"test-v1": _mapping().as_dict()}


def test_store_binds_support_assessment_and_approval_to_study_hash(tmp_path):
    store = WorkbenchStore(tmp_path / "state.sqlite3")
    study = StudySpec(
        name="study",
        hypothesis="h",
        falsifiable_prediction="p",
        assay="sensory_mn9",
        primary_metric="mn9_rate",
        backend="lif_2024",
        candidates=(CandidateSpec("c", "candidate"),),
    )
    store.create_study(study)
    assessment = {
        "schema_version": "study-support-assessment-1",
        "study_id": study.study_id,
        "study_configuration_hash": study.configuration_hash,
        "status": "READY_FOR_COMPUTATIONAL_REVIEW",
        "run_allowed": True,
        "assessment_hash": "assessment-v1",
    }
    approval = {
        "study_id": study.study_id,
        "study_configuration_hash": study.configuration_hash,
        "assessment_hash": "assessment-v1",
        "status": "FROZEN_FOR_COMPUTATIONAL_RUN",
    }

    store.set_support_assessment(study.study_id, assessment)
    store.set_support_approval(study.study_id, approval)
    assert store.get_support_approval(study.study_id) == approval
    changed = {**assessment, "assessment_hash": "assessment-v2"}
    store.set_support_assessment(study.study_id, changed)
    assert store.get_support_assessment(study.study_id) == changed
    assert store.get_support_approval(study.study_id) is None
