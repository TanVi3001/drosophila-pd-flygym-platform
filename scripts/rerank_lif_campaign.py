#!/usr/bin/env python
"""Recompute a campaign ranking under its declared contrast policy.

This utility does not rerun simulations.  It is intended for an auditable
analysis correction when a completed campaign used an older runner policy but
the study configuration already declares a different primary contrast.  The
output is explicitly marked as a derived/post-hoc ranking and keeps the
original campaign manifest hash and status visible.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from drosophila_pd.workbench import (  # noqa: E402
    RankingPolicy,
    StudySpec,
    WorkbenchService,
    WorkbenchStore,
    default_adapters,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_yaml(path: Path) -> Mapping[str, Any]:
    import yaml

    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError(f"study config must be a mapping: {path}")
    return value


def _policy_from_config(study: StudySpec, payload: Mapping[str, Any], bootstrap_samples: int) -> RankingPolicy:
    metadata = payload.get("metadata", {})
    if not isinstance(metadata, Mapping):
        raise ValueError("study metadata must be a mapping")
    declared = metadata.get("ranking_policy", {})
    if not isinstance(declared, Mapping):
        raise ValueError("study metadata ranking_policy must be a mapping")
    control = str(declared.get("control_candidate_id", "no_intervention"))
    declared_ids = {candidate.candidate_id for candidate in study.candidates}
    if control not in declared_ids:
        raise ValueError(f"ranking control is not declared in the stored study: {control}")
    return RankingPolicy(
        study_id=study.study_id,
        assay=study.assay,
        primary_metric=study.primary_metric,
        control_candidate_id=control,
        expected_direction=declared.get("expected_direction", "increase"),
        minimum_pairs=int(declared.get("minimum_pairs", 10)),
        bootstrap_samples=int(bootstrap_samples),
        ci_level=float(declared.get("ci_level", 0.95)),
        minimum_effect_threshold=float(declared.get("minimum_effect_threshold", 1.0)),
        minimum_direction_stability=float(declared.get("minimum_direction_stability", 0.8)),
        bootstrap_seed=int(declared.get("bootstrap_seed", 0)),
    )


def rerank(
    campaign_root: Path,
    study_config: Path,
    *,
    neural_repo: Path,
    neural_python: Path,
    output: Path,
    bootstrap_samples: int,
) -> dict[str, Any]:
    campaign_root = campaign_root.resolve()
    manifest_path = campaign_root / "campaign_manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, Mapping):
        raise ValueError("campaign manifest must be an object")
    if str(manifest.get("status", "")).upper() != "PASS":
        raise ValueError("only a completed PASS campaign may be reranked")
    jobs = manifest.get("jobs", [])
    if not isinstance(jobs, list) or any(str(job.get("status", "")) != "COMPLETED" for job in jobs):
        raise ValueError("campaign must contain only COMPLETED jobs")
    study_id = str(manifest.get("study_id", "")).strip()
    if not study_id:
        raise ValueError("campaign manifest is missing study_id")
    payload = _load_yaml(study_config.resolve())
    stored_study = StudySpec.from_dict(payload)
    store = WorkbenchStore(campaign_root / "workbench.sqlite3")
    service = WorkbenchService(
        store=store,
        artifact_root=campaign_root / "artifacts",
        adapters=default_adapters(
            repo_root=ROOT,
            interpreter=sys.executable,
            neural_repo_root=neural_repo.resolve(),
            neural_interpreter=neural_python.resolve(),
        ),
    )
    persisted = service.get_study(study_id)
    policy = _policy_from_config(persisted, payload, bootstrap_samples)
    collection = service.collect_ranking_observations(study_id, policy)
    ranking = service.rank_observations(collection["observations"], policy)
    result = {
        "report_version": 1,
        "status": "READY" if collection["status"] == "READY" else "INCOMPLETE",
        "study_id": study_id,
        "policy": policy.as_dict(),
        "ranking": ranking,
        "collection": collection,
        "derived_from": {
            "campaign_manifest": str(manifest_path),
            "campaign_manifest_sha256": _sha256(manifest_path),
            "campaign_status": manifest.get("status"),
            "campaign_schema_version": manifest.get("schema_version"),
            "source_campaign_ranking_policy": manifest.get("analysis_policy"),
            "study_config": str(study_config.resolve()),
            "study_config_sha256": _sha256(study_config.resolve()),
            "stored_study_configuration_hash": persisted.configuration_hash,
            "config_payload_configuration_hash": stored_study.configuration_hash,
        },
        "analysis_status": "DERIVED_POLICY_CORRECTION",
        "interpretation": (
            "This ranking reuses completed simulation artifacts and applies the declared "
            "study contrast; it is not a new simulation campaign. Seeds remain computational repeats."
        ),
        "scientific_scope": (
            "Matched computational temporal-protocol sensitivity only; no wet-lab, disease, "
            "driver-line, or firing-to-behavior claim is made."
        ),
    }
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-root", type=Path, required=True)
    parser.add_argument("--study-config", type=Path, required=True)
    parser.add_argument("--neural-repo", type=Path, default=ROOT.parent / "drosophila-pd-neural-disease")
    parser.add_argument(
        "--neural-python",
        type=Path,
        default=ROOT.parent / ".venvs" / "baseline-2024-312" / "Scripts" / "python.exe",
    )
    parser.add_argument("--bootstrap-samples", type=int, default=10000)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.bootstrap_samples < 50:
        raise SystemExit("--bootstrap-samples must be at least 50")
    try:
        result = rerank(
            args.campaign_root,
            args.study_config,
            neural_repo=args.neural_repo,
            neural_python=args.neural_python,
            output=args.output,
            bootstrap_samples=args.bootstrap_samples,
        )
    except (FileNotFoundError, OSError, ValueError, RuntimeError) as error:
        print(f"rerank failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 2
    print(json.dumps({"status": result["status"], "output": str(args.output.resolve())}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
