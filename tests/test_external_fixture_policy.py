from __future__ import annotations

from pathlib import Path
import sys

import pytest

import test_workbench_experimental_protocols as protocols


def _fixture_tree(root: Path) -> Path:
    repo_root = root / "drosophila-pd-flygym"
    neural_root = root / "drosophila-pd-neural-disease"
    model_root = root / "external" / "Drosophila_brain_model"
    (model_root).mkdir(parents=True)
    (neural_root / "annotations").mkdir(parents=True)
    (model_root / "2023_03_23_completeness_630_final.csv").write_text("id,complete\n1,True\n", encoding="utf-8")
    (model_root / "2023_03_23_connectivity_630_final.parquet").write_bytes(b"fixture")
    (neural_root / "annotations" / "flywire630_sensory_mn9_public.csv").write_text(
        "root_id\n1\n", encoding="utf-8"
    )
    return repo_root


def test_missing_external_lif_fixture_is_an_explicit_skip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root = tmp_path / "drosophila-pd-flygym"
    repo_root.mkdir()
    monkeypatch.setattr(protocols, "ROOT", repo_root)

    with pytest.raises(pytest.skip.Exception, match="external LIF fixtures"):
        protocols._lif_fixture_or_skip()


def test_complete_external_lif_fixture_uses_active_interpreter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = _fixture_tree(tmp_path)
    monkeypatch.setattr(protocols, "ROOT", repo_root)

    neural_root, model_root = protocols._lif_fixture_or_skip()

    assert neural_root == tmp_path / "drosophila-pd-neural-disease"
    assert model_root == tmp_path / "external" / "Drosophila_brain_model"
    assert Path(sys.executable).is_file()
