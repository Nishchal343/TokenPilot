from app.optimizers.context_optimizer import ContextOptimizer
from app.ai.routing import ProviderCandidate
from app.ai.service import ChatService
from unittest.mock import patch


def select(history, prompt, limit=1000, minimum=0):
    return ContextOptimizer(max_tokens=limit, minimum_messages=minimum, threshold=0.08).select_context(history, prompt, "openai", "gpt-4o-mini")


def test_short_conversation_preserves_context_in_order():
    history = [
        {"role": "user", "content": "Build an API endpoint."},
        {"role": "assistant", "content": "Which framework should we use?"},
    ]
    result = select(history, "Continue the API implementation.")
    assert result.messages == history
    assert result.messages_removed == 0


def test_long_history_removes_unrelated_topic_but_keeps_relevant_messages():
    history = [
        {"role": "user", "content": "How should the CSS layout handle mobile cards?"},
        {"role": "assistant", "content": "Use a responsive grid for the cards."},
        {"role": "user", "content": "Implement the API endpoint for JWT authentication."},
        {"role": "assistant", "content": "The JWT endpoint validates the bearer token."},
    ]
    result = select(history, "Continue the JWT API implementation.", limit=28)
    contents = [item["content"] for item in result.messages]
    assert any("JWT" in value for value in contents)
    assert result.messages_removed >= 1


def test_system_project_and_current_request_are_preserved():
    history = [
        {"role": "system", "content": "You are TokenPilot assistant."},
        {"role": "user", "content": "Project instructions: use Python and FastAPI.", "project_instruction": True},
        {"role": "user", "content": "Old unrelated greeting."},
    ]
    result = select(history, "Explain the FastAPI route.", limit=12)
    contents = [item["content"] for item in result.messages]
    assert "You are TokenPilot assistant." in contents
    assert "Project instructions: use Python and FastAPI." in contents


def test_code_and_document_context_receive_priority():
    history = [
        {"role": "user", "content": "The attached document describes the JWT API contract.", "attachments": [{"name": "api.pdf"}]},
        {"role": "assistant", "content": "The frontend color palette looks good."},
        {"role": "user", "content": "Here is the API code: ```python\nvalidate_jwt()\n```"},
    ]
    result = select(history, "Continue the JWT API code from the document.", limit=100)
    assert len(result.messages) == 3
    assert result.optimized_tokens <= result.original_tokens


def test_statistics_report_context_savings():
    history = [{"role": "user", "content": "Old unrelated content " * 20}]
    result = select(history, "A short new question.", limit=20)
    report = result.as_report("openai", "gpt-4o-mini")
    assert report["original_context_tokens"] >= report["optimized_context_tokens"]
    assert report["context_messages_removed"] == 1
    assert report["context_cost_saved"] >= 0


def test_chat_report_uses_overall_prompt_plus_context_totals():
    service = ChatService()
    service.context_optimizer = ContextOptimizer(max_tokens=20, minimum_messages=0, threshold=0.08)
    selected = ProviderCandidate("openai", "gpt-4o-mini", "test-key", "personal", 1)

    class FakeProvider:
        def generate(self, api_key, model, messages):
            assert len(messages) < 5
            return "done"

    history = [
        {"role": "user", "content": "Unrelated history " * 20},
        {"role": "assistant", "content": "More unrelated history " * 20},
    ]
    with patch("app.ai.service.provider_for", return_value=FakeProvider()):
        result = service.generate("Explain JWT", history, [], selected, [selected])

    report = result.optimization
    assert report["original_tokens"] == report["prompt_original_tokens"] + report["original_context_tokens"]
    assert report["optimized_tokens"] == report["prompt_optimized_tokens"] + report["optimized_context_tokens"]
    assert report["saved_tokens"] == report["prompt_tokens_saved"] + report["context_saved_tokens"]
    assert report["saved_tokens"] > report["prompt_tokens_saved"]
