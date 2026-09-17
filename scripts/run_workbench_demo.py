#!/usr/bin/env python
"""Run the Day 10 Workbench smoke/demo flow with a real healthy baseline.

The two jobs are identical control replays. Their comparison exercises the
orchestration and assay contracts; it must not be read as a comparison of two
biological mechanisms.
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
    parser = argparse.ArgumentParser(description="Run the Fly Research Workbench Day 10 demo")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=REPO_ROOT / ".workbench" / "day10_demo",
        help="New directory for SQLite state and per-run artifacts.",
    )
    args = parser.parse_args(argv)
    output_root = args.output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    database = output_root / "workbench.sqlite3"
    if database.exists():
        raise SystemExit(f"refusing to reuse existing demo database: {database}")

    import yaml

    study_data = yaml.safe_load(
        (REPO_ROOT / "configs" / "workbench" / "motor_flat_ground.yaml").read_text(encoding="utf-8")
    )
    study_data["study_id"] = f"day10-demo-{uuid.uuid4().hex[:8]}"
    study = StudySpec.from_dict(study_data)
    service = WorkbenchService(
        store=WorkbenchStore(database),
        artifact_root=output_root / "artifacts",
    )
    service.create_study(study)
    job_config = {
        "candidate_id": "no_perturbation",
        "baseline_config": str((REPO_ROOT / "configs" / "experiments" / "healthy_baseline.yaml").resolve()),
    }
    first = service.run_job(service.submit_job(study.study_id, job_config, job_id="demo-control-a").job_id)
    second = service.run_job(service.submit_job(study.study_id, job_config, job_id="demo-control-b").job_id)
    comparison = service.compare_jobs(study.study_id, first.job_id, second.job_id)
    report = service.get_report(study.study_id)
    bundle = service.get_evidence_bundle(study.study_id)
    bundle_path = service.export_evidence_bundle(study.study_id, output_root / "handoff.zip")
    summary = {
        "study_id": study.study_id,
        "job_ids": [first.job_id, second.job_id],
        "job_statuses": [first.status.value, second.status.value],
        "comparison": comparison,
        "report_status": report["status"],
        "ranking_eligible": report["ranking_eligible"],
        "evidence_status": bundle["status"],
        "handoff_zip": str(bundle_path),
        "scientific_scope": (
            "Day 10 software replay smoke test using two identical healthy baseline "
            "runs; not a biological comparison or validation."
        ),
    }
    summary_path = output_root / "demo_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if all(status == "COMPLETED" for status in summary["job_statuses"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
