from __future__ import annotations

import pytest

from drosophila_pd.workbench import CandidateSpec, StudySpec


def test_study_spec_requires_falsifiable_prediction_and_unique_candidates() -> None:
    candidate = CandidateSpec("mn9", "MN9")
    study = StudySpec(
        name="sensory pilot",
        hypothesis="activation changes output",
        falsifiable_prediction="output rate changes in the prespecified direction",
        assay="sensory_mn9",
        primary_metric="output_rate",
        candidates=(candidate,),
        controls=(
            {"id": "vehicle", "role": "control"},
        ),
    )

    restored = StudySpec.from_dict(study.as_dict())
    assert restored.study_id == study.study_id
    assert restored.configuration_hash == study.configuration_hash
    assert restored.candidates[0].candidate_id == "mn9"

    with pytest.raises(ValueError, match="falsifiable_prediction"):
        StudySpec(
            name="bad",
            hypothesis="h",
            falsifiable_prediction="",
            assay="locomotion",
            primary_metric="speed",
            candidates=(candidate,),
        )

    with pytest.raises(ValueError, match="unique"):
        StudySpec(
            name="duplicate",
            hypothesis="h",
            falsifiable_prediction="p",
            assay="locomotion",
            primary_metric="speed",
            candidates=(candidate, candidate),
        )
