#!/usr/bin/env python
"""Run an auditable multi-seed LIF Workbench campaign.

The script materializes the declared sensory study, runs the declared control
and candidate conditions for every explicit seed, and writes a campaign
manifest. It is intentionally sequential because the target laptop budget is
one simulation job at a time. The output is computational evidence only; it
does not create biological replicates or wet-lab labels.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


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


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ImportError as error:  # pragma: no cover - environment diagnostic
        raise RuntimeError("PyYAML is required to load a Workbench study config") from error
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"study config must be a YAML mapping: {path}")
    return value


def _load_seed_manifest(path: Path) -> set[str]:
    if path.suffix.lower() in {".yaml", ".yml"}:
        payload = _load_yaml(path)
    else:
        payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"seed manifest must be an object: {path}")
    seeds = payload.get("seeds", payload.get("seed_values", []))
    return {str(seed) for seed in seeds}


def _default_seeds(phase: str) -> list[int]:
    return list(range(10)) if phase == "screening" else list(range(100, 130))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("screening", "confirmation"), required=True)
    parser.add_argument("--study-config", type=Path, default=ROOT / "configs/workbench/sensory_mn9_lif.yaml")
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--neural-repo", type=Path, default=ROOT.parent / "drosophila-pd-neural")
    parser.add_argument(
        "--neural-python",
        type=Path,
        default=ROOT.parent / ".venvs" / "baseline-2024-312" / "Scripts" / "python.exe",
    )
    parser.add_argument("--seeds", type=int, nargs="+")
    parser.add_argument("--reference-seed-manifest", type=Path)
    parser.add_argument("--candidate-id", action="append", dest="candidate_ids")
    parser.add_argument(
        "--bootstrap-samples",
        type=int,
        default=10000,
        help="bootstrap repetitions for new ranking artifacts (historical campaigns are unchanged)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="resume an interrupted campaign from its SQLite job store and manifest",
    )
    parser.add_argument(
        "--max-jobs",
        type=int,
        help="when resuming, run at most this many pending jobs and leave a PARTIAL manifest",
    )
    return parser


def run_campaign(args: argparse.Namespace) -> dict[str, Any]:
    study_config = args.study_config.resolve()
    if not study_config.is_file():
        raise FileNotFoundError(study_config)
    output_root = args.output_root.resolve()
    if not args.resume and output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"campaign output must be new and empty: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)
    manifest_path = output_root / "campaign_manifest.json"
    if args.resume and not manifest_path.is_file():
        raise FileNotFoundError(f"cannot resume without campaign manifest: {manifest_path}")
    if args.max_jobs is not None and (not args.resume or args.max_jobs < 1):
        raise ValueError("--max-jobs is only valid for resume and must be positive")
    if args.bootstrap_samples < 50:
        raise ValueError("--bootstrap-samples must be at least 50")

    seeds = list(args.seeds) if args.seeds is not None else _default_seeds(args.phase)
    if not seeds or len(seeds) != len(set(seeds)) or any(seed < 0 for seed in seeds):
        raise ValueError("campaign seeds must be unique non-negative integers")
    expected = 10 if args.phase == "screening" else 30
    if len(seeds) != expected:
        raise ValueError(f"{args.phase} campaign requires exactly {expected} seeds; got {len(seeds)}")
    reference_seeds: set[str] = set()
    if args.reference_seed_manifest is not None:
        reference_manifest_path = args.reference_seed_manifest.resolve()
        reference_seeds = _load_seed_manifest(reference_manifest_path)
    else:
        reference_manifest_path = None
    if args.phase == "confirmation" and reference_manifest_path is None:
        raise ValueError(
            "confirmation campaigns require --reference-seed-manifest so the 30 seeds can be audited as new"
        )
    if args.phase == "confirmation" and reference_seeds.intersection(str(seed) for seed in seeds):
        raise ValueError("confirmation seeds overlap the reference screening seed set")

    study_payload = _load_yaml(study_config)
    study = StudySpec.from_dict(study_payload)
    candidate_ids = list(args.candidate_ids or [candidate.candidate_id for candidate in study.candidates])
    declared_ids = {candidate.candidate_id for candidate in study.candidates}
    if set(candidate_ids) - declared_ids:
        raise ValueError(f"unknown candidate IDs: {sorted(set(candidate_ids) - declared_ids)}")
    if len(candidate_ids) != len(set(candidate_ids)):
        raise ValueError("candidate IDs must be unique")
    declared_ranking_policy = study.metadata.get("ranking_policy", {})
    if declared_ranking_policy is None:
        declared_ranking_policy = {}
    if not isinstance(declared_ranking_policy, Mapping):
        raise ValueError("study metadata ranking_policy must be a mapping")
    control_candidate_id = str(declared_ranking_policy.get("control_candidate_id", "no_intervention"))
    if control_candidate_id not in declared_ids:
        raise ValueError(
            "ranking policy control_candidate_id is not declared in StudySpec: "
            + control_candidate_id
        )
    ranking_expected_direction = declared_ranking_policy.get("expected_direction", "increase")
    ranking_minimum_effect = float(declared_ranking_policy.get("minimum_effect_threshold", 1.0))
    ranking_minimum_stability = float(declared_ranking_policy.get("minimum_direction_stability", 0.8))

    service = WorkbenchService(
        store=WorkbenchStore(output_root / "workbench.sqlite3"),
        artifact_root=output_root / "artifacts",
        adapters=default_adapters(
            repo_root=ROOT,
            interpreter=sys.executable,
            neural_repo_root=args.neural_repo.resolve(),
            neural_interpreter=args.neural_python.resolve(),
        ),
    )
    if args.resume:
        existing_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(existing_manifest, dict) or not existing_manifest.get("study_id"):
            raise ValueError("campaign manifest is missing study_id")
        created = service.get_study(str(existing_manifest["study_id"]))
        if created.configuration_hash != study.configuration_hash:
            raise ValueError("study config hash does not match the interrupted campaign")
    else:
        created = service.create_study(study)
    manifest: dict[str, Any] = {
        "schema_version": "workbench-seed-campaign-2",
        "status": "RUNNING",
        "phase": args.phase,
        "started_at_utc": datetime.now(UTC).isoformat(),
        "study_id": created.study_id,
        "study_configuration_hash": created.configuration_hash,
        "study_config": str(study_config),
        "study_config_sha256": _sha256(study_config),
        "candidate_ids": candidate_ids,
        "seeds": seeds,
        "unique_seed_count": len(set(seeds)),
        "new_seed_set": args.phase == "confirmation" and not reference_seeds.intersection(str(seed) for seed in seeds),
        "reference_seeds": sorted(reference_seeds),
        "reference_seed_manifest": None if reference_manifest_path is None else str(reference_manifest_path),
        "reference_seed_manifest_sha256": (
            None if reference_manifest_path is None else _sha256(reference_manifest_path)
        ),
        "jobs": [],
        "ranking": None,
        "scientific_scope": (
            "Paired computational LIF screening/confirmation only. Seeds are computational repeats, "
            "not biological replicates; no wet-lab or disease claim is made."
        ),
        "analysis_policy": {
            "bootstrap_samples": int(args.bootstrap_samples),
            "seed_unit": "computational_seed_not_biological_replicate",
            "control_candidate_id": control_candidate_id,
            "expected_direction": ranking_expected_direction,
            "minimum_effect_threshold": ranking_minimum_effect,
            "minimum_direction_stability": ranking_minimum_stability,
            "declared_source": "study.metadata.ranking_policy",
        },
    }
    if args.resume:
        previous = json.loads(manifest_path.read_text(encoding="utf-8"))
        if isinstance(previous, dict):
            manifest.update(previous)
        manifest.update(
            {
                "status": "RUNNING",
                "resumed_at_utc": datetime.now(UTC).isoformat(),
                "study_id": created.study_id,
                "study_configuration_hash": created.configuration_hash,
            }
        )
    _write_json(manifest_path, manifest)

    try:
        if not args.resume and args.phase == "screening":
            submitted = service.submit_screening(
                created.study_id,
                seeds,
                candidate_ids=candidate_ids,
                base_config={"phase": args.phase},
            )
            jobs = [service.get_job(job_id) for job_id in submitted["job_ids"]]
        elif not args.resume:
            jobs = []
            for candidate_id in candidate_ids:
                for seed in seeds:
                    jobs.append(
                        service.submit_job(
                            created.study_id,
                            {"candidate_id": candidate_id, "seed": seed, "phase": args.phase},
                            job_id=f"{args.phase}-{candidate_id}-seed-{seed}",
                        )
                    )
        if args.resume:
            service.recover_stale_jobs(stale_after_s=0)
            jobs = service.list_jobs(study_id=created.study_id)
        processed_jobs = 0
        for job in jobs:
            current = service.get_job(job.job_id)
            if current.status.value == "COMPLETED":
                continue
            if args.resume and args.max_jobs is not None and processed_jobs >= args.max_jobs:
                break
            if current.status.value in {"FAILED", "CANCELLED"}:
                current = service.resume_job(current.job_id)
            if current.status.value in {"PENDING"}:
                service.run_job(current.job_id)
            processed_jobs += 1
            manifest["jobs"] = [item.as_dict() for item in service.list_jobs(study_id=created.study_id)]
            _write_json(manifest_path, manifest)
        manifest["jobs"] = [item.as_dict() for item in service.list_jobs(study_id=created.study_id)]
        statuses = {str(item["status"]) for item in manifest["jobs"]}
        if statuses != {"COMPLETED"}:
            if args.resume and args.max_jobs is not None:
                manifest["status"] = "PARTIAL"
                manifest["finished_at_utc"] = datetime.now(UTC).isoformat()
                _write_json(manifest_path, manifest)
                return manifest
            raise RuntimeError(f"campaign has non-completed jobs: {sorted(statuses)}")
        policy = RankingPolicy(
            study_id=created.study_id,
            assay=created.assay,
            primary_metric=created.primary_metric,
            control_candidate_id=control_candidate_id,
            expected_direction=ranking_expected_direction,
            minimum_pairs=len(seeds),
            bootstrap_samples=args.bootstrap_samples,
            minimum_effect_threshold=ranking_minimum_effect,
            minimum_direction_stability=ranking_minimum_stability,
        )
        ranking = service.rank_study(created.study_id, policy)
        manifest["ranking"] = ranking
        ranking_summary = ranking.get("ranking", {})
        manifest["ranking_status"] = str(ranking_summary.get("status", "UNKNOWN"))
        manifest["ranking_eligible"] = bool(ranking_summary.get("ranking_eligible", False))
        manifest["ranking_interpretation"] = (
            "Computational ranking is available within the declared study/assay/policy."
            if manifest["ranking_eligible"]
            else "All jobs completed, but no candidate met the declared ranking policy; no priority is asserted."
        )
        manifest["status"] = "PASS"
        manifest["finished_at_utc"] = datetime.now(UTC).isoformat()
        _write_json(manifest_path, manifest)
        return manifest
    except Exception as error:  # noqa: BLE001 - preserve a failed campaign artifact
        manifest["status"] = "FAILED"
        manifest["failure"] = {"error_type": type(error).__name__, "error": str(error)}
        manifest["finished_at_utc"] = datetime.now(UTC).isoformat()
        _write_json(manifest_path, manifest)
        raise


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run_campaign(args)
    except (FileExistsError, FileNotFoundError, OSError, RuntimeError, ValueError) as error:
        print(f"campaign failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
