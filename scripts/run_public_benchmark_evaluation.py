#!/usr/bin/env python
"""Evaluate the frozen public benchmark with declared score systems.

This command builds transparent score mappings from published Table 3 fields.
It refuses to produce a comparative PASS report until a backend supplies a
real degree-preserving-rewire score mapping for the same case IDs.  That
refusal is intentional: a proxy or a copy of the heuristic is not a null
graph experiment.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from drosophila_pd.workbench import (  # noqa: E402
    BenchmarkProtocol,
    prepare_benchmark_comparison,
)


def _portable_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.name


def _load(path: Path) -> Mapping[str, Any]:
    if path.suffix.lower() == ".json":
        value = json.loads(path.read_text(encoding="utf-8"))
    else:
        import yaml

        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError(f"document must be a mapping: {path}")
    return value


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and abs(number) != float("inf") else None


def _published_scores(protocol: BenchmarkProtocol) -> dict[str, dict[str, float]]:
    effect_only: dict[str, float] = {}
    workbench: dict[str, float] = {}
    heuristic: dict[str, float] = {}
    original_model: dict[str, float] = {}
    for case in protocol.cases:
        metadata = case.metadata
        rates = metadata.get("model_mn9_rates_hz", {})
        sd = metadata.get("model_mn9_sd_hz", {})
        if not isinstance(rates, Mapping) or not isinstance(sd, Mapping):
            continue
        fifty = rates.get("50")
        fifty_sd = sd.get("50")
        if not isinstance(fifty, Mapping) or not isinstance(fifty_sd, Mapping):
            continue
        left = _finite(fifty.get("left"))
        right = _finite(fifty.get("right"))
        left_sd = _finite(fifty_sd.get("left"))
        right_sd = _finite(fifty_sd.get("right"))
        shortest_path = _finite(metadata.get("shortest_path"))
        if None in {left, right, left_sd, right_sd}:
            continue
        effect = (left + right) / 2.0
        uncertainty = (left_sd + right_sd) / 2.0
        effect_only[case.case_id] = effect
        original_model[case.case_id] = effect
        workbench[case.case_id] = effect / max(uncertainty, 1e-12)
        if shortest_path is not None:
            heuristic[case.case_id] = 1.0 / (1.0 + shortest_path)
    return {
        "workbench": workbench,
        "effect_only": effect_only,
        "heuristic": heuristic,
        "original_model": original_model,
    }


def evaluate(
    registry_path: Path,
    *,
    rewired_scores_path: Path | None = None,
    random_seed: int = 17092026,
    allow_partial: bool = False,
) -> dict[str, Any]:
    protocol = BenchmarkProtocol.from_dict(_load(registry_path))
    scores = _published_scores(protocol)
    if rewired_scores_path is not None:
        raw = _load(rewired_scores_path)
        rewired = raw.get("scores", raw)
        if not isinstance(rewired, Mapping):
            raise ValueError("rewired score document must be keyed by case_id or contain scores")
        scores["degree_preserving_rewire"] = {
            str(case_id): value
            for case_id, raw_value in rewired.items()
            if (value := _finite(raw_value)) is not None
        }
    required = (
        "original_model",
        "workbench",
        "random",
        "effect_only",
        "heuristic",
        "degree_preserving_rewire",
    )
    missing_systems = [name for name in required if name != "random" and name not in scores]
    if missing_systems and not allow_partial:
        return {
            "status": "BLOCKED",
            "reason": "required_score_mapping_missing",
            "protocol_hash": protocol.protocol_hash,
            "score_systems_available": sorted(scores),
            "required_systems": list(required),
            "missing_systems": missing_systems,
            "score_coverage": {name: len(values) for name, values in scores.items()},
            "scientific_scope": (
                "Published-field score preparation only; no comparative held-out "
                "claim is emitted until all declared score systems are available."
            ),
        }
    prepared_systems = tuple(name for name in required if name == "random" or name in scores)
    result = prepare_benchmark_comparison(
        protocol,
        scores,
        random_seed=random_seed,
        required_systems=prepared_systems,
    )
    return {
        "status": "READY_FOR_REVIEW" if not missing_systems else "PARTIAL_BASELINES_ONLY",
        "protocol_hash": protocol.protocol_hash,
        "source_registry": _portable_path(registry_path),
        "missing_systems": missing_systems,
        "comparison": result,
        "scientific_scope": (
            "Retrospective published-field score preparation; labels are response-presence "
            "labels and do not establish biological validity. A partial report is not "
            "a complete comparative held-out result."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--registry",
        type=Path,
        default=ROOT / "configs/workbench/shiu_public_benchmark_v2.json",
    )
    parser.add_argument("--rewired-scores", type=Path)
    parser.add_argument("--random-seed", type=int, default=17092026)
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="write an explicitly partial report when a declared score system is unavailable",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(
        args.registry.resolve(),
        rewired_scores_path=args.rewired_scores,
        random_seed=args.random_seed,
        allow_partial=args.allow_partial,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": result["status"],
        "output": _portable_path(args.output),
        "protocol_hash": result["protocol_hash"],
    }, indent=2, sort_keys=True))
    return 0 if result["status"] == "READY_FOR_REVIEW" else 2


if __name__ == "__main__":
    raise SystemExit(main())
