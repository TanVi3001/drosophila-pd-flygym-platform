"""Local FastAPI server entry point."""

from __future__ import annotations

import argparse
from pathlib import Path

from .adapters import default_adapters
from .api import create_app
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
    args = parser.parse_args()
    import uvicorn

    service = WorkbenchService(
        store=WorkbenchStore(args.db),
        artifact_root=args.artifacts,
        adapters=default_adapters(
            neural_repo_root=args.neural_repo,
            neural_interpreter=args.neural_python,
        ),
    )
    uvicorn.run(create_app(service), host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main"]
