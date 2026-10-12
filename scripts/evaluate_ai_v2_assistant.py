"""Evaluate a frozen, human-annotated AI V2 development bundle."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from drosophila_pd.ai_v2.evaluation import evaluate_assistant_bundle


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="frozen DEVELOPMENT-only evaluation JSON")
    parser.add_argument("--output", type=Path, required=True, help="metrics JSON output path")
    parser.add_argument("--k", type=int, default=5, help="retrieval cutoff (must be preregistered)")
    args = parser.parse_args()
    try:
        bundle = json.loads(args.input.read_text(encoding="utf-8"))
        result = evaluate_assistant_bundle(bundle, k=args.k)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
        print(json.dumps({"status": "BLOCKED", "error": f"{type(error).__name__}: {error}"}, indent=2))
        return 2
    print(json.dumps({
        "status": result["evaluation_status"],
        "partition": result["partition"],
        "case_count": result["case_count"],
        "system_count": result["system_count"],
        "output": str(args.output.resolve()),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
