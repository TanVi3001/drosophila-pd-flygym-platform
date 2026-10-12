from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "ai_v2_step2_review", ROOT / "scripts" / "prepare_ai_v2_step2_review.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_review_proposal_uses_protocol_and_retrieved_excerpts_but_is_lexical_only():
    label, reason = MODULE.support_proposal(
        "fixture metric",
        "Protocol declares a condition.",
        [{"corpus_locator": "corpus.jsonl line 2", "text": "A fixture metric is listed."}],
    )
    assert label == "PROPOSED_DIRECT_TEXT_SUPPORT"
    assert "corpus.jsonl line 2" in reason
    assert "does not establish truth" in reason


def test_review_proposal_does_not_mark_paraphrase_as_supported():
    label, reason = MODULE.support_proposal(
        "The outcome changes",
        "A response differs.",
        [],
    )
    assert label == "PROPOSED_UNVERIFIABLE_OR_PARAPHRASED"
    assert "cannot establish contradiction" in reason


def test_field_display_distinguishes_absent_null_and_empty_string():
    assert MODULE.pretty(MODULE.ABSENT) == "<ABSENT>"
    assert MODULE.pretty(None) == "null"
    assert MODULE.pretty("") == '"" (empty string)'
