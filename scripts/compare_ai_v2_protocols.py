"""Prepare/run/report three-arm DEVELOPMENT protocol experiments, never simulations."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from drosophila_pd.ai_v2.comparison import (
    digest, encoded, manual_template, markdown_report, prepare_inputs, read_json,
    run_comparison, safe_path, score_comparison, verify_run,
)
from drosophila_pd.workbench.intake import configured_intake_provider


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--rubric", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--create-manual-template", type=Path)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--report-only", type=Path, metavar="EXISTING_RUN_DIR")
    parser.add_argument("--manual", type=Path)
    parser.add_argument("--claim-reviews", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--allow-provider-calls", action="store_true")
    args = parser.parse_args()
    try:
        if args.run and (not args.allow_provider_calls or args.manifest is None):
            raise ValueError("run needs exact approved manifest and explicit provider-call flag")
        inputs = prepare_inputs(args.corpus, args.rubric, args.manifest, generation=args.run)
        if args.create_manual_template:
            path = safe_path(args.create_manual_template)
            if any(path.is_relative_to(Path(root)) for root in inputs["protected_input_roots"]):
                raise ValueError("manual worksheet must be outside frozen input directories")
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as stream:
                stream.write(encoded(manual_template(inputs)))
            print(encoded({"status": "BLANK_MANUAL_TEMPLATE_CREATED", "case_count": len(inputs["rubric"]["cases"]),
                           "heldout_status": "LOCKED_NOT_RUN"}).decode())
        elif args.dry_run:
            print(encoded({"status": "STRUCTURE_ONLY_NO_REQUESTS", "case_count": len(inputs["rubric"]["cases"]),
                           "reference_status": inputs["rubric"]["status"], "retrieval_k": 5,
                           "live_run_approved": False, "heldout_status": "LOCKED_NOT_RUN"}).decode())
        elif args.report_only:
            if args.output_dir is None:
                raise ValueError("offline report needs a fresh output directory")
            config, records, output_sha = verify_run(args.report_only, inputs)
            annotations = read_json(args.claim_reviews) if args.claim_reviews else None
            result = score_comparison(inputs, records, config, output_sha, annotations)
            target = safe_path(args.output_dir)
            protected = [Path(root) for root in inputs["protected_input_roots"]] + [safe_path(args.report_only)]
            if args.claim_reviews:
                protected.append(safe_path(args.claim_reviews).parent)
            if any(target.is_relative_to(root) for root in protected):
                raise ValueError("report must not mutate run/reference/review packages")
            target.mkdir(parents=True, exist_ok=False)
            with (target / "metrics.json").open("xb") as stream:
                stream.write(encoded(result))
            with (target / "report.md").open("x", encoding="utf-8") as stream:
                stream.write(markdown_report(result))
            report_manifest = {"schema_version": "ai-v2-offline-comparison-report-1",
                               "source_run_manifest_sha256": digest((safe_path(args.report_only) / "run_manifest.json").read_bytes()),
                               "claim_reviews_sha256": digest(safe_path(args.claim_reviews).read_bytes()) if args.claim_reviews else None,
                               "heldout_status": "LOCKED_NOT_RUN",
                               "artifact_sha256": {name: digest((target / name).read_bytes()) for name in ("metrics.json", "report.md")}}
            with (target / "report_manifest.json").open("xb") as stream:
                stream.write(encoded(report_manifest))
            print(encoded({"status": result["status"], "comparison_complete": result["comparison_complete"],
                           "provider_called": False, "heldout_status": "LOCKED_NOT_RUN"}).decode())
        else:
            if args.output_dir is None:
                raise ValueError("run needs a fresh output directory")
            provider = configured_intake_provider(os.environ.get("WORKBENCH_INTAKE_BASE_URL"),
                                                  os.environ.get("WORKBENCH_INTAKE_MODEL"),
                                                  api_key_env=os.environ.get("WORKBENCH_INTAKE_API_KEY_ENV"))
            if provider is None or not provider.api_key_env or not os.environ.get(provider.api_key_env, "").strip():
                raise ValueError("configure the selected provider and key locally")
            if args.claim_reviews:
                raise ValueError("annotations are accepted only after outputs are frozen, in report-only mode")
            result = run_comparison(inputs, args.manifest, provider, args.output_dir, manual_path=args.manual,
                                    secrets=(os.environ[provider.api_key_env],))
            print(encoded({"status": result["status"], "comparison_complete": result["comparison_complete"],
                           "heldout_status": "LOCKED_NOT_RUN"}).decode())
            return 0 if result["comparison_complete"] else 1
        return 0
    except (OSError, ValueError, TypeError, KeyError) as error:
        # Do not echo secret, prompt, raw provider failure or private input path.
        print(encoded({"status": "BLOCKED", "error_type": type(error).__name__,
                       "message": "Check reviewed protocol inputs, exact provider binding, local key, and fresh paths; no bypass.",
                       "heldout_status": "LOCKED_NOT_RUN"}).decode())
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
