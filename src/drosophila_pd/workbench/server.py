"""Local FastAPI server entry point."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Mapping

from .adapters import default_adapters
from .api import create_app
from .evidence import ApprovedEvidenceCorpus, OfflineEvidenceRetriever
from .intake import configured_intake_provider
from .service import WorkbenchService
from .study_spec_draft import configured_study_spec_generator
from .store import WorkbenchStore
from .v2_runtime import (
    RuntimeLayout,
    WorkbenchV2DraftRuntime,
    validate_external_workbench_paths,
    v2_enabled_from_env,
)


def resolve_runtime_paths(
    *,
    db: Path | None,
    artifacts: Path | None,
    repository_root: Path,
    environ: Mapping[str, str] | None = None,
) -> tuple[Path, Path, RuntimeLayout | None]:
    """Resolve legacy V1 defaults or explicit repository-external V2 storage."""

    environment = os.environ if environ is None else environ
    if not v2_enabled_from_env(environment.get("FLY_WORKBENCH_V2_ENABLED")):
        return (
            db if db is not None else Path(".workbench") / "workbench.sqlite3",
            artifacts if artifacts is not None else Path(".workbench") / "artifacts",
            None,
        )
    configured_root = environment.get("FLY_WORKBENCH_V2_RUNTIME_ROOT", "").strip()
    if not configured_root:
        raise ValueError("FLY_WORKBENCH_V2_RUNTIME_ROOT is required when Workbench V2 is enabled")
    layout = RuntimeLayout.from_root(configured_root, repository_root=repository_root)
    db_path = db if db is not None else layout.v1_database
    artifact_path = artifacts if artifacts is not None else layout.v1_artifacts
    resolved_db, resolved_artifacts = validate_external_workbench_paths(
        db_path=db_path,
        artifact_path=artifact_path,
        repository_root=repository_root,
    )
    if not resolved_db.is_relative_to(layout.root) or not resolved_artifacts.is_relative_to(layout.root):
        raise ValueError("V2-enabled V1 database and artifacts must be inside FLY_WORKBENCH_V2_RUNTIME_ROOT")
    return resolved_db, resolved_artifacts, layout


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve Fly Research Workbench locally")
    parser.add_argument("--db", type=Path, help="SQLite path; when V2 is enabled it must be inside the external runtime root")
    parser.add_argument("--artifacts", type=Path, help="Artifact path; when V2 is enabled it must be inside the external runtime root")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--neural-repo", type=Path, help="Optional separate neural repository root")
    parser.add_argument("--neural-python", type=Path, help="Optional interpreter for the separate neural repository")
    parser.add_argument("--intake-base-url", help="Optional OpenAI-compatible API base URL for explicit protocol intake")
    parser.add_argument("--intake-model", help="Model name for explicit protocol intake")
    parser.add_argument("--intake-api-key-env", help="Environment variable containing the optional API key")
    parser.add_argument("--v2-intake-base-url", help="Optional V2-only OpenAI-compatible intake API base URL")
    parser.add_argument("--v2-intake-model", help="Optional V2-only intake model name")
    parser.add_argument("--v2-intake-api-key-env", help="Environment variable containing the V2 intake API key")
    parser.add_argument(
        "--v2-evidence-corpus-path",
        default=os.environ.get("FLY_WORKBENCH_V2_CORPUS_PATH"),
        help="Optional approved corpus.json under the external V2 corpus directory",
    )
    parser.add_argument(
        "--v2-evidence-corpus-sha256",
        default=os.environ.get("FLY_WORKBENCH_V2_CORPUS_SHA256"),
        help="Required SHA-256 when an approved V2 evidence corpus is configured",
    )
    parser.add_argument(
        "--v2-study-spec-base-url",
        default=os.environ.get("FLY_WORKBENCH_V2_STUDY_SPEC_BASE_URL"),
        help="Optional V2-only OpenAI-compatible StudySpec generation endpoint",
    )
    parser.add_argument(
        "--v2-study-spec-model",
        default=os.environ.get("FLY_WORKBENCH_V2_STUDY_SPEC_MODEL"),
        help="Optional V2-only StudySpec generation model name",
    )
    parser.add_argument(
        "--v2-study-spec-api-key-env",
        default=os.environ.get("FLY_WORKBENCH_V2_STUDY_SPEC_API_KEY_ENV"),
        help="Environment variable name containing the optional V2 model API key",
    )
    args = parser.parse_args()
    repository_root = Path(__file__).resolve().parents[3]
    try:
        db_path, artifact_path, runtime_layout = resolve_runtime_paths(
            db=args.db,
            artifacts=args.artifacts,
            repository_root=repository_root,
        )
    except ValueError as error:
        parser.error(str(error))
    import uvicorn

    intake_provider = configured_intake_provider(
        args.intake_base_url,
        args.intake_model,
        api_key_env=args.intake_api_key_env,
    )
    try:
        v2_provider = (
            configured_intake_provider(
                args.v2_intake_base_url,
                args.v2_intake_model,
                api_key_env=args.v2_intake_api_key_env,
            )
            if runtime_layout is not None
            else None
        )
        v2_study_spec_generator = (
            configured_study_spec_generator(
                args.v2_study_spec_base_url,
                args.v2_study_spec_model,
                api_key_env=args.v2_study_spec_api_key_env,
            )
            if runtime_layout is not None
            else None
        )
        if runtime_layout is not None and bool(args.v2_evidence_corpus_path) != bool(args.v2_evidence_corpus_sha256):
            raise ValueError("both V2 evidence corpus path and SHA-256 are required together")
        if runtime_layout is None and (
            args.v2_intake_base_url
            or args.v2_intake_model
            or args.v2_intake_api_key_env
            or args.v2_evidence_corpus_path
            or args.v2_evidence_corpus_sha256
            or args.v2_study_spec_base_url
            or args.v2_study_spec_model
            or args.v2_study_spec_api_key_env
        ):
            raise ValueError("V2 corpus and StudySpec provider options require FLY_WORKBENCH_V2_ENABLED=1")
    except ValueError as error:
        parser.error(str(error))
    if runtime_layout is not None:
        runtime_layout.prepare()
    adapters = default_adapters(
        neural_repo_root=args.neural_repo,
        neural_interpreter=args.neural_python,
    )
    evidence_retriever = None
    if runtime_layout is not None and args.v2_evidence_corpus_path:
        try:
            corpus = ApprovedEvidenceCorpus.load(
                args.v2_evidence_corpus_path,
                expected_sha256=args.v2_evidence_corpus_sha256,
                corpus_root=runtime_layout.v2_corpus,
            )
            evidence_retriever = OfflineEvidenceRetriever(
                corpus,
                audit_path=runtime_layout.v2_outputs / "retrieval_audit.jsonl",
                output_root=runtime_layout.v2_outputs,
            )
        except (OSError, ValueError) as error:
            parser.error(f"V2 evidence corpus rejected: {error}")
    supported_assays = {
        assay
        for adapter in adapters.values()
        for assay in adapter.describe().supported_assays
    }
    service = WorkbenchService(
        store=WorkbenchStore(db_path),
        artifact_root=artifact_path,
        adapters=adapters,
        intake_provider=intake_provider,
        v2_draft_runtime=(
            WorkbenchV2DraftRuntime(
                provider=v2_provider,
                output_root=runtime_layout.v2_outputs / "drafts",
                evidence_retriever=evidence_retriever,
                study_spec_generator=v2_study_spec_generator,
                supported_assays=supported_assays,
            )
            if runtime_layout is not None
            else None
        ),
    )
    uvicorn.run(create_app(service), host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main"]
