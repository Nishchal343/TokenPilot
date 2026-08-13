from unittest.mock import Mock, patch

import pytest

from app.ai.routing import ProviderCandidate
from app.ai.service import ChatService
from app.cache import ResponseCache


class FakeProvider:
    def __init__(self):
        self.calls = 0

    def generate(self, api_key, model, messages):
        self.calls += 1
        return "shared pipeline response"


@pytest.mark.parametrize(
    "role,owner_id",
    [("company", 1), ("manager", 2), ("employee", 3)],
)
def test_all_chat_roles_use_the_same_optimizer_pipeline(role, owner_id):
    cache = ResponseCache()
    service = ChatService(cache=cache)
    provider = FakeProvider()
    selected = ProviderCandidate("openai", "gpt-4o-mini", "test-key", "personal", owner_id)

    prompt = Mock(wraps=service.prompt_optimizer.optimize)
    context_select = Mock(wraps=service.context_optimizer.select_context)
    context_compress = Mock(wraps=service.context_optimizer.compress_context)
    document = Mock(wraps=service.document_optimizer.optimize_document)
    code = Mock(wraps=service.code_optimizer.optimize_code)

    with patch.object(service.prompt_optimizer, "optimize", prompt), \
         patch.object(service.context_optimizer, "select_context", context_select), \
         patch.object(service.context_optimizer, "compress_context", context_compress), \
         patch.object(service.document_optimizer, "optimize_document", document), \
         patch.object(service.code_optimizer, "optimize_code", code), \
         patch("app.ai.service.provider_for", return_value=provider):
        result = service.generate(
            "Explain REST APIs in a detailed but concise way.",
            [],
            [],
            selected,
            [selected],
            cache_scope=f"{role}:{owner_id}",
            tenant_scope="company:1",
        )

    assert result.optimization["cache_status"] == "MISS"
    assert provider.calls == 1
    assert prompt.call_count == 1
    assert context_select.call_count == 2  # provider context and cache context
    assert context_compress.call_count == 2
    assert document.call_count == 1
    assert code.call_count == 1
    assert {"prompt", "context", "document", "code"} <= set(result.optimization["stages"])


@pytest.mark.parametrize(
    "role,owner_id",
    [("company", 1), ("manager", 2), ("employee", 3)],
)
def test_all_chat_roles_share_the_same_private_cache_behavior(role, owner_id):
    cache = ResponseCache()
    service = ChatService(cache=cache)
    provider = FakeProvider()
    selected = ProviderCandidate("openai", "gpt-4o-mini", "test-key", "personal", owner_id)
    scope = f"{role}:{owner_id}"

    with patch("app.ai.service.provider_for", return_value=provider):
        first = service.generate("Explain cache isolation.", [], [], selected, [selected], cache_scope=scope, tenant_scope="company:1")
        second = service.generate("Explain cache isolation.", [], [], selected, [selected], cache_scope=scope, tenant_scope="company:1")

    assert first.optimization["cache_status"] == "MISS"
    assert second.optimization["cache_status"] == "HIT"
    assert provider.calls == 1

