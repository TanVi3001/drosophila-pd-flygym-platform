"""Command-line interface for the Fly Research Workbench service."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

from .adapters import default_adapters
from .benchmark import BenchmarkProtocol, freeze_benchmark_protocol
from .benchmark_baselines import prepare_benchmark_comparison
from .models import StudySpec
from .ranking import RankingPolicy
from .reproduction import verify_reproduction
from .service import WorkbenchService
from .store import WorkbenchStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fly Research Workbench v0.1")
    parser.add_argument("--db", type=Path, default=Path(".workbench") / "workbench.sqlite3")
    parser.add_argument("--artifacts", type=Path, default=Path(".workbench") / "artifacts")
    parser.add_argument("--neural-repo", type=Path, help="Optional separate neural repository root")
    parser.add_argument("--neural-python", type=Path, help="Optional interpreter for the separate neural repository")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("capabilities")
    commands.add_parser("list-studies")
    recover = commands.add_parser("recover-stale")
    recover.add_argument("--stale-after", type=float, default=3600.0)

    create = commands.add_parser("create-study")
    create.add_argument("--file", type=Path, required=True)

    get_study = commands.add_parser("get-study")
    get_study.add_argument("study_id")

    submit = commands.add_parser("submit")
    submit.add_argument("study_id")
    submit.add_argument("--config", type=Path)
    submit.add_argument("--backend")
    submit.add_argument("--job-id")
    submit.add_argument("--run", action="store_true", help="run immediately after submission")

    list_jobs = commands.add_parser("list-jobs")
    list_jobs.add_argument("--study-id")

    for name in ("job", "run", "cancel", "resume"):
        command = commands.add_parser(name)
        command.add_argument("job_id")

    report = commands.add_parser("report")
    report.add_argument("study_id")

    compare = commands.add_parser("compare")
    compare.add_argument("study_id")
    compare.add_argument("--reference-job", required=True)
    compare.add_argument("--condition-job", required=True)

    handoff = commands.add_parser("handoff")
    handoff.add_argument("study_id")

    export_bundle = commands.add_parser("export-bundle")
    export_bundle.add_argument("study_id")
    export_bundle.add_argument("--output", type=Path)

    review = commands.add_parser("review")
    review.add_argument("study_id")
    review.add_argument("--decision", choices=("pending", "approved", "rejected", "needs_revision"), required=True)
    review.add_argument("--reviewer")
    review.add_argument("--comments", default="")

    benchmark = commands.add_parser("benchmark")
    benchmark.add_argument("--protocol", type=Path, required=True)
    benchmark.add_argument("--predictions", type=Path, required=True)
    benchmark.add_argument(
        "--split",
        choices=("all", "development", "held_out"),
        default="all",
        help="benchmark split to evaluate",
    )
    benchmark.add_argument("--output", type=Path)

    benchmark_compare = commands.add_parser("benchmark-compare")
    benchmark_compare.add_argument("--protocol", type=Path, required=True)
    benchmark_compare.add_argument("--predictions-by-system", type=Path, required=True)
    benchmark_compare.add_argument(
        "--split",
        choices=("development", "held_out", "all"),
        default="held_out",
    )
    benchmark_compare.add_argument("--output", type=Path)

    benchmark_prepare = commands.add_parser("benchmark-prepare-comparison")
    benchmark_prepare.add_argument("--protocol", type=Path, required=True)
    benchmark_prepare.add_argument("--scores-by-system", type=Path, required=True)
    benchmark_prepare.add_argument("--directions", type=Path)
    benchmark_prepare.add_argument("--random-seed", type=int, default=0)
    benchmark_prepare.add_argument("--output", type=Path)

    benchmark_freeze = commands.add_parser("benchmark-freeze")
    benchmark_freeze.add_argument("--protocol", type=Path, required=True)
    benchmark_freeze.add_argument("--development", type=Path, required=True)
    benchmark_freeze.add_argument("--held-out", type=Path, required=True)
    benchmark_freeze.add_argument("--frozen-at", required=True)
    benchmark_freeze.add_argument("--label-policy", required=True)
    benchmark_freeze.add_argument("--freeze-commit")
    benchmark_freeze.add_argument("--output", type=Path)

    reproduction = commands.add_parser(
        "verify-reproduction",
        help="compare a second-operator campaign against a reference campaign",
    )
    reproduction.add_argument("--reference-manifest", type=Path, required=True)
    reproduction.add_argument("--replica-manifest", type=Path, required=True)
    reproduction.add_argument("--operator-name", required=True)
    reproduction.add_argument(
        "--operator-role",
        choices=("same_operator", "second_operator", "automated"),
        default="same_operator",
        help="role of the actor who produced the replica; second_operator is never inferred",
    )
    reproduction.add_argument("--clean-install", action="store_true")
    reproduction.add_argument("--python-version", default="3.12")
    reproduction.add_argument("--lockfile-or-export")
    reproduction.add_argument("--platform-interpreter")
    reproduction.add_argument("--neural-interpreter")
    reproduction.add_argument("--platform-repo")
    reproduction.add_argument("--neural-repo")
    reproduction.add_argument("--source-commit")
    reproduction.add_argument("--benchmark-protocol-hash")
    reproduction.add_argument("--failure-reference-manifest", type=Path)
    reproduction.add_argument("--failure-replica-manifest", type=Path)
    reproduction.add_argument("--absolute-tolerance", type=float, default=1e-9)
    reproduction.add_argument("--relative-tolerance", type=float, default=1e-9)
    reproduction.add_argument("--output", type=Path)

    sensitivity = commands.add_parser("sensitivity")
    sensitivity.add_argument("--runs", type=Path, required=True)
    sensitivity.add_argument("--output", type=Path)

    ranking = commands.add_parser("rank")
    ranking.add_argument("--observations", type=Path, required=True)
    ranking.add_argument("--policy", type=Path, required=True)
    ranking.add_argument("--output", type=Path)

    rank_study = commands.add_parser("rank-study")
    rank_study.add_argument("study_id")
    rank_study.add_argument("--policy", type=Path, required=True)
    rank_study.add_argument("--output", type=Path)

    confirmation = commands.add_parser("confirmation-plan")
    confirmation.add_argument("study_id")
    confirmation.add_argument("--top-k", type=int, default=3)
    confirmation.add_argument("--seeds", type=Path, help="JSON/YAML list of explicit fresh seeds")
    confirmation.add_argument("--sensitivity", type=Path, help="JSON/YAML sensitivity grid override")
    confirmation.add_argument("--output", type=Path)

    submit_confirmation = commands.add_parser("submit-confirmation")
    submit_confirmation.add_argument("study_id")
    submit_confirmation.add_argument("--plan", type=Path, help="Optional confirmation_plan.json override")
    submit_confirmation.add_argument(
        "--include-sensitivity",
        action="store_true",
        help="Submit every declared sensitivity case as explicit override jobs",
    )

    run_confirmation = commands.add_parser("run-confirmation")
    run_confirmation.add_argument("study_id")

    screening = commands.add_parser("screen-study")
    screening.add_argument("study_id")
    screening.add_argument("--seeds", type=Path, required=True, help="JSON/YAML list of explicit screening seeds")
    screening.add_argument("--candidates", type=Path, help="Optional JSON/YAML list of candidate IDs")
    screening.add_argument("--config", type=Path, help="Optional JSON/YAML shared backend config")
    screening.add_argument("--run", action="store_true", help="run the submitted screening jobs")

    run_screening = commands.add_parser("run-screening")
    run_screening.add_argument("study_id")

    events = commands.add_parser("events")
    events.add_argument("entity_type", choices=("study", "job"))
    events.add_argument("entity_id")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    service = WorkbenchService(
        store=WorkbenchStore(args.db),
        artifact_root=args.artifacts,
        adapters=default_adapters(
            neural_repo_root=args.neural_repo,
            neural_interpreter=args.neural_python,
        ),
    )
    try:
        payload = _dispatch(service, args)
    except (KeyError, ValueError, TypeError, OSError, RuntimeError, json.JSONDecodeError) as error:
        print(json.dumps({"error": f"{type(error).__name__}: {error}"}, indent=2, sort_keys=True))
        return 2
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0


def _dispatch(service: WorkbenchService, args: argparse.Namespace) -> Any:
    if args.command == "capabilities":
        return {"capabilities": service.capabilities()}
    if args.command == "recover-stale":
        return {
            "recovered_jobs": [
                job.as_dict()
                for job in service.recover_stale_jobs(stale_after_s=args.stale_after)
            ]
        }
    if args.command == "list-studies":
        return {"studies": [study.as_dict() for study in service.list_studies()]}
    if args.command == "create-study":
        data = _load_document(args.file)
        return service.create_study(StudySpec.from_dict(data)).as_dict()
    if args.command == "get-study":
        return service.get_study(args.study_id).as_dict()
    if args.command == "submit":
        config = _load_document(args.config) if args.config else {}
        job = service.submit_job(args.study_id, config, backend=args.backend, job_id=args.job_id)
        if args.run:
            job = service.run_job(job.job_id)
        return job.as_dict()
    if args.command == "list-jobs":
        return {"jobs": [job.as_dict() for job in service.list_jobs(study_id=args.study_id)]}
    if args.command == "job":
        return service.get_job(args.job_id).as_dict()
    if args.command == "run":
        return service.run_job(args.job_id).as_dict()
    if args.command == "cancel":
        return service.cancel_job(args.job_id).as_dict()
    if args.command == "resume":
        return service.resume_job(args.job_id).as_dict()
    if args.command == "report":
        return service.get_report(args.study_id)
    if args.command == "compare":
        return service.compare_jobs(args.study_id, args.reference_job, args.condition_job)
    if args.command == "handoff":
        return service.get_evidence_bundle(args.study_id)
    if args.command == "export-bundle":
        return {"path": str(service.export_evidence_bundle(args.study_id, args.output))}
    if args.command == "review":
        return service.record_review(
            args.study_id,
            reviewer=args.reviewer,
            decision=args.decision,
            comments=args.comments,
        )
    if args.command == "benchmark":
        protocol = BenchmarkProtocol.from_dict(_load_document(args.protocol))
        raw_predictions = _load_value(args.predictions)
        if isinstance(raw_predictions, dict) and "predictions" in raw_predictions:
            raw_predictions = raw_predictions["predictions"]
        if not isinstance(raw_predictions, dict):
            raise ValueError("predictions document must be an object keyed by case_id")
        result = service.evaluate_benchmark(
            protocol,
            raw_predictions,
            evaluation_split=args.split,
        )
        _write_optional(args.output, result)
        return result
    if args.command == "benchmark-compare":
        protocol = BenchmarkProtocol.from_dict(_load_document(args.protocol))
        raw_systems = _load_value(args.predictions_by_system)
        if isinstance(raw_systems, dict) and "predictions_by_system" in raw_systems:
            raw_systems = raw_systems["predictions_by_system"]
        if not isinstance(raw_systems, dict):
            raise ValueError("predictions-by-system document must be an object keyed by system name")
        result = service.compare_benchmark_systems(
            protocol,
            raw_systems,
            evaluation_split=args.split,
        )
        _write_optional(args.output, result)
        return result
    if args.command == "benchmark-prepare-comparison":
        protocol = BenchmarkProtocol.from_dict(_load_document(args.protocol))
        raw_scores = _load_value(args.scores_by_system)
        if isinstance(raw_scores, dict) and "scores_by_system" in raw_scores:
            raw_scores = raw_scores["scores_by_system"]
        if not isinstance(raw_scores, dict):
            raise ValueError("scores-by-system document must be an object keyed by system name")
        directions = None
        if args.directions:
            raw_directions = _load_value(args.directions)
            if isinstance(raw_directions, dict) and "directions" in raw_directions:
                raw_directions = raw_directions["directions"]
            if not isinstance(raw_directions, dict):
                raise ValueError("directions document must be an object keyed by system name")
            directions = raw_directions
        result = prepare_benchmark_comparison(
            protocol,
            raw_scores,
            directions=directions,
            random_seed=args.random_seed,
        )
        _write_optional(args.output, result)
        return result
    if args.command == "benchmark-freeze":
        protocol = BenchmarkProtocol.from_dict(_load_document(args.protocol))
        development = _load_value(args.development)
        held_out = _load_value(args.held_out)
        if isinstance(development, dict) and "case_ids" in development:
            development = development["case_ids"]
        if isinstance(held_out, dict) and "case_ids" in held_out:
            held_out = held_out["case_ids"]
        if not isinstance(development, list) or not isinstance(held_out, list):
            raise ValueError("benchmark split documents must contain a list or case_ids list")
        frozen = freeze_benchmark_protocol(
            protocol,
            development_case_ids=development,
            held_out_case_ids=held_out,
            frozen_at=args.frozen_at,
            label_policy=args.label_policy,
            freeze_commit=args.freeze_commit,
        )
        result = frozen.as_dict()
        _write_optional(args.output, result)
        return result
    if args.command == "verify-reproduction":
        result = verify_reproduction(
            args.reference_manifest,
            args.replica_manifest,
            operator_name=args.operator_name,
            operator_role=args.operator_role,
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
        _write_optional(args.output, result)
        return result
    if args.command == "sensitivity":
        raw_runs = _load_value(args.runs)
        if isinstance(raw_runs, dict) and "runs" in raw_runs:
            raw_runs = raw_runs["runs"]
        if not isinstance(raw_runs, list):
            raise ValueError("sensitivity document must contain a list of runs")
        result = service.sensitivity_report(raw_runs)
        _write_optional(args.output, result)
        return result
    if args.command == "rank":
        raw_observations = _load_value(args.observations)
        if isinstance(raw_observations, dict) and "observations" in raw_observations:
            raw_observations = raw_observations["observations"]
        if not isinstance(raw_observations, list):
            raise ValueError("observations document must contain a list")
        policy = RankingPolicy.from_dict(_load_document(args.policy))
        result = service.rank_observations(raw_observations, policy)
        _write_optional(args.output, result)
        return result
    if args.command == "rank-study":
        policy = RankingPolicy.from_dict(_load_document(args.policy))
        result = service.rank_study(args.study_id, policy)
        _write_optional(args.output, result)
        return result
    if args.command == "confirmation-plan":
        explicit_seeds = None
        if args.seeds is not None:
            raw_seeds = _load_value(args.seeds)
            if isinstance(raw_seeds, dict) and "seeds" in raw_seeds:
                raw_seeds = raw_seeds["seeds"]
            if not isinstance(raw_seeds, list):
                raise ValueError("seeds document must contain a list")
            explicit_seeds = raw_seeds
        sensitivity_grid = _load_value(args.sensitivity) if args.sensitivity is not None else None
        result = service.confirmation_plan(
            args.study_id,
            top_k=args.top_k,
            explicit_seeds=explicit_seeds,
            sensitivity_grid=sensitivity_grid,
        )
        _write_optional(args.output, result)
        return result
    if args.command == "submit-confirmation":
        plan = _load_document(args.plan) if args.plan is not None else None
        return service.submit_confirmation_plan(
            args.study_id,
            plan,
            include_sensitivity=args.include_sensitivity,
        )
    if args.command == "run-confirmation":
        return service.run_confirmation(args.study_id)
    if args.command == "screen-study":
        seeds = _load_value(args.seeds)
        if isinstance(seeds, dict) and "seeds" in seeds:
            seeds = seeds["seeds"]
        if not isinstance(seeds, list):
            raise ValueError("screening seeds document must contain a list")
        candidate_ids = None
        if args.candidates is not None:
            candidate_ids = _load_value(args.candidates)
            if isinstance(candidate_ids, dict) and "candidate_ids" in candidate_ids:
                candidate_ids = candidate_ids["candidate_ids"]
            if not isinstance(candidate_ids, list):
                raise ValueError("screening candidates document must contain a list")
        shared_config = _load_document(args.config) if args.config is not None else None
        result = service.submit_screening(
            args.study_id,
            seeds,
            candidate_ids=candidate_ids,
            base_config=shared_config,
        )
        if args.run:
            result = service.run_screening(args.study_id)
        return result
    if args.command == "run-screening":
        return service.run_screening(args.study_id)
    if args.command == "events":
        return {"events": service.events(args.entity_type, args.entity_id)}
    raise ValueError(f"unknown command: {args.command}")


def _load_document(path: Path) -> dict[str, Any]:
    value = _load_value(path)
    if not isinstance(value, dict):
        raise ValueError(f"document must contain an object: {path}")
    return value


def _load_value(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        import yaml

        value = yaml.safe_load(text)
    else:
        value = json.loads(text)
    return value


def _write_optional(path: Path | None, payload: Any) -> None:
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


__all__ = ["build_parser", "main"]
