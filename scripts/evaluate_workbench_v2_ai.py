#!/usr/bin/env python3
"""Evaluate saved Workbench V2 retrieval/draft records; never calls a provider."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from drosophila_pd.workbench.v2_evaluation import evaluate_ai_v2_bundle


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="JSON evaluation bundle")
    parser.add_argument("--output", type=Path, help="new report path; existing files are never overwritten")
    parser.add_argument("--k", type=int, default=5, help="retrieval cutoff (default: 5)")
    args = parser.parse_args(argv)
    try:
        bundle = json.loads(args.input.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
        report = evaluate_ai_v2_bundle(bundle, k=args.k)
        encoded = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if args.output:
            if args.output.exists():
                raise FileExistsError("refusing to overwrite an existing evaluation report")
            if not args.output.parent.is_dir():
                raise FileNotFoundError("output directory must already exist")
            args.output.write_text(encoded, encoding="utf-8", newline="\n")
            print(f"Wrote evaluation report: {args.output}")
        else:
            sys.stdout.write(encoded)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        print(f"evaluation failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
