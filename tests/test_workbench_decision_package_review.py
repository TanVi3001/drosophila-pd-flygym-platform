"""Regressions from direct review; engineering checks, not a new gold ledger."""
import importlib.util
import json
import os
from pathlib import Path
import py_compile
import shutil
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "src/drosophila_pd/workbench"
spec = importlib.util.spec_from_file_location(
    "task05_review_fixture", ROOT / "tests/test_workbench_decision_package.py"
)
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
dp = fixture.dp


def trusted_copy(tmp_path, monkeypatch):
    for name in ("models.py", "support.py", "decision_package.py"):
        shutil.copyfile(CODE / name, tmp_path / name)
    monkeypatch.setattr(dp, "__file__", str(tmp_path / "decision_package.py"))
    return tmp_path / "support.py"


def test_loader_executes_hashed_source_not_timestamp_bytecode(tmp_path, monkeypatch):
    source = trusted_copy(tmp_path, monkeypatch)
    old_bytes = source.read_bytes() + b'\nREVIEW_BYTE_PROBE = "OLD"\n'
    source.write_bytes(old_bytes)
    stamp = source.stat()
    # Deliberately seed valid timestamp bytecode for the old equal-size source.
    py_compile.compile(str(source), doraise=True,
                       invalidation_mode=py_compile.PycInvalidationMode.TIMESTAMP)
    new_bytes = old_bytes.replace(b'REVIEW_BYTE_PROBE = "OLD"',
                                  b'REVIEW_BYTE_PROBE = "NEW"')
    assert len(old_bytes) == len(new_bytes)
    source.write_bytes(new_bytes)
    os.utime(source, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    _, support = dp.pure_modules()
    assert support.REVIEW_BYTE_PROBE == "NEW"


def test_failed_load_does_not_cache_partial_modules(tmp_path, monkeypatch):
    source = trusted_copy(tmp_path, monkeypatch)
    source.write_bytes(source.read_bytes() + b'\nraise ValueError("REVIEW_IMPORT_FAILURE")\n')
    before = set(sys.modules)
    for _ in range(2):
        with pytest.raises(ValueError, match="REVIEW_IMPORT_FAILURE"):
            dp.pure_modules()
        assert not {name for name in set(sys.modules) - before
                    if name.startswith("_decision_pure_")}


def test_export_distinct_roles_with_identical_json(tmp_path):
    path = tmp_path / "package"
    fixture.package(path, fixture.LEDGER["cases"][1])
    snapshots = fixture.fixture(fixture.LEDGER["cases"][1])
    # With no mapping, this context does not change the missing-mapping outcome.
    snapshots["context"] = {"version": dp.POLICY}
    shutil.rmtree(path / dp.VERSION)
    dp.export_sidecar(path, snapshots, opt_in=True)
    manifest = json.loads((path / dp.VERSION / "dependencies.json").read_text())
    entries = {e["id"]: e for e in manifest["objects"]}
    assert entries["context"]["sha256"] == entries["policy"]["sha256"]
    assert entries["context"]["path"] != entries["policy"]["path"]
    result = dp.recompute(path)
    assert result["status"] == "RECOMPUTED", result
    assert result["original_agreement"] is True


def test_export_rejects_mismatched_bundle_before_writing_sidecar(tmp_path):
    path = tmp_path / "package"
    fixture.package(path)
    shutil.rmtree(path / dp.VERSION)
    bundle_path = path / "bundle.json"
    bundle = json.loads(bundle_path.read_text())
    bundle["study_id"] = "WRONG_STUDY"
    bundle_path.write_text(json.dumps(bundle), encoding="utf-8")
    original = bundle_path.read_bytes()
    with pytest.raises(ValueError, match="BUNDLE_STUDY_MISMATCH"):
        dp.export_sidecar(path, fixture.fixture(fixture.LEDGER["cases"][0]), opt_in=True)
    assert bundle_path.read_bytes() == original
    assert not (path / dp.VERSION).exists()


def test_export_serialization_failure_does_not_leave_sidecar(tmp_path):
    path = tmp_path / "package"
    snapshots = fixture.package(path)
    shutil.rmtree(path / dp.VERSION)
    bundle_path = path / "bundle.json"
    original = bundle_path.read_bytes()
    # Keep the snapshots bound to the bundle so this reaches serialization,
    # rather than passing early because of an unrelated BUNDLE_STUDY_MISMATCH.
    snapshots["context"] = {"invalid_json": float("nan")}
    with pytest.raises(ValueError, match="Out of range float values"):
        dp.export_sidecar(path, snapshots, opt_in=True)
    assert bundle_path.read_bytes() == original
    assert not (path / dp.VERSION).exists()


def test_import_rejects_duplicate_paths(tmp_path):
    path = tmp_path / "package"
    fixture.package(path)
    manifest_path = path / dp.VERSION / "dependencies.json"
    manifest = json.loads(manifest_path.read_text())
    entries = {entry["id"]: entry for entry in manifest["objects"]}
    entries["context"]["path"] = entries["policy"]["path"]
    manifest_path.write_bytes(dp._bytes(manifest))
    result = dp.recompute(path)
    assert result["status"] == "NOT_RECONSTRUCTABLE"
    assert result["reason"] == "DUPLICATE_PATH"
    assert result["operational_authority"] is False
