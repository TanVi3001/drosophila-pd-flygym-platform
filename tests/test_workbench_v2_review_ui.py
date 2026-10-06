from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path

import pytest


_SPEC = importlib.util.spec_from_file_location(
    "a07_demo_for_review_ui",
    Path(__file__).resolve().parents[1] / "scripts/run_workbench_v2_review_demo.py",
)
demo = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(demo)


class _Response:
    def __init__(self, status_code: int, headers: list[tuple[bytes, bytes]], body: bytes):
        self.status_code = status_code
        self.headers = dict(headers)
        self.content = body
        self.text = body.decode("utf-8")

    def json(self):
        return json.loads(self.text)


class _ASGITestClient:
    """Small dependency-free HTTP harness for the app's ASGI contract."""

    def __init__(self, app):
        self.app = app

    def get(self, path: str):
        return self.request("GET", path)

    def post(self, path: str, *, json: dict | None = None):
        return self.request("POST", path, payload=json)

    def request(self, method: str, path: str, *, payload: dict | None = None):
        body = b"" if payload is None else json_module_dumps(payload)
        sent: list[dict] = []
        receive_count = 0

        async def receive():
            nonlocal receive_count
            receive_count += 1
            if receive_count == 1:
                return {"type": "http.request", "body": body, "more_body": False}
            return {"type": "http.disconnect"}

        async def send(message):
            sent.append(message)

        scope = {
            "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
            "method": method, "scheme": "http", "path": path,
            "raw_path": path.encode("ascii"), "query_string": b"", "root_path": "",
            "headers": [(b"host", b"testserver"), (b"content-type", b"application/json")],
            "client": ("127.0.0.1", 12345), "server": ("127.0.0.1", 80), "state": {},
        }
        asyncio.run(self.app(scope, receive, send))
        start = next(message for message in sent if message["type"] == "http.response.start")
        response_body = b"".join(
            message.get("body", b"") for message in sent if message["type"] == "http.response.body"
        )
        return _Response(start["status"], start.get("headers", []), response_body)


def json_module_dumps(value: dict) -> bytes:
    return json.dumps(value).encode("utf-8")


def _client(tmp_path):
    pytest.importorskip("fastapi")
    from drosophila_pd.workbench.api import create_app

    service, workflow = demo.make_fixture_service(tmp_path / "external")
    return service, _ASGITestClient(create_app(service, workflow_automation=workflow))


def test_review_ui_exposes_only_explicit_human_gated_v2_actions(tmp_path):
    _service, client = _client(tmp_path)
    response = client.get("/")
    assert response.status_code == 200
    html = response.text
    for expected in (
        "AI V2 — Evidence draft → human review → gated Workbench run",
        "Retrieve evidence and create draft",
        "Load saved draft + checksum",
        "Promote reviewed design (does not run)",
        "Assess/refresh support",
        "Record human run approval",
        "Submit declared jobs",
        "Run submitted jobs",
        "Get provenance/QC report",
        "does not authenticate reviewer identity",
        "value=\"development\"",
        "value=\"synthetic_fixture\"",
    ):
        assert expected in html
    assert 'option value="heldout"' not in html
    assert "async function v2Run()" in html


def test_api_draft_review_promotion_approval_and_run_are_separate_gates(tmp_path):
    service, client = _client(tmp_path)

    draft_response = client.post(
        "/v2/study-spec/draft",
        json={"question": "How is the synthetic MN9 fixture readout represented?"},
    )
    assert draft_response.status_code == 200, draft_response.text
    draft = draft_response.json()
    assert draft["draft_id"].startswith("v2-study-draft-")
    assert service.list_studies() == []

    snapshot_response = client.get(f"/v2/study-spec/drafts/{draft['draft_id']}")
    assert snapshot_response.status_code == 200, snapshot_response.text
    snapshot = snapshot_response.json()
    assert snapshot["draft"]["draft_id"] == draft["draft_id"]
    assert len(snapshot["draft_sha256"]) == 64

    promotion_response = client.post(
        f"/v2/study-spec/drafts/{draft['draft_id']}/promote",
        json={
            "expected_draft_sha256": snapshot["draft_sha256"],
            "reviewer": "synthetic-api-reviewer",
            "review_decision": "APPROVED",
            "evaluation_split": "synthetic_fixture",
            "study": demo.reviewed_fixture_study(study_id="a09-api-e2e-study"),
        },
    )
    assert promotion_response.status_code == 200, promotion_response.text
    promotion = promotion_response.json()
    study_id = promotion["study"]["study_id"]
    assert promotion["status"] == "PROMOTED_REQUIRES_RUN_APPROVAL"
    assert promotion["job_created"] is False
    assert promotion["simulation_started"] is False
    assert service.list_jobs(study_id=study_id) == []
    pre_approval_status = client.get(f"/v2/workflows/{study_id}")
    assert pre_approval_status.status_code == 200
    assert pre_approval_status.json()["workflow_state"] == "HUMAN_APPROVAL_REQUIRED"

    blocked_submit = client.post(
        f"/v2/workflows/{study_id}/screening/submit", json={"seeds": [101]},
    )
    assert blocked_submit.status_code == 400
    assert service.list_jobs(study_id=study_id) == []

    assessment = client.post(f"/v2/workflows/{study_id}/assess", json={})
    assert assessment.status_code == 200, assessment.text
    assert assessment.json()["run_allowed"] is True
    status = client.get(f"/v2/workflows/{study_id}")
    assert status.status_code == 200
    assert status.json()["workflow_state"] == "HUMAN_APPROVAL_REQUIRED"

    approval = client.post(
        f"/v2/workflows/{study_id}/approve", json={"reviewer": "synthetic-run-reviewer"},
    )
    assert approval.status_code == 200, approval.text
    submission = client.post(
        f"/v2/workflows/{study_id}/screening/submit", json={"seeds": [101]},
    )
    assert submission.status_code == 200, submission.text
    assert submission.json()["submitted_job_count"] == 2

    run = client.post(
        f"/v2/workflows/{study_id}/screening/run", json={"timeout_s": 30},
    )
    assert run.status_code == 200, run.text
    assert run.json()["status"] == "COMPLETED"
    report_response = client.get(f"/v2/workflows/{study_id}/report")
    assert report_response.status_code == 200, report_response.text
    report = report_response.json()
    assert report["audit_chain"]["status"] == "VALID"
    assert report["ai_draft_lineage"]["draft_id"] == draft["draft_id"]
    assert report["ai_draft_lineage"]["run_approval_granted"] is False
    assert report["human_approval_sha256"]
    assert any("does not establish biological" in claim for claim in report["claim_boundary"])


def test_api_rejects_heldout_scope_before_creating_a_study(tmp_path):
    service, client = _client(tmp_path)
    draft = client.post(
        "/v2/study-spec/draft", json={"question": "Synthetic test question"},
    ).json()
    snapshot = client.get(f"/v2/study-spec/drafts/{draft['draft_id']}").json()
    response = client.post(
        f"/v2/study-spec/drafts/{draft['draft_id']}/promote",
        json={
            "expected_draft_sha256": snapshot["draft_sha256"],
            "reviewer": "synthetic-api-reviewer",
            "review_decision": "APPROVED",
            "evaluation_split": "heldout",
            "study": demo.reviewed_fixture_study(study_id="must-not-exist"),
        },
    )
    assert response.status_code == 400
    assert "held-out is locked" in response.text
    assert service.list_studies() == []
