"""Task04 engineering-only tests; imports only stdlib, pytest and pinned pure code."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "src/drosophila_pd/workbench"
LEDGER_PATH = ROOT / "docs/publication_review/TASK04_ORACLE_LEDGER.json"
LEDGER = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
spec = importlib.util.spec_from_file_location("task04_package", CODE / "decision_package.py")
dp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dp)


def fixture(case):
    models, support = dp.pure_modules()
    mutation = case["mutation"]
    pending = "pending" in mutation
    mapping = support.MappingRecord(
        mapping_id="m", biological_target="engineering-target", backend="engineering-backend",
        id_namespace="engineering-id", dataset_id="engineering-dataset", intervention_type="activation",
        target_ids=("t",), readout_ids=("r",), sources=({"citation": "ENGINEERING_ONLY"},),
        review_status="PENDING_SCIENTIFIC_REVIEW" if pending else "COMPUTATIONALLY_REVIEWED",
        reviewer=None if pending else "ENGINEERING_ONLY_NOT_REAL_REVIEWER",
        reviewed_at=None if pending else "ENGINEERING_ONLY_NOT_REVIEW_TIMESTAMP",
        context={"mode": "other" if "context" in mutation else "fixture"})
    candidates = [models.CandidateSpec("control", "ENGINEERING control", intervention={"type": "none"})]
    if mutation != "controls_only":
        candidates.append(models.CandidateSpec("a", "ENGINEERING a", target="engineering-target",
                          intervention={"type": "activation"}, metadata={"mapping_id": "m",
                          "mapping_version": "1", "mapping_record_hash": mapping.record_hash}))
    study = models.StudySpec(name="ENGINEERING_ONLY", hypothesis="contract fixture",
        falsifiable_prediction="contract tuple", assay="engineering-assay", primary_metric="unused",
        candidates=tuple(candidates), backend="engineering-backend", study_id=f"engineering-{case['id']}",
        created_at="ENGINEERING_FIXED_TIME", metadata={"engineering_only": True,
        "dataset_id": "engineering-dataset", "id_namespace": "engineering-id", "context": {"mode": "fixture"}},
        run_plan={"backend_requirements": {"readout_ids": ["r"]}})
    capability = models.CapabilityDescriptor("engineering-backend", "ENGINEERING", True,
                        ("engineering-assay",), ("none", "activation"))
    mappings = {} if mutation in {"missing_mapping", "controls_only"} else {"m": mapping}
    assessment = support.assess_study_support(study, capability, mappings)
    assessment["backend_preflight"] = {"status": "READY", "provenance": "ENGINEERING_INPUT_NOT_EXECUTED"}
    assessment.pop("assessment_hash")
    assessment["assessment_hash"] = models.stable_hash(assessment)
    approval = None
    if mutation == "none":
        approval = {"schema_version": "support-approval-1", "study_id": study.study_id,
                    "study_configuration_hash": study.configuration_hash,
                    "assessment_hash": assessment["assessment_hash"], "status": "FROZEN_FOR_COMPUTATIONAL_RUN",
                    "reviewer": "ENGINEERING_ONLY_NOT_REAL_APPROVAL", "approved_at": "ENGINEERING_FIXED_TIME"}
    return {"study": study.as_dict(), "capability": capability.as_dict(),
            "mappings": [m.as_dict() for m in mappings.values()], "support": assessment, "approval": approval,
            "inventory": [{"candidate_id": c.candidate_id, "job_state": "NO_JOB_ENGINEERING_FIXTURE"}
                          for c in candidates], "context": {"mode": "fixture"},
            "decision": dp.pure_projection(assessment)}


def package(path, case=None):
    snapshots = fixture(case or LEDGER["cases"][0])
    path.mkdir()
    # v2 JSON contract; existing v2 writer is deliberately not imported.
    bundle = {"evidence_bundle_version": 2, "study_id": snapshots["study"]["study_id"],
              "generated_at": "ENGINEERING_FIXED_TIME", "status": "ENGINEERING_ONLY", "ai_policy": "none",
              "study": snapshots["study"], "decision_report": {}, "run_manifests": [], "dossiers": [],
              "review": {}, "limitations": ["ENGINEERING_ONLY"], "ranking_report": {}, "ranking_review": {},
              "confirmation_submission": {}, "confirmation_run": {}, "scientific_scope": "ENGINEERING_ONLY"}
    (path / "bundle.json").write_text(json.dumps(bundle), encoding="utf-8")
    dp.export_sidecar(path, snapshots, opt_in=True)
    return snapshots


def outcome(decision):
    candidate = decision["candidate_assessments"].get("a")
    assert decision["candidate_assessments"]["control"]["priority_eligible"] is False
    return [decision["status"], decision["run_allowed"], candidate["status"] if candidate else None,
            candidate["priority_eligible"] if candidate else False, sorted(candidate["reasons"]) if candidate else []]


def alter(path, object_id, change):
    manifest_path = path / dp.VERSION / "dependencies.json"
    manifest = json.loads(manifest_path.read_text())
    entry = next(e for e in manifest["objects"] if e["id"] == object_id)
    target = path / entry["path"]
    obj = json.loads(target.read_text())
    change(obj)
    data = dp._bytes(obj)
    target.write_bytes(data)
    entry.update(size=len(data), sha256=hashlib.sha256(data).hexdigest())
    manifest_path.write_bytes(dp._bytes(manifest))


def test_ledger_receipt():
    digest = hashlib.sha256(LEDGER_PATH.read_bytes()).hexdigest()
    assert digest in (LEDGER_PATH.parent / "TASK04_ORACLE_RECEIPT.txt").read_text()
    assert LEDGER["reviewer_status"] == "PENDING_INDEPENDENT_ENGINEERING_REVIEW"
    assert len({c["id"] for c in LEDGER["cases"]}) == 6
    assert all({"id", "family", "preconditions", "expected", "rationale", "expected_intermediates"} <= c.keys()
               for c in LEDGER["cases"])


@pytest.mark.parametrize("case", LEDGER["cases"], ids=lambda c: c["id"])
def test_isolated_slice(tmp_path, case):
    original = tmp_path / "original-workspace"
    snapshots = package(original, case)
    assert outcome(snapshots["decision"]) == case["expected"]
    portable = tmp_path / "portable"
    shutil.copytree(original, portable)
    trusted = tmp_path / "trusted-code"
    trusted.mkdir()
    for name in ("decision_package.py", "models.py", "support.py"):
        shutil.copyfile(CODE / name, trusted / name)
    shutil.rmtree(original)
    runner = tmp_path / "runner.py"
    runner.write_text('''import sys, pathlib, runpy, json, os
package, code = map(pathlib.Path, sys.argv[1:])
allowed = [package.resolve(), code.resolve(), pathlib.Path(sys.base_prefix).resolve()]
def audit(event, args):
    if event == "open":
        path = args[0]
        if isinstance(path, (str, bytes)):
            p = pathlib.Path(os.fsdecode(path)).resolve()
            if not any(p.is_relative_to(root) for root in allowed):
                raise RuntimeError("FORBIDDEN_READ:" + str(p))
    if event.startswith(("socket.", "subprocess.", "os.system", "os.spawn")):
        raise RuntimeError("FORBIDDEN_EXECUTION:" + event)
sys.addaudithook(audit)
module = runpy.run_path(str(code / "decision_package.py"), run_name="task04_isolated")
result = module["recompute"](package)
result["loaded_modules"] = sorted(name for name in sys.modules if name.startswith("_decision_pure_"))
print(json.dumps(result))
''', encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k.upper() not in {"PYTHONPATH", "PYTHONHOME"}}
    proc = subprocess.run([sys.executable, "-I", "-B", str(runner), str(portable), str(trusted)],
                          cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["status"] == "RECOMPUTED", result
    assert result["integrity_closure"] == "VALID"
    assert result["original_agreement"] is True
    assert result["operational_authority"] is False
    assert outcome(result["decision"]) == case["expected"]
    assert len(result["loaded_modules"]) == 3  # private namespace + models + support
    artifact_root = os.environ.get("TASK04_ARTIFACTS")
    if artifact_root:
        target = Path(artifact_root) / case["id"]
        target.mkdir(parents=True, exist_ok=False)
        shutil.copytree(portable, target / "package")
        (target / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")


@pytest.mark.parametrize("kind,reason", [
    ("missing", "MISSING_DEPENDENCY:"), ("tampered", "HASH_MISMATCH:"),
    ("version", "UNSUPPORTED_SIDECAR_VERSION"), ("policy", "POLICY_MISMATCH"),
    ("code", "CODE_MISMATCH"), ("environment", "ENVIRONMENT_MISMATCH"),
    ("approval", "APPROVAL_BINDING_MISMATCH"), ("traversal", "UNSAFE_PATH"),
    ("absolute", "UNSAFE_PATH"), ("workspace_only", "MISSING_DEPENDENCY:"),
    ("preflight", "UNSUPPORTED_PREFLIGHT"), ("cycle", "UNSUPPORTED_DEPENDENCY_GRAPH_OR_SCHEMA"),
    ("duplicate", "DUPLICATE_OBJECT"), ("inventory", "INVENTORY_MISMATCH"),
])
def test_failures(tmp_path, kind, reason):
    path = tmp_path / "package"
    package(path)
    mf = path / dp.VERSION / "dependencies.json"
    manifest = json.loads(mf.read_text())
    entry = next(e for e in manifest["objects"] if e["id"] == "context")
    if kind in {"missing", "workspace_only"}:
        if kind == "workspace_only":
            workspace = tmp_path / "original-workspace"
            workspace.mkdir()
            shutil.copy(path / entry["path"], workspace / "context.json")
        (path / entry["path"]).unlink()
    elif kind == "tampered":
        (path / entry["path"]).write_bytes(b"{}")
    elif kind == "version":
        manifest["version"] = "decision-recompute-999"
    elif kind in {"traversal", "absolute"}:
        entry["path"] = "../context.json" if kind == "traversal" else str(tmp_path / "context.json")
    elif kind == "cycle":
        entry["requires"] = ["context"]
    elif kind == "duplicate":
        manifest["objects"].append(dict(entry))
    else:
        edits = {
            "policy": ("policy", lambda o: o.update(version="unknown")),
            "code": ("identity", lambda o: o["code"].update({"support.py": "0" * 64})),
            "environment": ("identity", lambda o: o.update(python="0.0.0")),
            "approval": ("approval", lambda o: o.update(assessment_hash="0" * 64)),
            "preflight": ("support", lambda o: o["backend_preflight"].update(status="FAILED")),
            "inventory": ("inventory", lambda o: o.pop()),
        }
        obj, change = edits[kind]
        alter(path, obj, change)
    if kind in {"version", "traversal", "absolute", "cycle", "duplicate"}:
        mf.write_bytes(dp._bytes(manifest))
    result = dp.recompute(path)
    assert result["status"] == "NOT_RECONSTRUCTABLE"
    assert result["reason"].startswith(reason), result
    assert result["operational_authority"] is False


def test_legacy_opt_in_and_no_overwrite(tmp_path):
    path = tmp_path / "package"
    package(path)
    original_bytes = (path / "bundle.json").read_bytes()
    snapshots = fixture(LEDGER["cases"][0])
    with pytest.raises(FileExistsError):
        dp.export_sidecar(path, snapshots, opt_in=True)
    shutil.rmtree(path / dp.VERSION)
    assert dp.export_sidecar(path, snapshots) is None
    assert (path / "bundle.json").read_bytes() == original_bytes
    assert dp.recompute(path)["reason"] == "LEGACY_NO_SIDECAR"


def test_absent_approval_is_explicit_not_inferred(tmp_path):
    path = tmp_path / "package"
    package(path)
    mf = path / dp.VERSION / "dependencies.json"
    manifest = json.loads(mf.read_text())
    entry = next(e for e in manifest["objects"] if e["id"] == "approval")
    data = b"null\n"
    (path / entry["path"]).write_bytes(data)
    entry.update(size=len(data), sha256=hashlib.sha256(data).hexdigest())
    mf.write_bytes(dp._bytes(manifest))
    result = dp.recompute(path)
    assert result["status"] == "RECOMPUTED"
    assert result["approval_evidence_present"] is False
    assert result["operational_authority"] is False


def test_original_agreement_is_not_integrity(tmp_path):
    path = tmp_path / "package"
    package(path)
    models, _ = dp.pure_modules()
    def changed(report):
        report["status"] = "OUT_OF_SCOPE"
        report.pop("assessment_hash")
        report["assessment_hash"] = models.stable_hash(report)
    alter(path, "support", changed)
    mf = json.loads((path / dp.VERSION / "dependencies.json").read_text())
    entry = next(e for e in mf["objects"] if e["id"] == "support")
    report = json.loads((path / entry["path"]).read_text())
    alter(path, "decision", lambda o: o.update(dp.pure_projection(report)))
    alter(path, "approval", lambda o: o.update(assessment_hash=report["assessment_hash"]))
    result = dp.recompute(path)
    assert result["status"] == "RECOMPUTED"
    assert result["integrity_closure"] == "VALID"
    assert result["original_agreement"] is False