from __future__ import annotations

import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from drosophila_pd.workbench import (
    CandidateSpec,
    CapabilityDescriptor,
    CommandBackendAdapter,
    JobStatus,
    RankingPolicy,
    StudySpec,
    WorkbenchService,
    WorkbenchStore,
    default_adapters,
)
from drosophila_pd.workbench import service as service_module


def _service(tmp_path: Path, *, slow: bool = False) -> tuple[WorkbenchService, StudySpec]:
    script = tmp_path / "fake_backend.py"
    script.write_text(
        "import argparse, json, time\n"
        "parser = argparse.ArgumentParser()\n"
        "parser.add_argument('--output', required=True)\n"
        "parser.add_argument('--sleep', action='store_true')\n"
        "parser.add_argument('--seed', type=int)\n"
        "parser.add_argument('--candidate', default='')\n"
        "args = parser.parse_args()\n"
        "if args.sleep: time.sleep(30)\n"
        "speed = 2.0 if args.candidate == 'c1' and args.seed is not None else 1.0\n"
        "payload = {'overall_pass': True, 'derived_locomotion_metrics': {'speed': speed}}\n"
        "if args.seed is not None: payload['configuration'] = {'random_seed': args.seed}\n"
        "with open(args.output, 'w', encoding='utf-8') as handle:\n"
        "    json.dump(payload, handle)\n",
        encoding="utf-8",
    )

    def command(_study, config, artifact_dir):
        output = artifact_dir / "result.json"
        command = [sys.executable, str(script), "--output", str(output)]
        if config.get("sleep"):
            command.append("--sleep")
        if config.get("seed") is not None:
            command.extend(("--seed", str(config["seed"])))
        if config.get("candidate_id") is not None:
            command.extend(("--candidate", str(config["candidate_id"])))
        return command

    adapter = CommandBackendAdapter(
        name="fake",
        descriptor=CapabilityDescriptor(
            name="fake",
            display_name="test backend",
            ready=True,
            supported_assays=("locomotion",),
            supports_explicit_seed=True,
            supports_parameter_overrides=True,
        ),
        repo_root=tmp_path,
        interpreter=sys.executable,
        command_factory=command,
        script_path=script,
    )
    service = WorkbenchService(
        store=WorkbenchStore(tmp_path / "state.sqlite3"),
        artifact_root=tmp_path / "artifacts",
        adapters={"fake": adapter},
    )
    study = StudySpec(
        name="service test",
        hypothesis="h",
        falsifiable_prediction="p",
        assay="locomotion",
        primary_metric="speed",
        candidates=(CandidateSpec("c1", "C1"), CandidateSpec("no_perturbation", "Control")),
        run_plan={
            "confirmation_seed_repetitions": 3,
            "sensitivity": {"fake.speed": [0.9, 1.0, 1.1]},
        },
        backend="fake",
    )
    service.create_study(study)
    return service, study


def test_service_runs_subprocess_and_writes_manifest_and_report(tmp_path) -> None:
    service, study = _service(tmp_path)
    job = service.submit_job(study.study_id, {"candidate_id": "c1"}, job_id="job-1")
    completed = service.run_job(job.job_id)

    assert completed.status == JobStatus.COMPLETED
    manifest_path = Path(completed.manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "COMPLETED"
    assert manifest["job_id"] == "job-1"
    assert manifest["artifact_hashes"]["result.json"]
    assert manifest["provenance"]["job_configuration"]["candidate_id"] == "c1"
    assert manifest["provenance"]["environment"]["python_executable"]
    assert manifest["provenance"]["pre_run"]["coordinator_code_state"]
    report = service.get_report(study.study_id)
    assert report["ranking_eligible"] is False
    assert report["results"][0]["metrics"]["overall_pass"] is True


def test_inventory_hashes_nested_manifests_but_not_outer_manifest(tmp_path: Path) -> None:
    root = tmp_path / "run"
    nested = root / "lif_condition"
    nested.mkdir(parents=True)
    (root / "run_manifest.json").write_text("{}", encoding="utf-8")
    (nested / "run_manifest.json").write_text("{}", encoding="utf-8")
    (nested / "metrics.json").write_text("{}", encoding="utf-8")

    inventory = service_module._inventory(root)

    assert "run_manifest.json" not in inventory
    assert "lif_condition/run_manifest.json" in inventory
    assert "lif_condition/metrics.json" in inventory


def test_metric_extractor_resolves_fully_qualified_nested_neural_path() -> None:
    value, error = service_module._extract_metric_value(
        {"metrics": {"readout_rates_hz": {"720575940660219265": 80.0}}},
        "metrics.readout_rates_hz.720575940660219265",
    )

    assert value == 80.0
    assert error is None


def test_git_state_hashes_file_contents_not_only_status(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True, text=True)
    source = repo / "src" / "example.py"
    source.parent.mkdir()
    source.write_text("value = 1\n", encoding="utf-8")
    first = service_module._git_state(repo)
    source.write_text("value = 2\n", encoding="utf-8")
    second = service_module._git_state(repo)

    assert first is not None and second is not None
    assert first["dirty"] is True
    assert first["content_sha256"] != second["content_sha256"]


def test_cancel_pending_then_resume_uses_a_new_run_directory(tmp_path) -> None:
    service, study = _service(tmp_path)
    job = service.submit_job(study.study_id, {"candidate_id": "c1"}, job_id="job-2")
    cancelled = service.cancel_job(job.job_id)
    assert cancelled.status == JobStatus.CANCELLED
    resumed = service.resume_job(job.job_id)
    assert resumed.status == JobStatus.PENDING
    completed = service.run_job(job.job_id)
    assert completed.status == JobStatus.COMPLETED
    assert completed.attempt == 1
    assert Path(completed.artifact_dir).is_dir()


def test_compare_uses_assay_contract_and_stays_exploratory(tmp_path) -> None:
    service, study = _service(tmp_path)
    reference = service.submit_job(study.study_id, {"candidate_id": "reference"}, job_id="job-reference")
    condition = service.submit_job(study.study_id, {"candidate_id": "condition"}, job_id="job-condition")
    service.run_job(reference.job_id)
    service.run_job(condition.job_id)

    comparison = service.compare_jobs(study.study_id, reference.job_id, condition.job_id)
    assert comparison["status"] == "EXPLORATORY"
    assert comparison["primary_metric"] == "speed"
    assert comparison["absolute_delta"] == 0.0


def test_evidence_bundle_is_unreviewed_until_human_approval(tmp_path) -> None:
    service, study = _service(tmp_path)
    job = service.submit_job(study.study_id, {"candidate_id": "c1"}, job_id="job-handoff")
    service.run_job(job.job_id)

    draft = service.get_evidence_bundle(study.study_id)
    assert draft["status"] == "DRAFT_UNREVIEWED"
    assert draft["dossiers"][0]["handoff_status"] == "READY_FOR_REVIEW"
    assert draft["dossiers"][0]["computation"]["run_count"] == 1
    assert "must not modify" in draft["ai_policy"]

    service.record_review(
        study.study_id,
        reviewer="PI",
        decision="approved",
        comments="Reviewed source and computational limits.",
    )
    approved = service.get_evidence_bundle(study.study_id)
    assert approved["status"] == "APPROVED_FOR_AI_SUMMARY"
    assert approved["review"]["reviewer"]["name"] == "PI"

    archive = service.export_evidence_bundle(study.study_id, tmp_path / "handoff.zip")
    with zipfile.ZipFile(archive) as bundle:
        names = set(bundle.namelist())
    assert {"bundle.json", "handoff.md", "checksums/sha256.json"}.issubset(names)


def test_rank_study_pairs_completed_jobs_and_persists_provenance(tmp_path) -> None:
    service, study = _service(tmp_path)
    for seed in range(3):
        control = service.submit_job(
            study.study_id,
            {"candidate_id": "no_perturbation", "seed": seed},
            job_id=f"control-{seed}",
        )
        condition = service.submit_job(
            study.study_id,
            {"candidate_id": "c1", "seed": seed},
            job_id=f"condition-{seed}",
        )
        service.run_job(control.job_id)
        service.run_job(condition.job_id)

    report = service.rank_study(
        study.study_id,
        RankingPolicy(
            study_id=study.study_id,
            control_candidate_id="no_perturbation",
            assay="locomotion",
            primary_metric="speed",
            expected_direction="increase",
            minimum_pairs=3,
            bootstrap_samples=100,
            minimum_effect_threshold=0.5,
        ),
    )

    assert report["status"] == "READY"
    assert report["collection"]["status"] == "READY"
    assert len(report["collection"]["observations"]) == 3
    assert report["collection"]["unpaired_jobs"] == []
    assert report["ranking"]["ranking_eligible"] is True
    assert report["ranking"]["ranked_candidates"][0]["candidate_id"] == "c1"
    assert report["provenance"]["policy_hash"]
    assert len(report["provenance"]["source_manifests"]) == 6
    report_path = Path(report["report_path"])
    assert report_path.is_file()
    assert json.loads(report_path.read_text(encoding="utf-8"))["study_id"] == study.study_id

    draft_bundle = service.get_evidence_bundle(study.study_id)
    assert draft_bundle["ranking_report"]["study_id"] == study.study_id
    assert draft_bundle["ranking_review"]["status"] == "PENDING_HUMAN_REVIEW"
    assert draft_bundle["dossiers"][0]["computation"]["ranking"]["section"] == "ranked_candidates"

    service.record_review(
        study.study_id,
        reviewer="PI",
        decision="approved",
        comments="Reviewed ranking scope, QC and computational limitations.",
    )
    approved_bundle = service.get_evidence_bundle(study.study_id)
    assert approved_bundle["ranking_review"]["status"] == "APPROVED_FOR_HANDOFF"
    archive = service.export_evidence_bundle(study.study_id, tmp_path / "ranked-handoff.zip")
    with zipfile.ZipFile(archive) as bundle:
        assert "reports/ranking_report.json" in set(bundle.namelist())

    plan = service.confirmation_plan(study.study_id, top_k=1)
    assert plan["status"] == "READY_FOR_SUBMISSION"
    assert plan["fresh_seeds"] == [3, 4, 5]
    assert plan["backend"]["supports_explicit_seed"] is True
    assert Path(plan["plan_path"]).is_file()

    submission = service.submit_confirmation_plan(study.study_id)
    assert submission["status"] == "SUBMITTED"
    assert submission["submitted_job_count"] == 6
    assert len(submission["job_ids"]) == 6
    assert all(job["config"]["phase"].startswith("confirmation") for job in submission["jobs"])
    assert Path(submission["submission_path"]).is_file()

    repeated = service.submit_confirmation_plan(study.study_id)
    assert repeated["status"] == "SUBMITTED"
    assert repeated["job_ids"] == submission["job_ids"]

    run_report = service.run_confirmation(study.study_id)
    assert run_report["status"] == "COMPLETED"
    assert run_report["completed_job_count"] == 6
    assert Path(run_report["run_report_path"]).is_file()

    handoff_after_submission = service.get_evidence_bundle(study.study_id)
    assert handoff_after_submission["confirmation_submission"]["status"] == "SUBMITTED"
    assert handoff_after_submission["dossiers"][0]["computation"]["confirmation_submission"]["status"] == "SUBMITTED"
    assert handoff_after_submission["confirmation_run"]["status"] == "COMPLETED"
    archive_after_run = service.export_evidence_bundle(study.study_id, tmp_path / "completed-handoff.zip")
    with zipfile.ZipFile(archive_after_run) as bundle:
        names = set(bundle.namelist())
    assert "reports/confirmation_run.json" in names

    sensitivity_submission = service.submit_confirmation_plan(
        study.study_id,
        include_sensitivity=True,
    )
    assert sensitivity_submission["status"] == "SUBMITTED"
    assert sensitivity_submission["include_sensitivity"] is True
    assert sensitivity_submission["sensitivity_case_count"] == 3
    assert sensitivity_submission["sensitivity_job_count"] == 18
    assert sensitivity_submission["submitted_job_count"] == 24
    sensitivity_jobs = [
        job for job in sensitivity_submission["jobs"]
        if job["config"]["phase"] == "confirmation_sensitivity"
    ]
    assert sensitivity_jobs
    assert all(job["config"]["parameter_overrides"] for job in sensitivity_jobs)
    sensitivity_run = service.run_confirmation(study.study_id)
    assert sensitivity_run["status"] == "COMPLETED"
    assert sensitivity_run["completed_job_count"] == 24


def test_rank_study_keeps_unpaired_jobs_out_of_ranking(tmp_path) -> None:
    service, study = _service(tmp_path)
    control = service.submit_job(
        study.study_id,
        {"candidate_id": "no_perturbation", "seed": 0},
        job_id="control-only",
    )
    condition = service.submit_job(
        study.study_id,
        {"candidate_id": "c1", "seed": 1},
        job_id="condition-without-control",
    )
    service.run_job(control.job_id)
    service.run_job(condition.job_id)

    report = service.rank_study(
        study.study_id,
        RankingPolicy(
            study_id=study.study_id,
            control_candidate_id="no_perturbation",
            assay="locomotion",
            primary_metric="speed",
            minimum_effect_threshold=0.5,
            bootstrap_samples=100,
        ),
    )

    assert report["status"] == "INCOMPLETE"
    assert report["ranking"]["ranking_eligible"] is False
    assert report["collection"]["unpaired_jobs"][0]["reason"] == "missing matching control job for seed"


def test_collection_pairs_by_phase_and_sensitivity_case(tmp_path) -> None:
    service, study = _service(tmp_path)
    configs = [
        ("base-control", {"candidate_id": "no_perturbation", "seed": 0}),
        ("base-candidate", {"candidate_id": "c1", "seed": 0}),
        (
            "sensitivity-control",
            {
                "candidate_id": "no_perturbation",
                "seed": 0,
                "phase": "confirmation_sensitivity_control",
                "parameter_overrides": {"fake.speed": 1.1},
            },
        ),
        (
            "sensitivity-candidate",
            {
                "candidate_id": "c1",
                "seed": 0,
                "phase": "confirmation_sensitivity",
                "parameter_overrides": {"fake.speed": 1.1},
            },
        ),
    ]
    for job_id, config in configs:
        job = service.submit_job(study.study_id, config, job_id=job_id)
        service.run_job(job.job_id)

    collection = service.collect_ranking_observations(
        study.study_id,
        RankingPolicy(
            study_id=study.study_id,
            control_candidate_id="no_perturbation",
            assay="locomotion",
            primary_metric="speed",
            minimum_effect_threshold=0.5,
            bootstrap_samples=100,
        ),
    )

    assert collection["status"] == "READY"
    assert len(collection["observations"]) == 2
    assert len({item["metadata"]["pairing_key"] for item in collection["observations"]}) == 2
    assert collection["unpaired_jobs"] == []


def test_collection_pairs_control_with_candidate_specific_intervention_fields(tmp_path) -> None:
    service, study = _service(tmp_path)
    for job_id, config in (
        (
            "activation-control",
            {"candidate_id": "no_perturbation", "seed": 0},
        ),
        (
            "activation-candidate",
            {
                "candidate_id": "c1",
                "seed": 0,
                "input_ids": ["input-a"],
                "stimulus_rate_hz": 150.0,
            },
        ),
    ):
        job = service.submit_job(study.study_id, config, job_id=job_id)
        service.run_job(job.job_id)

    collection = service.collect_ranking_observations(
        study.study_id,
        RankingPolicy(
            study_id=study.study_id,
            control_candidate_id="no_perturbation",
            assay="locomotion",
            primary_metric="speed",
            minimum_effect_threshold=0.5,
            bootstrap_samples=100,
        ),
    )

    assert collection["status"] == "READY"
    assert len(collection["observations"]) == 1
    assert collection["unpaired_jobs"] == []


def test_collection_reports_declared_candidate_coverage(tmp_path) -> None:
    service, study = _service(tmp_path)
    control = service.submit_job(
        study.study_id,
        {"candidate_id": "no_perturbation", "seed": 0},
        job_id="coverage-control",
    )
    service.run_job(control.job_id)

    collection = service.collect_ranking_observations(
        study.study_id,
        RankingPolicy(
            study_id=study.study_id,
            control_candidate_id="no_perturbation",
            assay="locomotion",
            primary_metric="speed",
            minimum_effect_threshold=0.5,
            bootstrap_samples=100,
        ),
    )

    assert collection["status"] == "INCOMPLETE"
    assert collection["missing_candidate_ids"] == ["c1"]
    assert collection["candidate_coverage"] == 0.0


def test_concrete_backend_materializes_intervention_and_rejects_unsupported_candidate(tmp_path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    service = WorkbenchService(
        store=WorkbenchStore(tmp_path / "state.sqlite3"),
        artifact_root=tmp_path / "artifacts",
        adapters=default_adapters(repo_root=repo_root, interpreter=sys.executable),
    )
    study = StudySpec(
        name="concrete adapter contract",
        hypothesis="h",
        falsifiable_prediction="p",
        assay="motor_flat_ground",
        primary_metric="mean_planar_path_speed_mm_s",
        candidates=(
            CandidateSpec("control", "Control"),
            CandidateSpec(
                "frequency",
                "Frequency override",
                intervention={
                    "type": "controller_parameter_override",
                    "parameters": {"controller.intrinsic_frequency_hz": 14.0},
                },
            ),
        ),
    )
    service.create_study(study)
    config = {
        "candidate_id": "frequency",
        "baseline_config": repo_root / "configs" / "experiments" / "healthy_baseline.yaml",
        "seed": 3,
    }
    job = service.submit_job(study.study_id, config, job_id="frequency-job")
    assert job.config["intervention_type"] == "controller_parameter_override"
    assert job.config["parameter_overrides"] == {"controller.intrinsic_frequency_hz": 14.0}
    adapter = service.adapters["flygym_healthy"]
    control_command = adapter.command(
        study,
        {
            "candidate_id": "control",
            "baseline_config": repo_root / "configs" / "experiments" / "healthy_baseline.yaml",
            "seed": 3,
        },
        tmp_path / "control",
    )
    candidate_command = adapter.command(study, job.config, tmp_path / "candidate")
    assert control_command != candidate_command
    assert "--override-json" in candidate_command

    invalid_study = StudySpec(
        name="unsupported adapter contract",
        hypothesis="h",
        falsifiable_prediction="p",
        assay="motor_flat_ground",
        primary_metric="mean_planar_path_speed_mm_s",
        candidates=(CandidateSpec("bad", "Bad", intervention={"type": "activation"}),),
    )
    service.create_study(invalid_study)
    with pytest.raises(ValueError, match="not supported by backend"):
        service.submit_job(
            invalid_study.study_id,
            {
                "candidate_id": "bad",
                "baseline_config": repo_root / "configs" / "experiments" / "healthy_baseline.yaml",
            },
        )


def test_approved_ranking_review_is_invalidated_when_report_changes(tmp_path) -> None:
    service, study = _service(tmp_path)
    ranking_path = service.artifact_root / study.study_id / "ranking_report.json"
    ranking_path.parent.mkdir(parents=True, exist_ok=True)
    ranking = {
        "report_version": 1,
        "study_id": study.study_id,
        "collection": {"status": "READY", "control_candidate_id": "no_perturbation"},
        "ranking": {
            "ranking_eligible": True,
            "ranked_candidates": [
                {"candidate_id": "c1", "rank": 1, "status": "RANKED"}
            ],
            "not_ranked": [],
        },
    }
    ranking_path.write_text(json.dumps(ranking), encoding="utf-8")
    service.record_review(study.study_id, reviewer="PI", decision="approved")
    assert service.get_evidence_bundle(study.study_id)["ranking_review"]["status"] == "APPROVED_FOR_HANDOFF"

    ranking["ranking"]["ranked_candidates"][0]["status"] = "EXPLORATORY"
    ranking_path.write_text(json.dumps(ranking), encoding="utf-8")
    stale = service.get_evidence_bundle(study.study_id)
    assert stale["ranking_review"]["status"] == "STALE_REVIEW"
    assert stale["ranking_review"]["can_be_used_for_handoff_priority"] is False


def test_recover_stale_running_job_requires_explicit_resume(tmp_path) -> None:
    service, study = _service(tmp_path)
    job = service.submit_job(study.study_id, {"candidate_id": "c1"}, job_id="stale-job")
    job.status = JobStatus.RUNNING
    job.started_at = "2000-01-01T00:00:00+00:00"
    service.store.update_job(job, event="started_without_worker")

    recovered = service.recover_stale_jobs(stale_after_s=0)

    assert [item.job_id for item in recovered] == ["stale-job"]
    assert service.get_job("stale-job").status == JobStatus.FAILED
    assert "resume explicitly" in service.get_job("stale-job").error


def test_screening_submission_expands_candidate_seed_matrix(tmp_path) -> None:
    service, study = _service(tmp_path)
    submission = service.submit_screening(
        study.study_id,
        [0, 1],
        candidate_ids=["no_perturbation", "c1"],
    )

    assert submission["status"] == "SUBMITTED"
    assert submission["expected_job_count"] == 4
    assert submission["submitted_job_count"] == 4
    assert all(job["config"]["phase"] == "screening" for job in submission["jobs"])
    repeated = service.submit_screening(
        study.study_id,
        [0, 1],
        candidate_ids=["no_perturbation", "c1"],
    )
    assert repeated["status"] == "SUBMITTED"
    assert repeated["job_ids"] == submission["job_ids"]

    run = service.run_screening(study.study_id)
    assert run["status"] == "COMPLETED"
    assert run["completed_job_count"] == 4
