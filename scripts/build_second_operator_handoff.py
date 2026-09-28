"""Copy verified frozen owner inputs into a portable, immutable handoff.

This is packaging only. It does not run simulations, ablations, or held-out
evaluation, and it refuses to overwrite an existing destination.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


EXPECTED = {
    "inputs/connectivity.parquet": "0f1c42d7ce44aabd80f9e126aac675ad19f69b8e40bb0951e54078720ee15e54",
    "inputs/completeness.csv": "479ed718404e7b1d898ee9a353410f481e6ed7694c30f579a7c2699f1c708a5d",
    "inputs/annotation.csv": "ce8058f56b33ac105c62ade6ac257ecec02247547335a10bf16ae0bcd533a25b",
    "inputs/mapping.csv": "c9017c2559ad96bc980c378f59f533e9e96ebc58ef85734ae33c91c9513d196b",
    "inputs/protocol.json": "8743feba5149f78d96238e9ee3bfacbc1d7dd8a33960b6a5eaf6bda77d8fdedb",
    "inputs/score_spec.json": "e522aba1bb58a0883a589255c09debbfc2cf0ad1841358242b3dd248e93aa452",
    "owner/development_ablation.json": "7be3413b85be977a0eede4a57e6d0f682a9e1837f8431f8a04a9245311865fef",
    "owner/owner_validation_record.json": "0f1abd82817516d1a0a8d92f759a543747a44ab240af59c4727706999d879c0a",
    "owner/owner_subset_verification_v2.json": "769541ad0dc4befbcfe2fbfe8845843bfe530c5de6510caeb14f994104fde3ac",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def portable_campaign(source: Path, destination: Path, source_reference: Path) -> None:
    payload = json.loads(source.read_text(encoding="utf-8"))
    for job in payload["jobs"]:
        for field in ("artifact_dir", "manifest_path"):
            original = Path(job[field]).resolve()
            try:
                relative = original.relative_to(source_reference.resolve())
            except ValueError as error:
                raise ValueError(f"campaign {field} escapes frozen reference: {original}") from error
            if not (destination.parent / relative).exists():
                raise FileNotFoundError(destination.parent / relative)
            job[field] = relative.as_posix()
    destination.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"handoff destination already exists: {output}")
    platform = workspace / "drosophila-pd-flygym"
    neural = workspace / "drosophila-pd-neural-disease"
    model = workspace / "external" / "Drosophila_brain_model"
    benchmark = model / "results" / "workbench_benchmark_20260923"
    owner = benchmark / "owner_reproduction_20260927"
    subset = owner / "reproduction_subset_v1"
    frozen = benchmark / "frozen_rewire_run02"
    sources = {
        "inputs/connectivity.parquet": model / "results/workbench_graph_nulls/flywire630_v1/graph_null_630_seed20260922_r01.parquet",
        "inputs/completeness.csv": model / "2023_03_23_completeness_630_final.csv",
        "inputs/annotation.csv": neural / "annotations/flywire630_sensory_mn9_public.csv",
        "inputs/mapping.csv": platform / "configs/workbench/shiu_v2_flywire630_mapping.csv",
        "inputs/protocol.json": platform / "configs/workbench/shiu_public_benchmark_v2.json",
        "inputs/score_spec.json": platform / "configs/workbench/shiu_workbench_score_v1.json",
        "owner/per_case_scores.csv": frozen / "per_case_scores.csv",
        "owner/freeze_manifest.json": frozen / "freeze_manifest.json",
        "owner/original_checksums.sha256": frozen / "checksums.sha256",
        "owner/development_ablation.json": owner / "development_ablation.json",
        "owner/development_score_table.csv": owner / "development_score_table.csv",
        "owner/owner_validation_record.json": owner / "owner_validation_record.json",
        "owner/owner_subset_verification_v2.json": subset / "owner_subset_verification_v2.json",
        "owner/run_owner_reproduction_subset.py": owner / "run_owner_reproduction_subset.py",
        "protocol/run_second_operator_subset.py": platform / "scripts/run_second_operator_subset.py",
        "protocol/second_operator_handoff.md": platform / "docs/second_operator_handoff.md",
    }
    checked = {}
    for relative, source in sources.items():
        if not source.is_file():
            raise FileNotFoundError(source)
        actual = sha256(source)
        expected = EXPECTED.get(relative)
        if expected and actual != expected:
            raise ValueError(f"HANDOFF_INTEGRITY_BLOCKED: {relative}: {actual} != {expected}")
        checked[relative] = {"sha256": actual, "expected_sha256": expected, "source": str(source)}
    reference = subset / "reference"
    if not reference.is_dir():
        raise FileNotFoundError(reference)
    # Validate the original campaign links before making the portable copy.
    for name in ("success_campaign.json", "failure_campaign.json"):
        payload = json.loads((reference / name).read_text(encoding="utf-8"))
        for job in payload["jobs"]:
            for field in ("artifact_dir", "manifest_path"):
                if not Path(job[field]).is_file() and field == "manifest_path":
                    raise FileNotFoundError(job[field])
                if field == "artifact_dir" and not Path(job[field]).is_dir():
                    raise FileNotFoundError(job[field])
    output.mkdir(parents=True)
    for relative, source in sources.items():
        dest = output / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        if sha256(dest) != checked[relative]["sha256"]:
            raise ValueError(f"copy hash mismatch: {dest}")
    shutil.copytree(reference / "artifacts", output / "reference" / "artifacts")
    originals = output / "reference" / "original_campaigns"
    originals.mkdir(parents=True)
    for name in ("success_campaign.json", "failure_campaign.json"):
        shutil.copy2(reference / name, originals / name)
        portable_campaign(reference / name, output / "reference" / name, reference)
    manifest = {
        "status": "FROZEN_OWNER_HANDOFF_NOT_SECOND_OPERATOR_RESULT",
        "heldout_status": "LOCKED_NOT_RUN",
        "platform_revision": subprocess.check_output(
            ["git", "-C", str(platform), "rev-parse", "HEAD"], text=True
        ).strip(),
        "portability_fix_commit": "5da654e3b39834b65afbed46754dce2ed8bc3ab9",
        "neural_revision": "e8a3cb2de2107925311053f9afcf2bfbc39fdf3c",
        "protocol_hash": "43b3704750572dade4774d514bcd986697f537b1b11de81ce918bac3310aad9f",
        "files": checked,
        "notes": "Campaign artifact links are relative; frozen nested artifacts are byte-for-byte copies. Run a separate independent replica; do not treat this package as a second-operator PASS.",
    }
    (output / "handoff_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    entries = [f"{sha256(path)}  {path.relative_to(output).as_posix()}"
               for path in sorted(output.rglob("*")) if path.is_file() and path.name != "checksums.sha256"]
    (output / "checksums.sha256").write_text("\n".join(entries) + "\n", encoding="utf-8")
    print(f"FROZEN_OWNER_HANDOFF: {output}")
    print(f"files={len(entries)}; HELDOUT_STATUS=LOCKED_NOT_RUN")


if __name__ == "__main__":
    main()
