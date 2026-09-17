from __future__ import annotations

import pytest

from drosophila_pd.workbench.service import WorkbenchService
from drosophila_pd.workbench.store import WorkbenchStore


def test_api_registers_confirmation_routes_and_local_ui_actions(tmp_path) -> None:
    pytest.importorskip("fastapi")
    from fastapi.routing import APIRoute

    from drosophila_pd.workbench.api import create_app

    service = WorkbenchService(
        store=WorkbenchStore(tmp_path / "workbench.sqlite3"),
        artifact_root=tmp_path / "artifacts",
    )
    app = create_app(service)
    paths = {route.path for route in app.routes if isinstance(route, APIRoute)}

    assert "/v1/studies/{study_id}/rank" in paths
    assert "/v1/studies/{study_id}/confirmation-plan" in paths
    assert "/v1/studies/{study_id}/confirmation-plan/submit" in paths
    assert "/v1/studies/{study_id}/confirmation-plan/run" in paths

    root = next(route for route in app.routes if route.path == "/")
    html = root.endpoint()
    assert "Submit confirmation jobs" in html
    assert "Run confirmation jobs" in html
    assert "include declared sensitivity reruns" in html
    assert "This local page uses the same service as the CLI" in html
