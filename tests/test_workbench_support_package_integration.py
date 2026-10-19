"""Task05: actual service/store/export with only synthetic offline state."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import types
from contextlib import contextmanager

import pytest

ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "src/drosophila_pd/workbench"
spec = importlib.util.spec_from_file_location("task05_fixture", ROOT / "tests/test_workbench_decision_package.py")
fixture_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture_module)
dp = fixture_module.dp
# Skip broad __init__, not service dependencies or service methods.
package = types.ModuleType("_task05_workbench")
package.__path__ = [str(CODE)]
sys.modules[package.__name__] = package
from _task05_workbench.service import WorkbenchService
from _task05_workbench.store import WorkbenchStore
from _task05_workbench.models import StudySpec, CapabilityDescriptor
from _task05_workbench.support import MappingRecord


def setup_service(root, case, monkeypatch, *, failed=False):
    snapshots = fixture_module.fixture(case)
    class Adapter:
        name = "engineering-backend"
        def describe(self):
            raw = dict(snapshots["capability"])
            raw.pop("scientific_scope")
            return CapabilityDescriptor(**raw)
        def validate(self, study, config):
            return ["ENGINEERING_FAILURE"] if failed else []
        def run(self, *args, **kwargs):
            pytest.fail("backend execution forbidden")
    class FixtureStore(WorkbenchStore):
        @contextmanager
        def _connect(self):
            connection = super()._connect()
            try:
                with connection:
                    yield connection
            finally:
                connection.close()
    store = FixtureStore(root / "state.sqlite3")
    service = WorkbenchService(store=store, artifact_root=root / "artifacts",
                               adapters={"engineering-backend": Adapter()})
    study = StudySpec.from_dict(snapshots["study"])
    service.create_study(study)
    for mapping in snapshots["mappings"]:
        service.register_mapping_record(MappingRecord.from_dict(mapping))
    def forbidden(*args, **kwargs):
        pytest.fail("operational mutation forbidden")
    for name in ("set_support_approval", "create_job"):
        monkeypatch.setattr(store, name, forbidden)
    monkeypatch.setattr(service, "submit_job", forbidden)
    return service, store, study


@pytest.mark.parametrize("case", fixture_module.LEDGER["cases"], ids=lambda c: c["id"])
def test_production_isolated_slice(tmp_path, monkeypatch, case):
    original = tmp_path / "original"
    service, store, study = setup_service(original, case, monkeypatch)
    target = original / "export"
    report = service.assess_support(study.study_id, required_context={"mode": "fixture"},
                                    decision_package_target=target)
    assert fixture_module.outcome(report) == case["expected"]
    assert store.get_support_approval(study.study_id) is None
    assert service.list_jobs(study_id=study.study_id) == []
    before = store.events("study", study.study_id)
    portable = tmp_path / "portable"
    shutil.copytree(target, portable)
    assert dp.recompute(portable)["original_agreement"]
    assert store.events("study", study.study_id) == before
    trusted = tmp_path / "trusted"
    trusted.mkdir()
    for name in ("decision_package.py", "models.py", "support.py"):
        shutil.copyfile(CODE / name, trusted / name)
    # Reuse the reviewed dependency guard verbatim, not the Task04 fixture path.
    source = (ROOT / "tests/test_workbench_decision_package.py").read_text(encoding="utf-8")
    runner_text = source.split("runner.write_text('''", 1)[1].split("''', encoding=", 1)[0]
    runner = tmp_path / "runner.py"
    runner.write_text(runner_text, encoding="utf-8")
    shutil.rmtree(original)
    proc = subprocess.run([sys.executable, "-I", "-B", str(runner), str(portable), str(trusted)],
                          cwd=tmp_path, capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["integrity_closure"] == "VALID"
    assert result["original_agreement"] is True
    assert result["operational_authority"] is False
    assert result["approval_evidence_present"] is False
    assert fixture_module.outcome(result["decision"]) == case["expected"]
    artifacts = os.environ.get("TASK05_ARTIFACTS")
    if artifacts:
        (Path(artifacts) / f"{case['id']}-result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")


def test_default_and_legacy_exports(tmp_path, monkeypatch):
    service, store, study = setup_service(tmp_path, fixture_module.LEDGER["cases"][0], monkeypatch)
    service.assess_support(study.study_id)
    directory = service.export_evidence_bundle(study.study_id, tmp_path / "legacy")
    assert not (directory / dp.VERSION).exists()
    assert dp.recompute(directory)["reason"] == "LEGACY_NO_SIDECAR"
    import zipfile
    archive = service.export_evidence_bundle(study.study_id, tmp_path / "legacy.zip")
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert json.loads(z.read("bundle.json"))["evidence_bundle_version"] == 2
        assert not any(dp.VERSION in name for name in z.namelist())


def test_failed_preflight_not_exported(tmp_path, monkeypatch):
    service, store, study = setup_service(tmp_path, fixture_module.LEDGER["cases"][0], monkeypatch, failed=True)
    target = tmp_path / "export"
    with pytest.raises(ValueError, match="UNSUPPORTED_PREFLIGHT"):
        service.assess_support(study.study_id, decision_package_target=target)
    assert not target.exists()
    assert store.get_support_assessment(study.study_id)["run_allowed"] is False
    assert store.get_support_approval(study.study_id) is None


def test_existing_target_not_overwritten(tmp_path, monkeypatch):
    service, store, study = setup_service(tmp_path, fixture_module.LEDGER["cases"][0], monkeypatch)
    target = tmp_path / "existing"
    target.mkdir()
    (target / "marker").write_text("preserve")
    with pytest.raises(ValueError, match="fresh directory"):
        service.assess_support(study.study_id, decision_package_target=target)
    assert (target / "marker").read_text() == "preserve"
    assert store.get_support_assessment(study.study_id) is None


def test_capability_binding(tmp_path):
    fixture_module.package(tmp_path / "package")
    fixture_module.alter(tmp_path / "package", "capability", lambda raw: raw.update(ready=False))
    assert dp.recompute(tmp_path / "package")["reason"] == "CAPABILITY_BINDING_MISMATCH"


def test_historical_approval_never_activates_store(tmp_path, monkeypatch):
    service, store, study = setup_service(tmp_path / "live-fixture", fixture_module.LEDGER["cases"][0], monkeypatch)
    before = store.events("study", study.study_id)
    fixture_module.package(tmp_path / "historical-package")
    result = dp.recompute(tmp_path / "historical-package")
    assert result["approval_evidence_present"] is True
    assert result["operational_authority"] is False
    assert store.get_support_approval(study.study_id) is None
    assert service.list_jobs(study_id=study.study_id) == []
    assert store.events("study", study.study_id) == before


def test_context_input_mismatch_is_not_integrity_failure(tmp_path):
    fixture_module.package(tmp_path / "package")
    fixture_module.alter(tmp_path / "package", "context", lambda raw: raw.update(mode="other"))
    result = dp.recompute(tmp_path / "package")
    assert result["integrity_closure"] == "VALID"
    assert result["original_agreement"] is False


def test_loader_identity_changes_with_source_bytes(tmp_path, monkeypatch):
    for name in ("models.py", "support.py"):
        shutil.copyfile(CODE / name, tmp_path / name)
    monkeypatch.setattr(dp, "__file__", str(tmp_path / "decision_package.py"))
    first = dp.pure_modules()
    with (tmp_path / "support.py").open("a", encoding="utf-8") as handle:
        handle.write("\n# engineering identity test\n")
    second = dp.pure_modules()
    assert first[1] is not second[1]
