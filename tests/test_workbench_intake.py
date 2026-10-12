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


@pytest.mark.parametrize("content", [
    '{"hypothesis":"first","hypothesis":"second"}',
    '{"context":{"sex":"female","sex":"male"}}',
    '{"name":NaN}', '{"name":Infinity}', '{"name":-Infinity}',
])
def test_provider_rejects_duplicate_keys_and_nonfinite_constants(monkeypatch, content):
    from drosophila_pd.workbench import intake

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, *_args):
            return json.dumps({"choices": [{"message": {"content": content}}]}).encode()

    monkeypatch.setattr(intake, "urlopen", lambda *_args, **_kwargs: Response())
    provider = intake.configured_intake_provider("http://localhost:9000", "stub")
    with pytest.raises(RuntimeError, match="not valid JSON object text"):
        provider.extract_with_evidence("Synthetic local protocol", evidence=[])


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


@pytest.mark.parametrize("field", ["hypothesis", "falsifiable_prediction", "assay", "primary_metric"])
def test_exact_missing_placeholder_is_absent_for_required_core_fields(field):
    raw = {
        "name": "fixture study",
        "hypothesis": "supported hypothesis",
        "falsifiable_prediction": "supported prediction",
        "assay": "fixture_assay",
        "primary_metric": "fixture_metric",
        "candidate_suggestions": [],
        "control_suggestions": [],
        "citations": [],
        "missing_fields": [field],
    }
    raw[field] = "missing"

    draft = create_intake_draft("A synthetic protocol.", Provider(raw))

    assert field not in draft["proposed_fields"]
    assert field in draft["missing_fields"]
    assert draft["approved"] is False
    assert draft["study_created"] is False
    assert draft["mapping_created"] is False


def test_core_empty_and_null_values_are_missing_without_inventing_replacements():
    raw = {
        "name": "fixture study",
        "hypothesis": None,
        "falsifiable_prediction": "",
        "assay": "  ",
        "primary_metric": "fixture_metric",
        "candidate_suggestions": [],
        "control_suggestions": [],
        "citations": [],
        "missing_fields": [],
    }

    draft = create_intake_draft("A synthetic protocol.", Provider(raw))

    assert draft["proposed_fields"] == {
        "name": "fixture study",
        "primary_metric": "fixture_metric",
        "candidate_suggestions": [],
        "control_suggestions": [],
        "citations": [],
    }
    assert set(draft["missing_fields"]) == {"hypothesis", "falsifiable_prediction", "assay"}


def test_valid_core_text_containing_missing_is_not_treated_as_placeholder():
    sentence = "The missing signal is predicted to reduce the fixture response."
    raw = {
        "hypothesis": sentence,
        "falsifiable_prediction": "The fixture response decreases.",
        "assay": "fixture_assay",
        "primary_metric": "fixture_metric",
        "candidate_suggestions": [],
        "control_suggestions": [],
        "citations": [],
        "missing_fields": [],
    }

    draft = create_intake_draft("A synthetic protocol.", Provider(raw))

    assert draft["proposed_fields"]["hypothesis"] == sentence
    assert draft["missing_fields"] == []


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

        def read(self, *_args):
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
    assert payload["response_format"]["type"] == "json_schema"
    assert payload["response_format"]["json_schema"]["schema"]["properties"]["context"]["type"] == "object"
    assert "protocol body" in payload["messages"][1]["content"]
    assert "Do not create or infer" in payload["messages"][0]["content"]
    assert result == {"hypothesis": "test"}


def test_openai_compatible_provider_requires_a_valid_pair_and_json_response():
    from drosophila_pd.workbench import intake

    with pytest.raises(ValueError, match="model"):
        intake.OpenAICompatibleIntakeProvider("https://llm.example/v1", " ")
    with pytest.raises(ValueError, match="HTTPS"):
        intake.OpenAICompatibleIntakeProvider("http://llm.example/v1", "small-model")

    provider = intake.OpenAICompatibleIntakeProvider("https://llm.example/v1", "small-model")
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, *_args):
            return b'{"choices": [{"message": {"content": "not-json"}}]}'

    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setattr(intake, "urlopen", lambda *_args, **_kwargs: Response())
        with pytest.raises(RuntimeError, match="valid JSON object"):
            provider.extract("protocol")
    finally:
        monkeypatch.undo()


def test_evidence_conditioned_provider_sends_only_explicit_chunks(monkeypatch):
    from drosophila_pd.workbench import intake

    captured = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, *_args):
            return json.dumps({"choices": [{"message": {"content": '{"hypothesis":"grounded draft"}'}}]}).encode()

    def fake_urlopen(request, *, timeout):
        captured["body"] = json.loads(request.data)
        return Response()

    monkeypatch.setattr(intake, "urlopen", fake_urlopen)
    provider = intake.OpenAICompatibleIntakeProvider("https://llm.example/v1", "small-model")
    result = provider.extract_with_evidence(
        "protocol question",
        evidence=[{"source_id": "SRC1", "chunk_id": "chunk1", "citation": "paper p. 2", "text": "approved excerpt"}],
    )

    payload = captured["body"]
    user_message = json.loads(payload["messages"][1]["content"])
    assert result == {"hypothesis": "grounded draft"}
    assert user_message["protocol_text"] == "protocol question"
    assert user_message["approved_evidence"][0]["text"] == "approved excerpt"
    assert "untrusted data" in payload["messages"][0]["content"]
    assert "Do not use outside knowledge" in payload["messages"][0]["content"]


def test_intake_provider_is_disabled_without_explicit_configuration():
    from drosophila_pd.workbench.intake import configured_intake_provider

    assert configured_intake_provider(None, None) is None
    with pytest.raises(ValueError, match="both"):
        configured_intake_provider("https://llm.example/v1", None)


@pytest.mark.parametrize("base_url", [
    "https://generativelanguage.googleapis.com/v1beta/openai",
    "https://generativelanguage.googleapis.com/v1beta/openai/",
    "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
])
def test_gemini_compatibility_request_uses_google_endpoint_and_selected_key(monkeypatch, base_url):
    """Transport contract only: no real Gemini call, account or quality claim."""
    from drosophila_pd.workbench import intake

    captured = {}
    result = {"name": "synthetic extraction draft", "missing_fields": ["hypothesis"]}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, *_args):
            return json.dumps({"choices": [{"message": {"content": json.dumps(result)}}]}).encode()

    def fake_urlopen(request, *, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr(intake, "urlopen", fake_urlopen)
    monkeypatch.setenv("WB_GEMINI_TEST_KEY", "fake-gemini-key-not-a-credential")
    monkeypatch.setenv("WORKBENCH_API_TOKEN", "different-staging-token")
    provider = intake.configured_intake_provider(
        base_url, "gemini-3.5-flash-lite", api_key_env="WB_GEMINI_TEST_KEY"
    )
    evidence = [{"source_id": "SYNTHETIC_GUIDE", "chunk_id": "fixture-001",
                 "citation": "Synthetic guide", "text": "Leave unspecified fields missing."}]
    assert provider.extract_with_evidence("Synthetic software protocol.", evidence=evidence) == result

    request = captured["request"]
    body = json.loads(request.data)
    assert request.full_url == "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
    assert request.get_method() == "POST"
    assert request.get_header("Authorization") == "Bearer fake-gemini-key-not-a-credential"
    assert provider.provider_id == "openai-compatible:gemini-3.5-flash-lite"
    assert captured["timeout"] == 60
    assert body["model"] == "gemini-3.5-flash-lite"
    assert body["temperature"] == 0
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["schema"]["additionalProperties"] is False
    assert "missing_fields" in body["response_format"]["json_schema"]["schema"]["required"]
    assert "tools" not in body  # No Google Search or other tool enabled.
    user_content = json.loads(body["messages"][1]["content"])
    assert user_content == {"protocol_text": "Synthetic software protocol.", "approved_evidence": evidence}
    assert "untrusted data" in body["messages"][0]["content"]


def test_provider_transport_disables_redirects(monkeypatch):
    from urllib.error import HTTPError
    from urllib.request import Request
    from drosophila_pd.workbench import intake

    seen = {}

    class Opener:
        def open(self, request, *, timeout):
            seen["request"] = request
            seen["timeout"] = timeout
            return "fixture response"

    def fake_build(handler):
        seen["handler"] = handler
        return Opener()

    monkeypatch.setattr(intake, "build_opener", fake_build)
    request = Request("https://provider.example/chat/completions")
    assert intake.urlopen(request, timeout=60) == "fixture response"
    assert seen["request"] is request and seen["timeout"] == 60
    with pytest.raises(HTTPError):
        seen["handler"].redirect_request(request, None, 302, "redirect", {}, "https://other.example")
