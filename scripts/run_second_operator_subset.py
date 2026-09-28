"""Run the frozen success/failure technical subset in an independent checkout.

This script writes a *replica*, not an independent-reproduction verdict. The
human operator must separately establish independence and run the verifier.
No held-out benchmark data are read here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from drosophila_pd.workbench import (
    CandidateSpec, StudySpec, WorkbenchService, WorkbenchStore, default_adapters,
)


SEED = 20260922
READOUT = "720575940660219265"
STUDY_ID = "owner-reproduction-lif-contract-v1"
NEURAL_COMMIT = "e8a3cb2de2107925311053f9afcf2bfbc39fdf3c"
SCIENTIFIC_SCOPE = (
    "Owner-assisted technical reproduction subset for the Workbench LIF "
    "execution and failure/QC contracts. This is not biological validation, "
    "not independent reproduction, and does not use held-out benchmark labels."
)
INPUT_HASHES = {
    "connectivity.parquet": "0f1c42d7ce44aabd80f9e126aac675ad19f69b8e40bb0951e54078720ee15e54",
    "completeness.csv": "479ed718404e7b1d898ee9a353410f481e6ed7694c30f579a7c2699f1c708a5d",
    "annotation.csv": "ce8058f56b33ac105c62ade6ac257ecec02247547335a10bf16ae0bcd533a25b",
}


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def _study() -> StudySpec:
    # Deliberately identical to the frozen owner subset StudySpec.
    return StudySpec(
        study_id=STUDY_ID,
        created_at="2026-09-27T00:00:00+00:00",
        name="Owner reproduction LIF contract",
        hypothesis="A deterministic no-input LIF execution can be reproduced under the same declared computational configuration.",
        falsifiable_prediction="Repeated runs with identical seed, inputs and model files produce equivalent declared MN9 computational metrics.",
        assay="sensory_mn9",
        primary_metric="metrics.readout_rates_hz.720575940660219265",
        candidates=(CandidateSpec(
            candidate_id="no_intervention",
            label="No-input computational control",
            intervention={"type": "none"},
            expected_direction="unchanged",
        ),),
        controls=({"id": "no_intervention", "role": "technical_control"},),
        backend="lif_2024",
        metadata={"purpose": "owner_reproduction_infrastructure_validation", "held_out_data_used": False},
    )


def _write(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--handoff", type=Path, required=True)
    parser.add_argument("--platform-repo", type=Path, required=True)
    parser.add_argument("--neural-repo", type=Path, required=True)
    parser.add_argument("--neural-python", type=Path, required=True)
    parser.add_argument("--expected-platform-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    handoff = args.handoff.resolve()
    platform = args.platform_repo.resolve()
    neural = args.neural_repo.resolve()
    neural_python = args.neural_python.resolve()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"replica output already exists: {output}")
    if handoff == output or handoff in output.parents:
        raise ValueError("replica output must be separate from the frozen handoff")
    if sys.version_info[:3] != (3, 12, 10):
        raise RuntimeError(f"expected Python 3.12.10, got {sys.version}")
    if not neural_python.is_file():
        raise FileNotFoundError(neural_python)
    for label, repo in (("platform", platform), ("neural", neural)):
        if _git(repo, "status", "--porcelain"):
            raise RuntimeError(f"{label} worktree must be clean")
    neural_revision = _git(neural, "rev-parse", "HEAD")
    if neural_revision != NEURAL_COMMIT:
        raise RuntimeError(f"neural revision mismatch: {neural_revision}")
    platform_revision = _git(platform, "rev-parse", "HEAD")
    if platform_revision != args.expected_platform_commit:
        raise RuntimeError(f"platform revision mismatch: {platform_revision}")
    subprocess.run([sys.executable, "-m", "pip", "check"], check=True)
    subprocess.run([str(neural_python), "-m", "pip", "check"], check=True)
    neural_version = subprocess.check_output(
        [str(neural_python), "-c", "import sys; print('.'.join(map(str, sys.version_info[:3])))"],
        text=True,
    ).strip()
    if neural_version != "3.12.10":
        raise RuntimeError(f"expected neural Python 3.12.10, got {neural_version}")
    subprocess.run(
        [str(neural_python), "-c", "import brian2, pandas, pyarrow"], check=True
    )
    inputs = handoff / "inputs"
    for name, expected in INPUT_HASHES.items():
        actual = _hash(inputs / name)
        if actual != expected:
            raise ValueError(f"HANDOFF_INTEGRITY_BLOCKED: {name}: {actual} != {expected}")
    output.mkdir(parents=True)
    common = output / "common"
    common.mkdir()
    annotation = common / "annotation.csv"
    shutil.copy2(inputs / "annotation.csv", annotation)
    if _hash(annotation) != INPUT_HASHES["annotation.csv"]:
        raise ValueError("annotation copy hash mismatch")
    store = WorkbenchStore(output / "workbench.sqlite3")
    service = WorkbenchService(
        store=store,
        artifact_root=output / "artifacts",
        adapters=default_adapters(
            repo_root=platform,
            interpreter=Path(sys.executable),
            neural_repo_root=neural,
            neural_interpreter=neural_python,
        ),
    )
    study = _study()
    service.create_study(study)
    config = {
        "candidate_id": "no_intervention",
        "seed": SEED,
        "model_root": str(inputs),
        "completeness": str(inputs / "completeness.csv"),
        "connectivity": str(inputs / "connectivity.parquet"),
        "annotation_file": str(annotation),
        "readout_ids": [READOUT],
        "trials": 1,
        "duration_s": 0.05,
        "stimulus_rate_hz": 50.0,
        "id_namespace": "flywire_root_id",
        "dataset_id": "flywire-630-2023-03-23",
        "phase": "owner_reproduction_subset",
    }
    for label, job_id, expected_status in (
        ("success", "repro-success-seed-20260922", "COMPLETED"),
        ("failure", "repro-failure-seed-20260922", "FAILED"),
    ):
        job = service.submit_job(study.study_id, config, job_id=job_id)
        held = annotation.with_suffix(".temporarily_held")
        if label == "failure":
            if held.exists():
                raise FileExistsError(held)
            annotation.rename(held)
        try:
            job = service.run_job(job.job_id)
        finally:
            if label == "failure" and held.exists():
                held.rename(annotation)
        if job.status.value != expected_status:
            raise RuntimeError(f"{label} job: {job.status.value} / {job.error}")
        campaign = {
            "campaign_version": 1,
            "phase": "reproduction_success" if label == "success" else "reproduction_failure_qc",
            "status": "PASS" if label == "success" else "PARTIAL",
            "study_id": study.study_id,
            "study_configuration_hash": study.configuration_hash,
            "study_config_sha256": study.configuration_hash,
            "scientific_scope": SCIENTIFIC_SCOPE,
            "platform_repo": str(platform),
            "neural_repo": str(neural),
            "jobs": [job.as_dict()],
        }
        _write(output / f"{label}_campaign.json", campaign)
    _write(output / "environment_record.json", {
        "operator_role": "UNVERIFIED_BY_SCRIPT",
        "platform_revision": platform_revision,
        "neural_revision": neural_revision,
        "platform_python": sys.executable,
        "neural_python": str(neural_python),
        "platform_python_version": ".".join(map(str, sys.version_info[:3])),
        "neural_python_version": neural_version,
        "pip_check": "PASS",
        "neural_import_smoke": "PASS",
        "input_hashes": INPUT_HASHES,
        "heldout_status": "LOCKED_NOT_RUN",
    })
    print(f"technical subset campaigns written to {output}; independent status requires human verification")


if __name__ == "__main__":
    main()
