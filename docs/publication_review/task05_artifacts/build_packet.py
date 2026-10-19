"""Explicit review allowlist; never traverse scientific data or artifact trees."""
from pathlib import Path
import hashlib
import json
import subprocess
import zipfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
REVIEW = ROOT / "docs/publication_review"
ART = REVIEW / "task05_artifacts"
def digest(data):
    return hashlib.sha256(data).hexdigest()

files = {
    "AGENTS.md": "instructions",
    "pyproject.toml": "test configuration",
}
for name in ("TASK03_RELIABILITY_BUNDLE_SPEC.md", "TASK03_DECISIONS.md",
             "TASK04_IMPLEMENTATION_REPORT.md", "TASK04_CHECKPOINT.md",
             "TASK04_ORACLE_LEDGER.json", "TASK04_ORACLE_RECEIPT.txt",
             "TASK05_REVIEW_INTEGRATION_REPORT.md", "TASK05_CHECKPOINT.md"):
    files[f"docs/publication_review/{name}"] = "specification/oracle/review history"
for name in ("service", "decision_package", "models", "support", "store", "handoff",
             "adapters", "assays", "benchmark", "confirmation", "intake", "ranking", "selection"):
    files[f"src/drosophila_pd/workbench/{name}.py"] = "full call-path source or service import dependency; unrelated entry points not executed"
for name in ("test_workbench_decision_package.py", "test_workbench_support_package_integration.py"):
    files[f"tests/{name}"] = "targeted executable verification"
for run in (1, 2, 3):
    for name in ("pytest.xml", "exit.txt"):
        files[f"docs/publication_review/task05_artifacts/run-{run}/{name}"] = "retained verification receipt"
for name in ("S01-result.json", "S02-result.json", "S05-result.json"):
    files[f"docs/publication_review/task05_artifacts/run-3/{name}"] = "synthetic integrated result"
files["docs/publication_review/task05_artifacts/build_packet.py"] = "explicit allowlist builder"

summary = {"status": "COMPLETE_BOUNDED_ENGINEERING_SUBSET", "independent_review": "PENDING_INDEPENDENT_ENGINEERING_REVIEW",
           "oracle_revision": "task04-support-oracle-1", "runs": [],
           "integrated": {"cases": ["S01", "S02", "S05"], "oracle_agreement": "3/3",
                          "production_agreement": "3/3", "closure_valid": "3/3"},
           "limitations": ["not OS sandbox", "not full service regression", "preflight not replayed", "not independent reproduction"]}
for run in (1, 2, 3):
    suite = ET.parse(ART / f"run-{run}/pytest.xml").getroot().find("testsuite")
    summary["runs"].append(dict(run=run, **{k: int(suite.attrib[k]) for k in ("tests", "failures", "errors", "skipped")}))
assert summary["runs"][-1] == dict(run=3, tests=34, failures=0, errors=0, skipped=0)
assert digest((REVIEW / "TASK04_ORACLE_LEDGER.json").read_bytes()) == "f75cb973b5c577f1bc230c44c05e9f02958b2e0ebdc810a348c2ddf2d99eb034"
diff = subprocess.check_output(["git", "--no-pager", "-C", str(ROOT), "diff", "--", "src/drosophila_pd/workbench/service.py"])
(ART / "tracked-subset.diff").write_bytes(diff)
(ART / "verification-summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
files["docs/publication_review/task05_artifacts/tracked-subset.diff"] = "tracked changes only; new module/test supplied in full"
files["docs/publication_review/task05_artifacts/verification-summary.json"] = "machine-readable results"
manifest = {"kind": "SELF_REVIEW_PACKET_NOT_INDEPENDENT_REPRODUCTION", "root": str(ROOT),
            "head": subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip(),
            "files": []}
for path, role in sorted(files.items()):
    data = (ROOT / path).read_bytes()
    manifest["files"].append({"path": path, "sha256": digest(data), "size": len(data), "role": role})
manifest_bytes = (json.dumps(manifest, indent=2) + "\n").encode()
(ART / "manifest.json").write_bytes(manifest_bytes)
archive_path = REVIEW / "task05_review_packet.zip"
with zipfile.ZipFile(archive_path, "x", compression=zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(files):
        archive.write(ROOT / path, path)
    archive.writestr("manifest.json", manifest_bytes)
with zipfile.ZipFile(archive_path) as archive:
    assert archive.testzip() is None
    assert set(archive.namelist()) == set(files) | {"manifest.json"}
    for entry in manifest["files"]:
        assert digest(archive.read(entry["path"])) == entry["sha256"]
print(json.dumps({"archive": str(archive_path), "included_files": len(files), "crc_names_hashes": "PASS",
                  "sha256": digest(archive_path.read_bytes()), "runs": summary["runs"]}, indent=2))