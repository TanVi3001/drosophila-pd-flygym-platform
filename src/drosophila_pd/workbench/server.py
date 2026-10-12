"""Local FastAPI server entry point."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from .adapters import default_adapters
from .api import create_app
from .intake import configured_intake_provider
from .rag import load_frozen_evidence_corpus
from .service import WorkbenchService
from .store import WorkbenchStore


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve Fly Research Workbench locally")
    parser.add_argument("--db", type=Path, default=Path(".workbench") / "workbench.sqlite3")
    parser.add_argument("--artifacts", type=Path, default=Path(".workbench") / "artifacts")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--neural-repo", type=Path, help="Optional separate neural repository root")
    parser.add_argument("--neural-python", type=Path, help="Optional interpreter for the separate neural repository")
    parser.add_argument("--intake-base-url", help="Optional OpenAI-compatible API base URL for explicit protocol intake")
    parser.add_argument("--intake-model", help="Model name for explicit protocol intake")
    parser.add_argument("--intake-api-key-env", help="Environment variable containing the optional API key")
    args = parser.parse_args()
    deployment_env = os.environ.get("WORKBENCH_ENV", "local").strip().lower()
    api_token = os.environ.get("WORKBENCH_API_TOKEN")
    if deployment_env not in {"local", "staging"}:
        parser.error("WORKBENCH_ENV must be 'local' or 'staging'; public production deployment is not supported by this profile")
    if api_token and len(api_token) < 32:
        parser.error("WORKBENCH_API_TOKEN must contain at least 32 characters")
    if deployment_env == "staging" and not api_token:
        parser.error("WORKBENCH_API_TOKEN is required when WORKBENCH_ENV=staging")
    import uvicorn

    intake_provider = configured_intake_provider(
        args.intake_base_url or os.environ.get("WORKBENCH_INTAKE_BASE_URL"),
        args.intake_model or os.environ.get("WORKBENCH_INTAKE_MODEL"),
        api_key_env=args.intake_api_key_env or os.environ.get("WORKBENCH_INTAKE_API_KEY_ENV"),
    )
    service = WorkbenchService(
        store=WorkbenchStore(args.db),
        artifact_root=args.artifacts,
        adapters=default_adapters(
            neural_repo_root=args.neural_repo,
            neural_interpreter=args.neural_python,
        ),
        intake_provider=intake_provider,
    )
    rag_manifest = os.environ.get("WORKBENCH_RAG_MANIFEST", "").strip()
    rag_corpus = None
    if rag_manifest:
        try:
            rag_corpus = load_frozen_evidence_corpus(
                rag_manifest,
                retrieval_log_path=service.artifact_root / "rag_retrieval.jsonl",
            )
        except (OSError, ValueError) as error:
            parser.error(f"could not load approved RAG corpus: {error}")
    allow_ungrounded_intake = os.environ.get("WORKBENCH_ALLOW_UNGROUNDED_INTAKE", "false").strip().lower()
    if allow_ungrounded_intake not in {"true", "false"}:
        parser.error("WORKBENCH_ALLOW_UNGROUNDED_INTAKE must be 'true' or 'false'")
    enable_synthetic_fixture = os.environ.get("WORKBENCH_ENABLE_SYNTHETIC_FIXTURE", "false").strip().lower()
    if enable_synthetic_fixture not in {"true", "false"}:
        parser.error("WORKBENCH_ENABLE_SYNTHETIC_FIXTURE must be 'true' or 'false'")
    if deployment_env == "staging" and enable_synthetic_fixture == "true":
        from .staging_fixture import install_staging_fixture

        install_staging_fixture(service)
    uvicorn.run(
        create_app(
            service,
            api_token=api_token,
            deployment_env=deployment_env,
            rag_corpus=rag_corpus,
            allow_ungrounded_intake=allow_ungrounded_intake == "true",
        ),
        host=args.host,
        port=args.port,
        proxy_headers=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main"]
