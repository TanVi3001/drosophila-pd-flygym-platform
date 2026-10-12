from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import run_ai_v2_review_gated_demo as demo


def _prepare_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(demo, "ROOT", tmp_path)
    return demo.prepare(tmp_path / ".workbench" / "ai-v2-e2e-demo" / "session")


def _complete_review_form(session: Path) -> dict:
    form_path = session / "human_review_form.json"
    form = json.loads(form_path.read_text(encoding="utf-8"))
    options = json.loads((session / "mapping_options.json").read_text(encoding="utf-8"))
    mapping = options["selectable_records"][0]
    form.update({
        "reviewer_id": "synthetic-test-reviewer",
        "decision": "ACCEPT_FOR_SYNTHETIC_DEMO_ONLY",
        "rationale": "Test-only synthetic workflow acceptance.",
        "mapping_choice": {
            "mapping_id": mapping["mapping_id"],
            "version": mapping["version"],
            "record_hash": mapping["record_hash"],
        },
        "acknowledgements": {
            "synthetic_fixture_only": True,
            "no_biological_claim": True,
            "study_spec_reviewed": True,
        },
    })
    form_path.write_text(json.dumps(form, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return form


def test_generated_review_form_finalizes_fixture_studyspec_without_approval_or_run(tmp_path, monkeypatch):
    session = _prepare_session(tmp_path, monkeypatch)
    form = _complete_review_form(session)

    assert set(form) == demo.REVIEW_FIELDS
    assert form["fixture_notice"] == demo.FIXTURE_NOTICE

    result = demo.finalize(session)

    assert result["status"] == "SYNTHETIC_STUDYSPEC_VALIDATED_AWAITING_RESEARCHER_APPROVAL"
    assert result["human_approval"] is False
    assert result["job_submitted"] is False
    assert result["simulation_run"] is False
    assert result["actual_llm_called"] is False
    assert result["heldout_status"] == "LOCKED_NOT_RUN"
    output = session / "finalized"
    assert json.loads((output / "support_assessment.json").read_text(encoding="utf-8"))["status"] == "READY_FOR_COMPUTATIONAL_REVIEW"
    assert json.loads((output / "human_review_record.json").read_text(encoding="utf-8"))["reviewer_id_self_reported"] == "synthetic-test-reviewer"
    assert not (output / "support_approval.json").exists()
    assert not list(output.rglob("*job*"))
    inventory = json.loads((output / "sha256.json").read_text(encoding="utf-8"))
    assert "synthetic_demo_state.sqlite3" in inventory
    assert not any(name.endswith(("-wal", "-shm")) for name in inventory)
    for relative_path, expected_hash in inventory.items():
        assert demo._sha256(output / relative_path) == expected_hash


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda form: form.update(fixture_notice="edited notice"), "fixture_notice does not match"),
        (lambda form: form.update(fixture_notice=42), "fixture_notice does not match"),
        (lambda form: form.update(unexpected_field="not allowed"), "missing or unsupported fields"),
    ],
)
def test_review_form_rejects_notice_changes_and_unknown_fields(tmp_path, monkeypatch, mutation, message):
    session = _prepare_session(tmp_path, monkeypatch)
    form = _complete_review_form(session)
    mutation(form)
    (session / "human_review_form.json").write_text(
        json.dumps(form, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    with pytest.raises(ValueError, match=message):
        demo.finalize(session)
    assert not (session / "finalized").exists()


def test_unconfirmed_synthetic_acknowledgement_still_blocks_finalize(tmp_path, monkeypatch):
    session = _prepare_session(tmp_path, monkeypatch)
    form = _complete_review_form(session)
    form["acknowledgements"]["no_biological_claim"] = False
    (session / "human_review_form.json").write_text(
        json.dumps(form, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    with pytest.raises(ValueError, match="all synthetic-scope acknowledgements must be true"):
        demo.finalize(session)
    assert not (session / "finalized").exists()
