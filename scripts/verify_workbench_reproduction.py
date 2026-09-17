#!/usr/bin/env python
"""Verify a second-operator Workbench reproduction.

The command writes an auditable reproduction manifest and exits non-zero until
the success and explicit failure subsets, clean-install declaration, provenance
and output comparisons all pass.  It does not modify either campaign.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from drosophila_pd.workbench.reproduction import (  # noqa: E402
    DEFAULT_ABSOLUTE_TOLERANCE,
    DEFAULT_RELATIVE_TOLERANCE,
    verify_reproduction,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-manifest", type=Path, required=True)
    parser.add_argument("--replica-manifest", type=Path, required=True)
    parser.add_argument("--operator-name", required=True)
    parser.add_argument("--clean-install", action="store_true")
    parser.add_argument("--python-version", default="3.12")
    parser.add_argument("--lockfile-or-export")
    parser.add_argument("--platform-interpreter")
    parser.add_argument("--neural-interpreter")
    parser.add_argument("--platform-repo")
    parser.add_argument("--neural-repo")
    parser.add_argument("--source-commit")
    parser.add_argument("--benchmark-protocol-hash")
    parser.add_argument("--failure-reference-manifest", type=Path)
    parser.add_argument("--failure-replica-manifest", type=Path)
    parser.add_argument("--absolute-tolerance", type=float, default=DEFAULT_ABSOLUTE_TOLERANCE)
    parser.add_argument("--relative-tolerance", type=float, default=DEFAULT_RELATIVE_TOLERANCE)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    try:
        result = verify_reproduction(
            args.reference_manifest,
            args.replica_manifest,
            operator_name=args.operator_name,
            clean_install=args.clean_install,
            python_version=args.python_version,
            lockfile_or_export=args.lockfile_or_export,
            platform_interpreter=args.platform_interpreter,
            neural_interpreter=args.neural_interpreter,
            platform_repo=args.platform_repo,
            neural_repo=args.neural_repo,
            source_commit=args.source_commit,
            benchmark_protocol_hash=args.benchmark_protocol_hash,
            failure_reference_manifest=args.failure_reference_manifest,
            failure_replica_manifest=args.failure_replica_manifest,
            absolute_tolerance=args.absolute_tolerance,
            relative_tolerance=args.relative_tolerance,
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        result = {
            "reproduction_id": "workbench-independent-reproduction-v1",
            "status": "BLOCKED",
            "error": f"{type(error).__name__}: {error}",
        }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if result.get("status") == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
