from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient

from drosophila_pd.ai_v2.contracts import AIStudySpec
from drosophila_pd.workbench.api import create_app
from drosophila_pd.workbench.models import CandidateSpec, StudySpec
from drosophila_pd.workbench.service import WorkbenchService
from drosophila_pd.workbench.store import WorkbenchStore


def _service(tmp_path: Path) -> WorkbenchService:
    service = WorkbenchService(
        store=WorkbenchStore(tmp_path / "state.sqlite3"),
        artifact_root=tmp_path / "artifacts",
    )
    from drosophila_pd.workbench.staging_fixture import install_staging_fixture

    install_staging_fixture(service)
    return service


def _draft() -> AIStudySpec:
    study = StudySpec(
        name="Synthetic staging workflow",
        hypothesis="The fixture condition changes a synthetic scalar.",
        falsifiable_prediction="Synthetic response differs from its fixture control.",
        assay="synthetic_demo",
        primary_metric="metrics.response",
        backend="staging_fixture",
        candidates=(
            CandidateSpec("control", "Synthetic control", intervention={"type": "none"}),
            CandidateSpec(
                "condition", "Synthetic condition", target="synthetic target",
                intervention={"type": "activation"},
            ),
        ),
        controls=({"id": "control", "role": "negative_control"},),
        run_plan={"backend_requirements": {"dataset_id": "synthetic_dataset", "id_namespace": "synthetic_id"}},
        metadata={"dataset_id": "synthetic_dataset", "id_namespace": "synthetic_id", "context": {}},
    )
    return AIStudySpec(study, ("SYNTHETIC_EVIDENCE_CHUNK",), provenance={"provider_id": "fixture-not-llm"})


def test_staging_token_health_readiness_and_docs_boundary(tmp_path: Path) -> None:
    app = create_app(_service(tmp_path), api_token="t" * 40, deployment_env="staging")
    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        assert client.get("/healthz").json()["authentication_required"] is True
        assert client.get("/readyz").json() == {
            "status": "ready", "checks": {"database": True, "artifact_storage": True},
        }
        assert client.get("/v1/capabilities").status_code == 401
        assert client.get("/v1/capabilities", headers={"Authorization": "Bearer wrong"}).status_code == 401
        headers = {"Authorization": "Bearer " + "t" * 40}
        assert client.get("/v1/capabilities", headers=headers).status_code == 200
        assert client.get("/docs").status_code == 401
        assert client.get("/docs", headers=headers).status_code == 404


def test_staging_api_requires_mapping_choice_then_human_approval_and_separate_run(tmp_path: Path) -> None:
    service = _service(tmp_path)
    headers = {"Authorization": "Bearer " + "s" * 40}
    app = create_app(service, api_token="s" * 40, deployment_env="staging")
    with TestClient(app) as client:
        resolve_response = client.post(
            "/v1/ai/mappings/resolve",
            headers=headers,
            json={"draft": _draft().as_dict(), "candidate_id": "condition"},
        )
        resolution = resolve_response.json()
        assert resolve_response.status_code == 200
        assert resolution["status"] == "HUMAN_SELECTION_REQUIRED"
        assert resolution["requires_human_selection"] is True
        option = resolution["options"][0]

        stale = client.post(
            "/v1/ai/studies/draft",
            headers=headers,
            json={
                "draft": _draft().as_dict(),
                "candidate_id": "condition",
                "mapping_selection": {
                    "mapping_id": option["mapping_id"],
                    "version": option["version"],
                    "record_hash": "0" * 64,
                },
            },
        )
        assert stale.status_code == 400
        assert client.get("/v1/studies", headers=headers).json()["studies"] == []

        created = client.post(
            "/v1/ai/studies/draft",
            headers=headers,
            json={
                "draft": _draft().as_dict(),
                "candidate_id": "condition",
                "mapping_selection": {
                    "mapping_id": option["mapping_id"],
                    "version": option["version"],
                    "record_hash": option["record_hash"],
                },
            },
        )
        assert created.status_code == 200, created.text
        body = created.json()
        study_id = body["study"]["study_id"]
        assert body["mapping_binding"]["target_ids"] == ["SYNTHETIC_TARGET_ID"]
        assert body["workflow_status"]["stage"] == "AWAITING_HUMAN_APPROVAL"
        assert client.post(
            f"/v1/ai/studies/{study_id}/jobs", headers=headers,
            json={"candidate_id": "condition"},
        ).status_code == 400

        approval = client.post(
            f"/v1/ai/studies/{study_id}/approval", headers=headers,
            json={"reviewer": "internal staging operator"},
        )
        assert approval.status_code == 200, approval.text
        submitted = client.post(
            f"/v1/ai/studies/{study_id}/jobs", headers=headers,
            json={"candidate_id": "condition"},
        )
        assert submitted.status_code == 200, submitted.text
        job_id = submitted.json()["job"]["job_id"]
        ran = client.post(f"/v1/ai/jobs/{job_id}/run", headers=headers)
        assert ran.status_code == 200, ran.text
        assert ran.json()["job"]["status"] == "COMPLETED"
        assert ran.json()["workflow_status"]["stage"] == "RUNS_COMPLETED"
        assert ran.json()["job"]["config"]["mapping_record_hash"] == option["record_hash"]
