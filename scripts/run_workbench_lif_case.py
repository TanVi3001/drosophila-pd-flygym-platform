#!/usr/bin/env python
"""Run a small real LIF control/activation study through Workbench.

This is an engineering and computational-readout smoke test.  It deliberately
does not claim that the activation condition is a biological intervention or
that a ranking is wet-lab evidence.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import json
import sys
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from drosophila_pd.workbench import (  # noqa: E402
    CandidateSpec,
    RankingPolicy,
    StudySpec,
    WorkbenchService,
    WorkbenchStore,
    default_adapters,
)


def _parse_neuron_id(value: str) -> str:
    text = str(value).strip()
    if not text or not text.isdigit():
        raise argparse.ArgumentTypeError("neuron IDs must be exact non-empty decimal strings")
    return text


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--neural-repo", type=Path, default=ROOT.parent / "drosophila-pd-neural-disease")
    parser.add_argument(
        "--neural-python",
        type=Path,
        default=ROOT.parent / ".venvs" / "baseline-2024-312" / "Scripts" / "python.exe",
    )
    parser.add_argument(
        "--model-root",
        type=Path,
        default=ROOT.parent / "external" / "Drosophila_brain_model",
    )
    parser.add_argument("--annotation-file", type=Path, default=None)
    parser.add_argument("--input-id", type=_parse_neuron_id, action="append", required=True)
    parser.add_argument(
        "--readout-id",
        type=_parse_neuron_id,
        action="append",
        default=[],
        help="Optional explicit readout ID; when supplied, use the sensory_mn9 assay.",
    )
    parser.add_argument("--seeds", type=int, nargs="+", default=[0, 1])
    parser.add_argument("--trials", type=int, default=1)
    parser.add_argument("--duration-s", type=float, default=0.01)
    parser.add_argument("--stimulus-rate-hz", type=float, default=150.0)
    parser.add_argument("--output-root", type=Path, default=ROOT / ".workbench" / "lif_case")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    model_root = args.model_root.resolve()
    completeness = model_root / "2023_03_23_completeness_630_final.csv"
    connectivity = model_root / "2023_03_23_connectivity_630_final.parquet"
    output_root = args.output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    readout_ids = list(dict.fromkeys(str(value) for value in args.readout_id))
    assay = "sensory_mn9" if readout_ids else "neural"
    primary_metric = (
        f"metrics.readout_rates_hz.{readout_ids[0]}"
        if readout_ids
        else "metrics.spike_count_total"
    )
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
    study = service.create_study(
        StudySpec(
            name="Workbench LIF activation smoke",
            hypothesis="The reviewed input set changes the computational neural output.",
            falsifiable_prediction="Spike count differs from the matched no-input control under the declared protocol.",
            assay=assay,
            primary_metric=primary_metric,
            backend="lif_2024",
            candidates=(
                CandidateSpec("no_intervention", "No input control", intervention={"type": "none"}, expected_direction="unchanged"),
                CandidateSpec(
                    "activation",
                    "Reviewed input activation",
                    intervention={"type": "activation", "parameters": {"input_ids": list(args.input_id)}},
                    expected_direction="increase",
                ),
            ),
            controls=({"id": "no_intervention", "role": "negative_control"},),
            run_plan={
                "seed_repetitions": len(args.seeds),
                "backend_requirements": {
                    "model_root": str(model_root),
                    "completeness": str(completeness),
                    "connectivity": str(connectivity),
                    "annotation_file": (
                        str(args.annotation_file.resolve()) if args.annotation_file is not None else None
                    ),
                    "input_ids": [],
                    "readout_ids": [str(value) for value in readout_ids],
                    "trials": args.trials,
                    "duration_s": args.duration_s,
                    "stimulus_rate_hz": args.stimulus_rate_hz,
                    "id_namespace": "flywire_root_id",
                    "dataset_id": "flywire-630-2023-03-23",
                },
            },
        )
    )
    jobs = []
    for seed in args.seeds:
        for candidate_id in ("no_intervention", "activation"):
            jobs.append(
                service.submit_job(
                    study.study_id,
                    {"candidate_id": candidate_id, "seed": seed, "phase": "screening"},
                    job_id=f"{candidate_id}-seed-{seed}",
                )
            )
    completed = []
    for job in jobs:
        completed.append(service.run_job(job.job_id))
    policy = RankingPolicy(
        study_id=study.study_id,
        assay=assay,
        primary_metric=primary_metric,
        control_candidate_id="no_intervention",
        expected_direction="increase",
        minimum_pairs=len(args.seeds),
        bootstrap_samples=200,
        minimum_effect_threshold=1.0,
        minimum_direction_stability=0.8,
    )
    ranking = service.rank_study(study.study_id, policy)
    summary = {
        "study_id": study.study_id,
        "job_statuses": {job.job_id: job.status.value for job in completed},
        "ranking_status": ranking["status"],
        "ranking_path": ranking["report_path"],
        "scientific_scope": (
            "Computational LIF readout smoke only; no biological validation, MN9 causal claim, "
            "or wet-lab prioritization is implied."
        ),
    }
    (output_root / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
