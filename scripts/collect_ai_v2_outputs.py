"""Collect development RAG API outputs without scoring or changing approvals."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

# Package imports can initialize NumPy even though this client does no matrix work.
# Bound default client-process resources; do not override an explicit operator setting.
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

from drosophila_pd.ai_v2.collection import WorkbenchAPIClient, collect_outputs, load_collection_inputs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--rubric", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, help="exact reviewed runtime manifest; required for draft collection")
    parser.add_argument("--output-dir", type=Path, help="new directory; existing directories are never overwritten")
    parser.add_argument("--mode", choices=("retrieval-only", "rag-draft"), default="retrieval-only")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--api-token-env", default="WORKBENCH_API_TOKEN")
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--expected-manifest-sha256")
    parser.add_argument("--allow-provider-calls", action="store_true")
    parser.add_argument("--allow-remote-workbench", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="validate local inputs only; no API requests or output files")
    args = parser.parse_args()
    try:
        inputs = load_collection_inputs(args.corpus, args.rubric, mode=args.mode,
                                        allow_provider_calls=args.allow_provider_calls, manifest_path=args.manifest)
        token = os.environ.get(args.api_token_env, "")
        client = WorkbenchAPIClient(args.base_url, token=token, timeout=args.timeout,
                                    allow_remote=args.allow_remote_workbench)
        if args.dry_run:
            print(json.dumps({"status": "INPUTS_READY_NO_REQUESTS", "mode": args.mode,
                              "task_type": inputs["task_type"], "case_count": len(inputs["rubric"]["cases"]),
                              "corpus_sha256": inputs["corpus_sha256"], "rubric_sha256": inputs["rubric_sha256"],
                              "retrieval_k": inputs["retrieval_k"], "scoring_status": "NOT_RUN",
                              "heldout_status": "LOCKED_NOT_RUN"}, indent=2))
            return 0
        if args.output_dir is None:
            raise ValueError("--output-dir is required unless --dry-run is used")
        result = collect_outputs(inputs, client, args.output_dir, mode=args.mode,
                                 expected_manifest_sha256=args.expected_manifest_sha256,
                                 secrets=(token,) if token else ())
        print(json.dumps({key: result[key] for key in (
            "collection_status", "case_count", "status_counts", "provider_call_confirmed_count",
            "provider_call_unknown_count", "scoring_status", "heldout_status",
        )}, indent=2))
        return 0 if result["collection_status"] == "COMPLETE" else 1
    except (OSError, ValueError, TypeError) as error:
        # No raw endpoint/token/input text is included in CLI failures.
        print(json.dumps({"status": "BLOCKED", "error_type": type(error).__name__,
                          "message": "Collection blocked or interrupted: check development inputs, approval gates, storage and a fresh output directory."}, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
