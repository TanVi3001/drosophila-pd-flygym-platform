from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "run_guarded_heldout_evaluation.py"
SPEC = importlib.util.spec_from_file_location("guarded_heldout", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _protocol(path: Path, *, status: str = "PROPOSED_OWNER_APPROVAL_REQUIRED") -> Path:
    path.write_text(
        json.dumps(
            {
                "status": status,
                "owner_approval": {"status": "PENDING"},
                "evaluation": {"partition": "held_out"},
                "source_identity": {},
            }
        ),
        encoding="utf-8",
    )
    return path


def test_guard_refuses_without_explicit_approval_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HELDOUT_APPROVAL", raising=False)
    with pytest.raises(MODULE.GuardError, match="HELDOUT_APPROVAL"):
        MODULE.execute(
            protocol_path=tmp_path / "must-not-read.json",
            output=tmp_path / "new-output",
            expected_protocol_sha256="0" * 64,
            expected_source_commit="0" * 40,
            rewire_scores=tmp_path / "scores.csv",
        )
    assert not (tmp_path / "new-output").exists()


def test_guard_refuses_proposed_protocol_even_with_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    protocol = _protocol(tmp_path / "protocol.json")
    monkeypatch.setenv("HELDOUT_APPROVAL", "APPROVED")
    with pytest.raises(MODULE.GuardError, match="protocol SHA-256"):
        MODULE.execute(
            protocol_path=protocol,
            output=tmp_path / "new-output",
            expected_protocol_sha256="0" * 64,
            expected_source_commit="0" * 40,
            rewire_scores=tmp_path / "scores.csv",
        )
    with pytest.raises(MODULE.GuardError, match="OWNER_APPROVED"):
        MODULE.execute(
            protocol_path=protocol,
            output=tmp_path / "new-output",
            expected_protocol_sha256=MODULE._sha256(protocol),
            expected_source_commit="0" * 40,
            rewire_scores=tmp_path / "scores.csv",
        )
    assert not (tmp_path / "new-output").exists()


def test_heldout_template_has_pending_label_and_no_input_arguments() -> None:
    template = ROOT / "scripts" / "render_heldout_figure_template.py"
    text = template.read_text(encoding="utf-8")
    assert "PENDING ONE-TIME HELD-OUT EXECUTION" in text
    assert 'parser.add_argument("--output"' in text
    assert 'parser.add_argument("--metrics"' not in text
