#!/usr/bin/env python
"""Run the Workbench motor sample with a real control/perturbation pair.

This is an execution harness, not a biological validation script. It creates
new backend outputs through the same service used by the CLI and API. If the
local FlyGym runtime is unavailable, the failed job and manifest are retained
as an explicit failure state.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import uuid

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from drosophila_pd.workbench import StudySpec, WorkbenchService, WorkbenchStore  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=REPO_ROOT / ".workbench" / "motor_case",
    )
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)
    output_root = args.output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    database = output_root / "workbench.sqlite3"
    if database.exists():
        raise SystemExit(f"refusing to reuse existing study database: {database}")

    import yaml

    study_data = yaml.safe_load(
        (REPO_ROOT / "configs" / "workbench" / "motor_flat_ground.yaml").read_text(
            encoding="utf-8"
        )
    )
    study_data["study_id"] = f"motor-case-{uuid.uuid4().hex[:8]}"
    study = StudySpec.from_dict(study_data)
    service = WorkbenchService(
        store=WorkbenchStore(database),
        artifact_root=output_root / "artifacts",
    )
    service.create_study(study)
    baseline = str((REPO_ROOT / "configs" / "experiments" / "healthy_baseline.yaml").resolve())
    control = service.submit_job(
        study.study_id,
        {"candidate_id": "no_perturbation", "seed": args.seed, "baseline_config": baseline},
        job_id="motor-control",
    )
    candidate = service.submit_job(
        study.study_id,
        {
            "candidate_id": "declared_motor_perturbation",
            "seed": args.seed,
            "baseline_config": baseline,
        },
        job_id="motor-perturbation",
    )
    control = service.run_job(control.job_id)
    candidate = service.run_job(candidate.job_id)
    comparison = (
        service.compare_jobs(study.study_id, control.job_id, candidate.job_id)
        if control.status.value == "COMPLETED" and candidate.status.value == "COMPLETED"
        else {
            "status": "NOT_ELIGIBLE",
            "reason": "control or perturbation job did not complete",
        }
    )
    summary = {
        "study_id": study.study_id,
        "job_statuses": {control.job_id: control.status.value, candidate.job_id: candidate.status.value},
        "job_configs": {control.job_id: control.config, candidate.job_id: candidate.config},
        "comparison": comparison,
        "report": service.get_report(study.study_id),
        "scientific_scope": (
            "Computational motor benchmark only. The perturbation is a configured "
            "controller override; no neuron, disease, or wet-lab validation claim is made."
        ),
    }
    summary_path = output_root / "motor_case_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True, default=str))
    return 0 if all(item.status.value == "COMPLETED" for item in (control, candidate)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
