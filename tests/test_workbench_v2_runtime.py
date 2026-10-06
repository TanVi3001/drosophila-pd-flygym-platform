from __future__ import annotations

import json

import pytest

from drosophila_pd.workbench.server import resolve_runtime_paths
from drosophila_pd.workbench.service import WorkbenchService
from drosophila_pd.workbench.store import WorkbenchStore
from drosophila_pd.workbench.v2_runtime import (
    RuntimeLayout,
    WorkbenchV2DraftRuntime,
    validate_external_path,
    validate_external_workbench_paths,
    v2_enabled_from_env,
)


class FixtureProvider:
    provider_id = "a01-fixture"

    def extract(self, _text: str, *, source_uri: str | None = None):
        return {
            "hypothesis": "the declared input changes the declared readout",
            "falsifiable_prediction": "the readout differs from control",
            "assay": "sensory_mn9",
            "primary_metric": "mn9_rate",
            "mapping": {"target_ids": ["must-be-filtered"]},
        }


def test_v2_is_opt_in_and_runtime_paths_are_outside_repository(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    external = tmp_path / "runtime"

    assert v2_enabled_from_env(None) is False
    assert v2_enabled_from_env("false") is False
    assert v2_enabled_from_env("1") is True
    with pytest.raises(ValueError, match="outside"):
        RuntimeLayout.from_root(repo / "runtime", repository_root=repo)

    layout = RuntimeLayout.from_root(external, repository_root=repo)
    assert not external.exists()
    layout.prepare()
    assert layout.v1_database == external / "workbench" / "state" / "workbench.sqlite3"
    assert layout.v2_config.is_dir()
    assert layout.v2_corpus.is_dir()
    assert layout.v2_prompts.is_dir()
    assert layout.v2_cache.is_dir()
    assert layout.v2_outputs.is_dir()
    assert layout.database_backups.is_dir()


def test_external_path_validator_rejects_relative_and_overlapping_paths(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    with pytest.raises(ValueError, match="absolute"):
        validate_external_path("relative\runtime", repository_root=repo, label="runtime")
    with pytest.raises(ValueError, match="outside"):
        validate_external_path(repo / "outputs", repository_root=repo, label="outputs")
    with pytest.raises(ValueError, match="must not overlap"):
        validate_external_workbench_paths(
            db_path=tmp_path / "external" / "store.sqlite3",
            artifact_path=tmp_path / "external",
            repository_root=repo,
        )


def test_server_keeps_v1_defaults_when_v2_is_disabled(tmp_path):
    db, artifacts, layout = resolve_runtime_paths(
        db=None,
        artifacts=None,
        repository_root=tmp_path / "repo",
        environ={},
    )
    assert db == (tmp_path / "repo" / ".workbench" / "workbench.sqlite3").relative_to(tmp_path / "repo")
    assert artifacts == (tmp_path / "repo" / ".workbench" / "artifacts").relative_to(tmp_path / "repo")
    assert layout is None


def test_server_v2_paths_are_explicitly_scoped_to_external_runtime(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    runtime_root = tmp_path / "external-runtime"
    db, artifacts, layout = resolve_runtime_paths(
        db=None,
        artifacts=None,
        repository_root=repo,
        environ={
            "FLY_WORKBENCH_V2_ENABLED": "true",
            "FLY_WORKBENCH_V2_RUNTIME_ROOT": str(runtime_root),
        },
    )
    assert layout is not None
    assert db == layout.v1_database
    assert artifacts == layout.v1_artifacts
    with pytest.raises(ValueError, match="inside FLY_WORKBENCH_V2_RUNTIME_ROOT"):
        resolve_runtime_paths(
            db=tmp_path / "other" / "db.sqlite3",
            artifacts=None,
            repository_root=repo,
            environ={
                "FLY_WORKBENCH_V2_ENABLED": "true",
                "FLY_WORKBENCH_V2_RUNTIME_ROOT": str(runtime_root),
            },
        )


def test_v2_draft_is_sanitized_graph_free_and_does_not_persist_protocol_text(tmp_path):
    runtime = WorkbenchV2DraftRuntime(provider=FixtureProvider(), output_root=tmp_path / "ai_v2" / "outputs")
    private_protocol = "UNIQUE PRIVATE PROTOCOL TEXT not for artifact storage"
    draft = runtime.preview(private_protocol, source_uri="https://example.org/protocol")

    assert draft["workflow_mode"] == "DRAFT_ONLY"
    assert draft["retrieval_mode"] == "NOT_CONFIGURED_IN_A01"
    assert draft["graph_used"] is False
    assert draft["simulation_started"] is False
    assert draft["approval_granted"] is False
    assert draft["study_created"] is False
    assert draft["mapping_created"] is False
    assert "mapping_generation_prohibited" in draft["guardrail_events"]
    assert "mapping" not in draft["proposed_fields"]
    saved = (tmp_path / "ai_v2" / "outputs" / f"{draft['draft_id']}.json").read_text(encoding="utf-8")
    assert private_protocol not in saved
    assert json.loads(saved)["source_sha256"] == draft["source_sha256"]


def test_v2_api_is_separate_from_v1_and_disabled_route_is_unavailable(tmp_path):
    pytest.importorskip("fastapi")
    from fastapi import HTTPException

    from drosophila_pd.workbench.api import create_app

    def endpoint_for(app, path):
        return next(route.endpoint for route in app.routes if getattr(route, "path", None) == path)

    v1_artifacts = tmp_path / "v1-artifacts"
    v1_service = WorkbenchService(
        store=WorkbenchStore(tmp_path / "v1.sqlite3"),
        artifact_root=v1_artifacts,
        intake_provider=FixtureProvider(),
    )
    v1_app = create_app(v1_service)
    with pytest.raises(HTTPException) as disabled:
        endpoint_for(v1_app, "/v2/protocol-intake/draft")({"protocol_text": "protocol"})
    assert disabled.value.status_code == 503
    v1_result = endpoint_for(v1_app, "/v1/protocol-intake/draft")({"protocol_text": "protocol"})
    assert v1_result["schema_version"] == "protocol-intake-draft-1"
    assert list((v1_artifacts / "intake_drafts").glob("*.json"))

    v2_output = tmp_path / "external-runtime" / "ai_v2" / "outputs" / "drafts"
    v2_service = WorkbenchService(
        store=WorkbenchStore(tmp_path / "isolated.sqlite3"),
        artifact_root=tmp_path / "isolated-artifacts",
        intake_provider=FixtureProvider(),
        v2_draft_runtime=WorkbenchV2DraftRuntime(provider=FixtureProvider(), output_root=v2_output),
    )
    v2_app = create_app(v2_service)
    result = endpoint_for(v2_app, "/v2/protocol-intake/draft")({"protocol_text": "protocol"})
    assert result["workflow_mode"] == "DRAFT_ONLY"
    assert list(v2_output.glob("*.json"))
    assert not list((tmp_path / "isolated-artifacts" / "intake_drafts").glob("*.json"))

    unconfigured_service = WorkbenchService(
        store=WorkbenchStore(tmp_path / "unconfigured.sqlite3"),
        artifact_root=tmp_path / "unconfigured-artifacts",
        v2_draft_runtime=WorkbenchV2DraftRuntime(provider=None, output_root=tmp_path / "unconfigured-v2"),
    )
    with pytest.raises(HTTPException) as unavailable:
        endpoint_for(create_app(unconfigured_service), "/v2/protocol-intake/draft")({"protocol_text": "protocol"})
    assert unavailable.value.status_code == 503
    assert not (tmp_path / "unconfigured-v2").exists()
