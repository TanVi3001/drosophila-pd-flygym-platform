from __future__ import annotations

import json

import pytest

from drosophila_pd.workbench.intake import create_intake_draft


class Provider:
    provider_id = "fixture-provider-v1"

    def __init__(self, response):
        self.response = response

    def extract(self, text, *, source_uri=None):
        return self.response


def test_intake_is_a_source_linked_draft_and_does_not_make_mappings():
    draft = create_intake_draft(
        "Activate sensory neurons and measure MN9 firing.",
        Provider(
            {
                "name": "sensory pilot",
                "hypothesis": "activation changes MN9 firing",
                "falsifiable_prediction": "MN9 rate changes",
                "assay": "sensory_mn9",
                "primary_metric": "mn9_rate",
                "candidate_suggestions": [{"target": "sugar_grns", "intervention": "activation"}],
                "citations": [{"citation": "paper", "locator": "Methods"}],
                "backend": "lif_2024",
                "mapping": {"neuron_ids": ["123"]},
            }
        ),
        source_uri="https://example.org/paper",
    )

    assert draft["status"] == "DRAFT_REQUIRES_RESEARCHER_REVIEW"
    assert draft["provider_id"] == "fixture-provider-v1"
    assert draft["source_uri"] == "https://example.org/paper"
    assert draft["source_sha256"]
    assert draft["proposed_fields"]["hypothesis"] == "activation changes MN9 firing"
    assert "backend" not in draft["proposed_fields"]
    assert "mapping" not in draft["proposed_fields"]
    assert "intervention" not in draft["proposed_fields"]["candidate_suggestions"][0]
    assert "mapping_generation_prohibited" in draft["guardrail_events"]


def test_intake_reports_missing_fields_and_rejects_non_object_provider_output():
    draft = create_intake_draft("A short protocol.", Provider({"name": "pilot"}))

    assert set(draft["missing_fields"]) == {
        "hypothesis",
        "falsifiable_prediction",
        "assay",
        "primary_metric",
    }
    assert draft["proposed_fields"] == {"name": "pilot"}

    try:
        create_intake_draft("protocol", Provider(["unexpected"]))
    except ValueError as error:
        assert "object" in str(error)
    else:
        raise AssertionError("non-object output should be rejected")


def test_intake_provider_failure_is_not_reported_as_a_draft():
    class BrokenProvider:
        provider_id = "broken"

        def extract(self, _text, *, source_uri=None):
            raise RuntimeError("provider unavailable")

    try:
        create_intake_draft("protocol", BrokenProvider())
    except RuntimeError as error:
        assert "provider unavailable" in str(error)
    else:
        raise AssertionError("provider failure was hidden")


def test_intake_sanitizes_nested_context_candidate_sources_and_controls():
    draft = create_intake_draft(
        "protocol",
        Provider(
            {
                "hypothesis": "h",
                "falsifiable_prediction": "p",
                "assay": "sensory_mn9",
                "primary_metric": "mn9_rate",
                "context": {
                    "sex": "female",
                    "stimulus": "sugar",
                    "mapping_id": "ai-mapping",
                    "readout_ids": ["123"],
                    "stimulus_rate_hz": 50,
                },
                "candidate_suggestions": [
                    {
                        "target": "sugar sensory cells",
                        "rationale": "described in the protocol",
                        "mapping": {"target_ids": ["123"]},
                        "sources": [{"citation": "paper", "neuron_ids": ["123"]}],
                    }
                ],
                "control_suggestions": [
                    {"label": "no stimulus", "rationale": "protocol control", "intervention": {"type": "none"}}
                ],
                "citations": [{"citation": "paper", "locator": "Table 1", "target_ids": ["123"]}],
            }
        ),
    )

    fields = draft["proposed_fields"]
    assert fields["context"] == {"sex": "female", "stimulus": "sugar"}
    assert fields["candidate_suggestions"] == [
        {
            "rationale": "described in the protocol",
            "sources": [{"citation": "paper"}],
            "target": "sugar sensory cells",
        }
    ]
    assert fields["control_suggestions"] == [{"label": "no stimulus", "rationale": "protocol control"}]
    assert fields["citations"] == [{"citation": "paper", "locator": "Table 1"}]
    assert "mapping_generation_prohibited" in draft["guardrail_events"]


def test_openai_compatible_provider_sends_guarded_json_request(monkeypatch):
    from drosophila_pd.workbench import intake

    captured = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps({"choices": [{"message": {"content": '{"hypothesis":"test"}'}}]}).encode()

    def fake_urlopen(request, *, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr(intake, "urlopen", fake_urlopen)
    monkeypatch.setenv("WB_TEST_TOKEN", "secret-token")
    provider = intake.OpenAICompatibleIntakeProvider(
        "https://llm.example/v1", "small-model", api_key_env="WB_TEST_TOKEN"
    )

    result = provider.extract("protocol body", source_uri="https://paper.example/methods")

    request = captured["request"]
    payload = json.loads(request.data)
    assert request.full_url == "https://llm.example/v1/chat/completions"
    assert request.get_header("Authorization") == "Bearer secret-token"
    assert captured["timeout"] == 60
    assert payload["response_format"] == {"type": "json_object"}
    assert "protocol body" in payload["messages"][1]["content"]
    assert "Do not create or infer" in payload["messages"][0]["content"]
    assert result == {"hypothesis": "test"}


def test_openai_compatible_provider_requires_a_valid_pair_and_json_response():
    from drosophila_pd.workbench import intake

    with pytest.raises(ValueError, match="model"):
        intake.OpenAICompatibleIntakeProvider("https://llm.example/v1", " ")

    provider = intake.OpenAICompatibleIntakeProvider("https://llm.example/v1", "small-model")
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b'{"choices": [{"message": {"content": "not-json"}}]}'

    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setattr(intake, "urlopen", lambda *_args, **_kwargs: Response())
        with pytest.raises(RuntimeError, match="valid JSON object"):
            provider.extract("protocol")
    finally:
        monkeypatch.undo()


def test_intake_provider_is_disabled_without_explicit_configuration():
    from drosophila_pd.workbench.intake import configured_intake_provider

    assert configured_intake_provider(None, None) is None
    with pytest.raises(ValueError, match="both"):
        configured_intake_provider("https://llm.example/v1", None)
