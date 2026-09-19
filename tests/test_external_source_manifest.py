from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "source_manifest.json"
REQUIRED_FIELDS = {
    "id",
    "role",
    "original_path",
    "source_url",
    "source_kind",
    "license_or_terms",
    "local_size_bytes",
    "local_sha256",
    "expected_filename",
    "download_notes",
    "verified_at",
}
EXTERNALIZED = {
    "data/flywire_annotations.tsv",
    "data/2025_Completeness_783.csv",
    "data/2025_Connectivity_783.parquet",
    "data/benchmarks/41586_2024_7763_MOESM2_ESM.xlsx",
}


def test_external_manifest_is_complete_and_network_free() -> None:
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))

    assert payload["schema_version"] == 1
    assert payload["entries"]
    assert "do not download" in payload["ci_policy"].lower()

    seen_paths: set[str] = set()
    for entry in payload["entries"]:
        assert REQUIRED_FIELDS <= entry.keys()
        assert entry["original_path"] not in seen_paths
        seen_paths.add(entry["original_path"])
        assert entry["source_url"].startswith("https://")
        assert isinstance(entry["local_size_bytes"], int)
        assert entry["local_size_bytes"] > 0
        digest = entry["local_sha256"]
        assert len(digest) == hashlib.sha256().digest_size * 2
        assert all(char in "0123456789abcdef" for char in digest)
        assert Path(entry["original_path"]).name == entry["expected_filename"]

    assert EXTERNALIZED <= seen_paths


def test_externalized_inputs_are_not_tracked() -> None:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    tracked = {
        item.decode("utf-8")
        for item in result.stdout.split(b"\0")
        if item
    }
    assert not (EXTERNALIZED & tracked)
