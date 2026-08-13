from unittest.mock import patch

from app.providers.registry import GeminiProvider, configured_model


class FakeResponse:
    is_error = False

    def json(self):
        return {"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}


def test_gemini_provider_sends_one_http_request():
    with patch("app.providers.registry.httpx.post", return_value=FakeResponse()) as request:
        result = GeminiProvider().generate("valid-key", "gemini-2.5-flash", [{"role": "user", "content": "hello"}])

    assert result == "ok"
    assert request.call_count == 1
    assert "/models/gemini-3.6-flash:generateContent" in request.call_args.args[0]


def test_legacy_bare_gemini_model_is_normalized_centrally():
    assert configured_model("Gemini", "gemini") == "gemini-3.6-flash"
    assert configured_model("Gemini", "gemini-2.5-flash") == "gemini-3.6-flash"
