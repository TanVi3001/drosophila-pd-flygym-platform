"""Run the paper-facing Workbench release gates.

The command is intentionally conservative: missing independent reproduction,
biological review, seed manifests, tags, or clean worktrees are reported as
BLOCKED. It never turns a missing artifact into a pass and never changes the
repositories.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def _load_yaml(path: Path) -> Mapping[str, Any]:
    if path.suffix.lower() == ".json":
        value = json.loads(path.read_text(encoding="utf-8"))
    else:
        try:
            import yaml
        except ImportError as error:  # pragma: no cover - environment diagnostic
            raise RuntimeError("PyYAML is required for the release gate") from error
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError(f"expected a YAML mapping: {path}")
    return value


def _check(name: str, status: str, detail: str, **extra: Any) -> dict[str, Any]:
    result = {"name": name, "status": status, "detail": detail}
    result.update(extra)
    return result


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _clean_worktree(name: str, repo: Path) -> dict[str, Any]:
    if not (repo / ".git").exists():
        return _check(name, "BLOCKED", f"not a git repository: {repo}")
    try:
        status = _git(repo, "status", "--porcelain", "--untracked-files=all")
        head = _git(repo, "rev-parse", "HEAD")
    except (OSError, subprocess.CalledProcessError) as error:
        return _check(name, "BLOCKED", f"git inspection failed: {error}")
    if status:
        return _check(
            name,
            "BLOCKED",
            "worktree is not clean",
            head=head,
            changed_paths=status.splitlines(),
        )
    return _check(name, "PASS", "clean worktree", head=head)


def _release_tag(repo: Path, name: str) -> dict[str, Any]:
    try:
        tags = [line for line in _git(repo, "tag", "--points-at", "HEAD").splitlines() if line]
    except (OSError, subprocess.CalledProcessError) as error:
        return _check(name, "BLOCKED", f"tag inspection failed: {error}")
    if not tags:
        return _check(name, "BLOCKED", "HEAD has no release tag")
    return _check(name, "PASS", "HEAD has a release tag", tags=tags)


def _benchmark_gate(path: Path) -> dict[str, Any]:
    if not path.exists():
        return _check("benchmark_protocol", "BLOCKED", f"missing file: {path}")
    try:
        from drosophila_pd.workbench import BenchmarkProtocol

        protocol = BenchmarkProtocol.from_dict(_load_yaml(path))
        validation = protocol.freeze_validation()
    except Exception as error:  # noqa: BLE001 - gate must report the blocker
        return _check("benchmark_protocol", "BLOCKED", f"could not load protocol: {error}")
    if validation["status"] != "READY":
        return _check(
            "benchmark_protocol",
            "BLOCKED",
            "benchmark freeze validation failed",
            validation=validation,
        )
    payload = _load_yaml(path)
    source = payload.get("source", {})
    contract = payload.get("evaluation_contract", {})
    review_status = str(
        source.get(
            "review_status",
            contract.get("review_status", "PENDING_SCIENTIFIC_REVIEW")
            if isinstance(contract, Mapping)
            else "PENDING_SCIENTIFIC_REVIEW",
        )
    ).upper()
    if review_status not in {"APPROVED", "SIGNED_OFF"}:
        return _check(
            "benchmark_protocol",
            "BLOCKED",
            "protocol is frozen computationally but lacks scientific reviewer sign-off",
            validation=validation,
            review_status=review_status,
        )
    return _check("benchmark_protocol", "PASS", "frozen and scientifically signed off", validation=validation)


def _benchmark_mapping_gate(path: Path) -> dict[str, Any]:
    """Require reviewer approval for section-specific assay mappings."""

    if not path.exists():
        return _check("benchmark_mapping", "BLOCKED", f"missing benchmark registry: {path}")
    try:
        payload = _load_yaml(path)
    except Exception as error:  # noqa: BLE001 - gate must report the blocker
        return _check("benchmark_mapping", "BLOCKED", f"could not load benchmark registry: {error}")
    contract = payload.get("evaluation_contract", {})
    if not isinstance(contract, Mapping):
        return _check("benchmark_mapping", "BLOCKED", "evaluation_contract is missing")
    status = str(contract.get("status", "")).upper()
    required_fields = contract.get("required_case_fields", [])
    if status not in {"APPROVED", "SIGNED_OFF"}:
        return _check(
            "benchmark_mapping",
            "BLOCKED",
            "section-specific benchmark mapping lacks scientific sign-off",
            mapping_status=status or "missing",
        )
    if not isinstance(required_fields, list) or not required_fields:
        return _check(
            "benchmark_mapping",
            "BLOCKED",
            "approved benchmark mapping does not declare required case context",
        )
    return _check("benchmark_mapping", "PASS", "section-specific benchmark mapping approved")


def _benchmark_evaluation_gate(path: Path | None, protocol_path: Path) -> dict[str, Any]:
    """Require a matched, held-out comparison before release can be ready."""

    if path is None:
        return _check(
            "benchmark_evaluation",
            "BLOCKED",
            "no held-out Workbench/baseline comparison supplied",
        )
    if not path.exists():
        return _check("benchmark_evaluation", "BLOCKED", f"missing comparison report: {path}")
    try:
        from drosophila_pd.workbench import BenchmarkProtocol

        protocol = BenchmarkProtocol.from_dict(_load_yaml(protocol_path))
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as error:  # noqa: BLE001 - gate must report the blocker
        return _check("benchmark_evaluation", "BLOCKED", f"could not read comparison report: {error}")

    if not isinstance(payload, Mapping):
        return _check("benchmark_evaluation", "BLOCKED", "comparison report must be a JSON object")
    if str(payload.get("evaluation_split", "")).lower() != "held_out":
        return _check("benchmark_evaluation", "BLOCKED", "comparison must evaluate the held_out split")
    if str(payload.get("protocol_hash", "")) != protocol.protocol_hash:
        return _check(
            "benchmark_evaluation",
            "BLOCKED",
            "comparison protocol hash does not match the frozen registry",
            expected_protocol_hash=protocol.protocol_hash,
            reported_protocol_hash=payload.get("protocol_hash"),
        )
    systems = payload.get("systems")
    required_systems = {"workbench", "random", "effect_only", "heuristic"}
    if str(protocol.protocol_id).endswith("v2") or "table3" in str(protocol.protocol_id):
        required_systems.update({"original_model", "degree_preserving_rewire"})
    if not isinstance(systems, Mapping):
        return _check("benchmark_evaluation", "BLOCKED", "comparison has no systems mapping")
    missing_systems = sorted(required_systems - {str(name) for name in systems})
    if missing_systems:
        return _check(
            "benchmark_evaluation",
            "BLOCKED",
            "required baseline systems are missing",
            missing_systems=missing_systems,
        )
    baseline_protocol = payload.get("baseline_protocol")
    if not isinstance(baseline_protocol, Mapping):
        return _check(
            "benchmark_evaluation",
            "BLOCKED",
            "comparison does not declare its baseline calibration protocol",
        )
    if baseline_protocol.get("random_seed") is None or not baseline_protocol.get("calibration"):
        return _check(
            "benchmark_evaluation",
            "BLOCKED",
            "comparison baseline protocol lacks random seed or calibration rule",
        )
    held_out_count = len(protocol.held_out_case_ids)
    matched = payload.get("matched_evaluation")
    if not isinstance(matched, Mapping):
        return _check(
            "benchmark_evaluation",
            "BLOCKED",
            "comparison does not declare a matched assessable denominator",
        )
    if str(matched.get("status", "")).upper() != "COMPLETE":
        return _check(
            "benchmark_evaluation",
            "BLOCKED",
            "held-out comparison is partial; all systems must be assessable on the same frozen cases",
            matched_evaluation=matched,
        )
    try:
        matched_count = int(matched.get("common_assessable_case_count", -1))
        matched_total = int(matched.get("held_out_case_count", -1))
    except (TypeError, ValueError):
        matched_count = matched_total = -1
    if matched_count != held_out_count or matched_total != held_out_count:
        return _check(
            "benchmark_evaluation",
            "BLOCKED",
            "matched assessable denominator does not cover every held-out case",
            matched_evaluation=matched,
            expected_held_out_case_count=held_out_count,
        )
    matched_case_ids = matched.get("common_assessable_case_ids")
    expected_case_ids = set(protocol.held_out_case_ids)
    if not isinstance(matched_case_ids, list) or {str(case_id) for case_id in matched_case_ids} != expected_case_ids:
        return _check(
            "benchmark_evaluation",
            "BLOCKED",
            "matched denominator does not list exactly the frozen held-out case IDs",
            expected_case_ids=sorted(expected_case_ids),
            reported_case_ids=matched_case_ids,
        )
    incomplete = []
    for name in sorted(required_systems):
        report = systems.get(name)
        if not isinstance(report, Mapping):
            incomplete.append(f"{name}:not_an_object")
            continue
        if str(report.get("status", "")).upper() != "EVALUATED":
            incomplete.append(f"{name}:status_{report.get('status', 'missing')}")
        try:
            reported_case_count = int(report.get("case_count", -1))
        except (TypeError, ValueError):
            reported_case_count = -1
        if reported_case_count != held_out_count:
            incomplete.append(f"{name}:case_count_{report.get('case_count')}")
        try:
            assessable_count = int(report.get("assessable_case_count", -1))
        except (TypeError, ValueError):
            assessable_count = -1
        if assessable_count != held_out_count:
            incomplete.append(f"{name}:assessable_case_count_{report.get('assessable_case_count')}")
        try:
            coverage = float(report.get("coverage", float("nan")))
        except (TypeError, ValueError):
            coverage = float("nan")
        if not math.isfinite(coverage) or coverage != 1.0:
            incomplete.append(f"{name}:coverage_{report.get('coverage')}")
        if report.get("unassessable_cases") not in ([], None):
            incomplete.append(f"{name}:unassessable_cases_present")
        evaluated_cases = report.get("evaluated_cases")
        if not isinstance(evaluated_cases, list) or {
            str(item.get("case_id")) for item in evaluated_cases if isinstance(item, Mapping)
        } != expected_case_ids:
            incomplete.append(f"{name}:evaluated_case_ids_mismatch")
        required_metrics = {"confusion_matrix", "precision", "recall", "precision_at_k", "coverage", "false_negatives"}
        incomplete.extend(
            f"{name}:missing_{metric}"
            for metric in sorted(required_metrics)
            if metric not in report
        )
        if not isinstance(report.get("precision_at_k"), Mapping) or report["precision_at_k"].get("value") is None:
            incomplete.append(f"{name}:precision_at_k_value_missing")
    if incomplete:
        return _check(
            "benchmark_evaluation",
            "BLOCKED",
            "held-out comparison is incomplete",
            incomplete=incomplete,
        )
    return _check(
        "benchmark_evaluation",
        "PASS",
        "held-out Workbench and baseline comparison is complete",
        systems=sorted(required_systems),
        held_out_case_count=held_out_count,
    )


def _seed_gate(path: Path | None, name: str, expected_count: int, require_new: bool = False) -> dict[str, Any]:
    if path is None:
        return _check(name, "BLOCKED", "no seed-run manifest supplied")
    if not path.exists():
        return _check(name, "BLOCKED", f"missing seed-run manifest: {path}")
    try:
        payload = _load_yaml(path) if path.suffix.lower() in {".yaml", ".yml"} else json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping):
            raise ValueError("seed manifest must be an object")
        seeds = payload.get("seeds", payload.get("seed_values", []))
        if not isinstance(seeds, list):
            raise ValueError("seeds must be a list")
        status = str(payload.get("status", "")).upper()
        unique_seeds = {str(seed) for seed in seeds}
        new_seed_set = bool(payload.get("new_seed_set", payload.get("fresh_seeds", False)))
        jobs = payload.get("jobs")
        if not isinstance(jobs, list) or not jobs:
            raise ValueError("jobs must be a non-empty list of completed job records")
        job_seed_set: set[str] = set()
        job_keys: set[tuple[str, str]] = set()
        job_errors: list[str] = []
        for index, job in enumerate(jobs):
            if not isinstance(job, Mapping):
                job_errors.append(f"job[{index}] is not an object")
                continue
            job_status = str(job.get("status", "")).upper()
            if job_status != "COMPLETED":
                job_errors.append(f"job[{index}] status={job.get('status', 'missing')}")
            config = job.get("config")
            if not isinstance(config, Mapping):
                job_errors.append(f"job[{index}] has no config object")
                continue
            candidate_id = str(config.get("candidate_id", "")).strip()
            seed = str(config.get("seed", "")).strip()
            if not candidate_id or not seed:
                job_errors.append(f"job[{index}] lacks candidate_id or seed")
                continue
            key = (candidate_id, seed)
            if key in job_keys:
                job_errors.append(f"duplicate candidate/seed pair {candidate_id}/{seed}")
            job_keys.add(key)
            job_seed_set.add(seed)
        if job_errors:
            raise ValueError("; ".join(job_errors))
        if len(seeds) != expected_count or len(unique_seeds) != expected_count:
            raise ValueError(f"expected {expected_count} unique declared seeds, got {len(unique_seeds)}")
        if job_seed_set != unique_seeds:
            raise ValueError(
                "completed jobs do not cover exactly the declared seed set "
                f"(declared={sorted(unique_seeds)}, jobs={sorted(job_seed_set)})"
            )
        reference_seeds: set[str] = set()
        reference_manifest = payload.get("reference_seed_manifest")
        raw_reference_seeds = payload.get("reference_seeds")
        if isinstance(raw_reference_seeds, list):
            reference_seeds = {str(seed) for seed in raw_reference_seeds}
        if reference_manifest:
            reference_path = Path(str(reference_manifest))
            if not reference_path.is_absolute():
                reference_path = path.parent / reference_path
            if not reference_path.exists():
                raise ValueError(f"reference seed manifest is missing: {reference_path}")
            reference_payload = (
                _load_yaml(reference_path)
                if reference_path.suffix.lower() in {".yaml", ".yml"}
                else json.loads(reference_path.read_text(encoding="utf-8"))
            )
            if not isinstance(reference_payload, Mapping):
                raise ValueError("reference seed manifest must be an object")
            reference_values = reference_payload.get("seeds", reference_payload.get("seed_values", []))
            if not isinstance(reference_values, list):
                raise ValueError("reference seed manifest seeds must be a list")
            file_reference_seeds = {str(seed) for seed in reference_values}
            if reference_seeds and reference_seeds != file_reference_seeds:
                raise ValueError("reference_seeds does not match reference_seed_manifest")
            reference_seeds = file_reference_seeds
        if require_new:
            if not reference_seeds:
                raise ValueError("confirmation manifest does not identify the screening seed set")
            if unique_seeds.intersection(reference_seeds):
                raise ValueError("confirmation seeds overlap the screening seed set")
            if not new_seed_set:
                raise ValueError("confirmation seeds are not marked as a new seed set")
    except Exception as error:  # noqa: BLE001
        return _check(name, "BLOCKED", f"could not read seed manifest: {error}")
    if status not in {"PASS", "COMPLETED", "COMPLETE"}:
        return _check(name, "BLOCKED", f"seed manifest status is {status or 'missing'}")
    return _check(
        name,
        "PASS",
        f"{len(unique_seeds)} unique seeds and completed jobs verified",
        seeds=sorted(unique_seeds),
        completed_job_count=len(jobs),
    )


def _reproduction_gate(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return _check("independent_reproduction", "BLOCKED", "completed second-operator manifest is missing")
    try:
        payload = _load_yaml(path) if path.suffix.lower() in {".yaml", ".yml"} else json.loads(path.read_text(encoding="utf-8"))
    except Exception as error:  # noqa: BLE001
        return _check("independent_reproduction", "BLOCKED", f"could not read manifest: {error}")
    environment = payload.get("environment", {})
    inputs = payload.get("inputs", {})
    subset = payload.get("subset", {})
    comparison = payload.get("comparison", {})
    required = (
        str(payload.get("status", "")).upper() == "PASS",
        str(payload.get("operator_role", "")).lower() in {"second_operator", "independent_operator"},
        bool(str(payload.get("operator_name", "")).strip()),
        bool(str(payload.get("source_commit", "")).strip()),
        bool(environment.get("clean_install")),
        bool(environment.get("lockfile_or_export")),
        bool(inputs.get("study_config_hash")),
        isinstance(inputs.get("public_artifact_hashes"), list)
        and bool(inputs.get("public_artifact_hashes")),
        bool(subset.get("includes_success_case")),
        bool(subset.get("includes_failure_case")),
        bool(comparison.get("manifests_match")),
        bool(comparison.get("provenance_match")),
        bool(comparison.get("outputs_within_declared_tolerance")),
        bool(comparison.get("failure_states_checked")),
        not comparison.get("discrepancies"),
    )
    if not all(required):
        return _check("independent_reproduction", "BLOCKED", "second-operator reproduction is incomplete", payload=payload)
    return _check("independent_reproduction", "PASS", "clean second-operator reproduction passed")


def _biology_gate(path: Path) -> dict[str, Any]:
    if not path.exists():
        return _check("mn9_biological_review", "BLOCKED", f"missing review record: {path}")
    try:
        payload = _load_yaml(path)
    except Exception as error:  # noqa: BLE001
        return _check("mn9_biological_review", "BLOCKED", f"could not read review record: {error}")
    status = str(payload.get("status", "")).upper()
    checks = payload.get("biology_checks", {})
    all_approved = isinstance(checks, Mapping) and checks and all(str(value).upper() == "APPROVED" for value in checks.values())
    protocol_status = str(payload.get("wet_lab_protocol", {}).get("status", "")).upper()
    if status not in {"APPROVED", "SIGNED_OFF"} or not all_approved or protocol_status not in {"APPROVED", "READY"}:
        return _check("mn9_biological_review", "BLOCKED", "MN9/driver-line/protocol review is not approved", review_status=status)
    return _check("mn9_biological_review", "PASS", "MN9 biological review approved")


def _computational_public_data_profile(
    registry_path: Path,
    artifact_path: Path,
) -> dict[str, Any]:
    """Report public-data integrity without closing human release gates."""

    if not registry_path.exists():
        return {
            "release_profile": "computational_public_data",
            "status": "BLOCKED",
            "blockers": ["public_registry_missing"],
            "limitations": ["human_source_review_pending", "independent_operator_pending"],
        }
    try:
        from validate_workbench_registry import validate
        from drosophila_pd.workbench import BenchmarkProtocol

        integrity = validate(registry_path, artifact_path)
        protocol = BenchmarkProtocol.from_dict(_load_yaml(registry_path))
        freeze = protocol.freeze_validation()
    except Exception as error:  # noqa: BLE001 - profile must remain auditable
        return {
            "release_profile": "computational_public_data",
            "status": "BLOCKED",
            "blockers": ["public_registry_validation_error"],
            "error": f"{type(error).__name__}: {error}",
            "limitations": ["human_source_review_pending", "independent_operator_pending"],
        }
    blockers = []
    if integrity.get("status") != "READY":
        blockers.append("public_registry_integrity")
    if freeze.get("status") != "READY":
        blockers.append("public_registry_protocol_freeze")
    return {
        "release_profile": "computational_public_data",
        "status": "READY_WITH_LIMITATIONS" if not blockers else "BLOCKED",
        "blockers": blockers,
        "checks": {"registry_integrity": integrity, "protocol_freeze": freeze},
        "limitations": [
            "human_source_and_biological_mapping_review_pending",
            "independent_second_operator_not_claimed",
            "worktree_and_release_tags_are_not_closed_by_this_profile",
            "no_wet_lab_or_prospective_biological_validation",
        ],
        "claim_scope": (
            "Reproducible computational public-data benchmark profile only; "
            "not Q1 readiness or biological validation."
        ),
    }


def run_gate(args: argparse.Namespace) -> dict[str, Any]:
    checks = [
        _benchmark_gate(args.benchmark),
        _benchmark_mapping_gate(args.benchmark),
        _benchmark_evaluation_gate(args.benchmark_comparison, args.benchmark),
        _seed_gate(args.screening_manifest, "screening_10_seeds", 10),
        _seed_gate(args.confirmation_manifest, "confirmation_30_new_seeds", 30, require_new=True),
        _reproduction_gate(args.reproduction_manifest),
        _biology_gate(args.biology_review),
        _clean_worktree("platform_worktree", args.platform_repo),
        _clean_worktree("neural_worktree", args.neural_repo),
        _release_tag(args.platform_repo, "platform_release_tag"),
        _release_tag(args.neural_repo, "neural_release_tag"),
    ]
    blockers = [check["name"] for check in checks if check["status"] == "BLOCKED"]
    return {
        "gate_version": 1,
        "status": "READY_FOR_RELEASE" if not blockers else "BLOCKED",
        "blockers": blockers,
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform-repo", type=Path, default=REPO_ROOT)
    parser.add_argument("--neural-repo", type=Path, default=REPO_ROOT.parent / "drosophila-pd-neural-disease")
    parser.add_argument("--benchmark", type=Path, default=REPO_ROOT / "configs/workbench/shiu_public_benchmark_v1.yaml")
    parser.add_argument(
        "--profile",
        choices=("legacy", "computational_public_data"),
        default="legacy",
        help="legacy all-gate release check or the explicitly limited public-data profile",
    )
    parser.add_argument(
        "--public-registry",
        type=Path,
        default=REPO_ROOT / "configs/workbench/shiu_public_benchmark_v2.json",
    )
    parser.add_argument(
        "--public-artifact",
        type=Path,
        default=REPO_ROOT / "data/benchmarks/41586_2024_7763_MOESM2_ESM.xlsx",
    )
    parser.add_argument("--benchmark-comparison", type=Path, help="Matched held-out Workbench/baseline comparison JSON")
    parser.add_argument("--biology-review", type=Path, default=REPO_ROOT / "configs/workbench/mn9_biological_review.yaml")
    parser.add_argument("--reproduction-manifest", type=Path)
    parser.add_argument("--screening-manifest", type=Path)
    parser.add_argument("--confirmation-manifest", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = (
        _computational_public_data_profile(args.public_registry, args.public_artifact)
        if args.profile == "computational_public_data"
        else run_gate(args)
    )
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if result["status"] in {"READY_FOR_RELEASE", "READY_WITH_LIMITATIONS"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
