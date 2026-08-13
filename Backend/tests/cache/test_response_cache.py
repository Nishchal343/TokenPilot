from app.cache.response_cache import ResponseCache
from app.ai.routing import ProviderCandidate
from app.ai.service import ChatService
from app.providers.registry import ProviderRequestError
from fastapi import HTTPException
from unittest.mock import patch


def make_key(cache, prompt="hello", provider="openai", model="gpt-4o-mini"):
    return cache.key_for(optimized_prompt=prompt, context=[], documents=[], code=[], provider=provider, model=model)


def test_successful_response_is_reused_and_stats_are_recorded():
    cache = ResponseCache(ttl_seconds=60)
    key = make_key(cache)
    assert cache.lookup(key) is None
    assert cache.store(key, "real provider response", "openai", "gpt-4o-mini", 120, {"cache_status": "MISS"})
    entry = cache.lookup(key)
    assert entry is not None
    assert entry.content == "real provider response"
    assert cache.stats()["cache_hits"] == 1
    assert cache.stats()["cache_misses"] == 1
    assert cache.stats()["api_calls_avoided"] == 1
    assert cache.stats()["average_response_time_saved_ms"] == 120


def test_empty_response_is_never_cached():
    cache = ResponseCache()
    key = make_key(cache)
    assert cache.store(key, "   ", "openai", "gpt-4o-mini", 120, {}) is False
    assert cache.lookup(key) is None


def test_provider_and_model_are_part_of_cache_key():
    cache = ResponseCache()
    assert make_key(cache, provider="openai") != make_key(cache, provider="gemini")
    assert make_key(cache, model="gpt-4o-mini") != make_key(cache, model="gemini-2.5-pro")


def test_global_and_private_metrics_are_separated_by_tenant():
    cache = ResponseCache()
    global_key = make_key(cache, prompt="shared", provider="openai")
    private_key = make_key(cache, prompt="private", provider="openai")
    cache.store(global_key, "shared response", "openai", "gpt-4o-mini", 100, {"optimized_tokens": 12}, cache_tier="global", tenant_scope="company:1")
    cache.store(private_key, "private response", "openai", "gpt-4o-mini", 100, {"optimized_tokens": 8}, cache_tier="private", tenant_scope="company:1")
    assert cache.lookup(global_key, cache_tier="global", tenant_scope="company:1")
    assert cache.lookup(private_key, cache_tier="private", tenant_scope="company:1")

    stats = cache.tenant_stats("company:1")
    assert stats["global_cache"]["exact_hits"] == 1
    assert stats["global_cache"]["tokens_saved"] == 12
    assert stats["private_cache"]["exact_hits"] == 1
    assert stats["private_cache"]["tokens_saved"] == 8
    assert cache.tenant_stats("company:2")["total_optimization"]["cache_hits"] == 0


def test_lookup_rejects_wrong_tier_or_tenant_even_when_key_matches():
    cache = ResponseCache()
    key = make_key(cache, prompt="scoped")
    context_key = cache.context_key_for(context=[], documents=[], code=[], provider="openai", model="gpt-4o-mini", scope="company:1")
    cache.store(key, "company one answer", "openai", "gpt-4o-mini", 80, {}, semantic_query="scoped", context_key=context_key, cache_tier="global", tenant_scope="company:1")

    assert cache.lookup(key, semantic_query="scoped", context_key=context_key, cache_tier="global", tenant_scope="company:2") is None
    assert cache.lookup(key, semantic_query="scoped", context_key=context_key, cache_tier="private", tenant_scope="company:1") is None


def test_semantically_normalized_query_reuses_a_context_scoped_entry():
    cache = ResponseCache(semantic_threshold=0.92)
    context_key = cache.context_key_for(context=[], documents=[], code=[], provider="openai", model="gpt-4o-mini", scope="company:1")
    first_key = make_key(cache, prompt="Describe caching", provider="openai", model="gpt-4o-mini")
    assert cache.store(first_key, "real provider response", "openai", "gpt-4o-mini", 80, {}, semantic_query="Describe caching", context_key=context_key)

    second_key = make_key(cache, prompt="Explain caching", provider="openai", model="gpt-4o-mini")
    entry = cache.lookup(second_key, semantic_query="Explain caching", context_key=context_key)

    assert entry is not None
    assert entry.content == "real provider response"
    assert cache.stats()["semantic_cache_hits"] == 1


def test_rest_api_semantic_variant_hits_without_lowering_the_threshold():
    cache = ResponseCache(semantic_threshold=0.92)
    context_key = cache.context_key_for(context=[], documents=[], code=[], provider="openai", model="gpt-4o-mini", scope="employee:7")
    first_key = make_key(cache, prompt="Explain what a REST API is and how it works.")
    cache.store(first_key, "REST API response", "openai", "gpt-4o-mini", 50, {}, semantic_query="Explain what a REST API is and how it works.", context_key=context_key)

    assert cache.lookup("semantic-rest-api-key", semantic_query="Tell me about REST APIs and how they work.", context_key=context_key) is not None


def test_semantic_rest_api_paraphrases_reuse_one_provider_response_with_chat_history():
    cache = ResponseCache(semantic_threshold=0.92)
    service = ChatService(cache=cache)
    selected = ProviderCandidate("openai", "gpt-4o-mini", "test-key", "personal", 1)
    calls = []

    class FakeProvider:
        def generate(self, api_key, model, messages):
            calls.append(messages)
            return "A REST API lets systems communicate over HTTP."

    questions = [
        "Explain what a REST API is and how it works.",
        "Tell me about REST APIs and how they work.",
        "What is a REST API? Explain it in simple terms.",
        "Can you explain REST APIs and their purpose?",
        "Explain how database indexing works.",
    ]
    history = []
    results = []
    with patch("app.ai.service.provider_for", return_value=FakeProvider()):
        for question in questions:
            result = service.generate(question, history, [], selected, [selected], cache_scope="employee:7")
            results.append(result)
            history.extend([
                {"role": "user", "content": question, "images": []},
                {"role": "assistant", "content": result.content, "images": []},
            ])

    assert [result.optimization["cache_status"] for result in results] == ["MISS", "HIT", "HIT", "HIT", "MISS"]
    assert len(calls) == 2


def test_semantic_cache_never_crosses_a_scope_or_context_boundary():
    cache = ResponseCache()
    company_one = cache.context_key_for(context=[], documents=[], code=[], provider="openai", model="gpt-4o-mini", scope="company:1")
    company_two = cache.context_key_for(context=[], documents=[], code=[], provider="openai", model="gpt-4o-mini", scope="company:2")
    key = make_key(cache, prompt="Explain caching")
    cache.store(key, "company one answer", "openai", "gpt-4o-mini", 80, {}, semantic_query="Explain caching", context_key=company_one)

    assert cache.lookup("another-key", semantic_query="Describe caching", context_key=company_two) is None


def test_expired_entries_are_misses():
    now = [100.0]
    cache = ResponseCache(ttl_seconds=10, clock=lambda: now[0])
    key = make_key(cache)
    cache.store(key, "response", "openai", "gpt-4o-mini", 50, {})
    now[0] = 111.0
    assert cache.lookup(key) is None
    assert cache.stats()["cache_misses"] == 1


def test_chat_service_skips_provider_on_repeated_optimized_request():
    cache = ResponseCache(ttl_seconds=60)
    service = ChatService(cache=cache)
    selected = ProviderCandidate("openai", "gpt-4o-mini", "test-key", "personal", 1)
    calls = []

    class FakeProvider:
        def generate(self, api_key, model, messages):
            calls.append((api_key, model, messages))
            return "real AI response"

    with patch("app.ai.service.provider_for", return_value=FakeProvider()):
        first = service.generate("Explain caching", [], [], selected, [selected])
        second = service.generate("Explain caching", [], [], selected, [selected])

    assert len(calls) == 1
    assert first.optimization["cache_status"] == "MISS"
    assert second.optimization["cache_status"] == "HIT"
    assert second.content == first.content


def test_chat_service_reuses_exact_message_after_its_completed_turn_is_in_history():
    """Matches the real endpoint, which persists the first user/assistant turn."""
    cache = ResponseCache(ttl_seconds=60)
    service = ChatService(cache=cache)
    selected = ProviderCandidate("openai", "gpt-4o-mini", "test-key", "personal", 1)
    calls = []

    class FakeProvider:
        def generate(self, api_key, model, messages):
            calls.append(messages)
            return "A REST API is an interface."

    prompt = "Explain what a REST API is and how it works."
    with patch("app.ai.service.provider_for", return_value=FakeProvider()):
        first = service.generate(prompt, [], [], selected, [selected], cache_scope="employee:7")
        second = service.generate(prompt, [
            {"role": "user", "content": prompt, "images": []},
            {"role": "assistant", "content": first.content, "images": []},
        ], [], selected, [selected], cache_scope="employee:7")

    assert len(calls) == 1
    assert first.optimization["cache_status"] == "MISS"
    assert second.optimization["cache_status"] == "HIT"
    assert second.content == first.content


def test_chat_service_reuses_exact_message_after_multiple_consecutive_retries():
    cache = ResponseCache(ttl_seconds=60)
    service = ChatService(cache=cache)
    selected = ProviderCandidate("openai", "gpt-4o-mini", "test-key", "personal", 1)
    calls = []

    class FakeProvider:
        def generate(self, api_key, model, messages):
            calls.append(messages)
            return "repeatable response"

    prompt = "Explain what a REST API is and how it works."
    retry_history = [
        {"role": "user", "content": "Earlier question", "images": []},
        {"role": "assistant", "content": "Earlier answer", "images": []},
    ]
    with patch("app.ai.service.provider_for", return_value=FakeProvider()):
        first = service.generate(prompt, retry_history, [], selected, [selected], cache_scope="employee:7")
        repeated_history = retry_history + [
            {"role": "user", "content": prompt, "images": []},
            {"role": "assistant", "content": first.content, "images": []},
            {"role": "user", "content": prompt, "images": []},
            {"role": "assistant", "content": first.content, "images": []},
        ]
        third = service.generate(prompt, repeated_history, [], selected, [selected], cache_scope="employee:7")

    assert len(calls) == 1
    assert third.optimization["cache_status"] == "HIT"


def test_self_contained_retries_stay_cacheable_across_five_turns():
    cache = ResponseCache(ttl_seconds=60)
    service = ChatService(cache=cache)
    selected = ProviderCandidate("openai", "gpt-4o-mini", "test-key", "personal", 1)
    calls = []

    class FakeProvider:
        def generate(self, api_key, model, messages):
            calls.append(messages)
            return "stable response"

    history = []
    with patch("app.ai.service.provider_for", return_value=FakeProvider()):
        results = []
        for _ in range(5):
            result = service.generate("Explain what a REST API is and how it works.", history, [], selected, [selected], cache_scope="employee:7")
            results.append(result)
            history.extend([
                {"role": "user", "content": "Explain what a REST API is and how it works.", "images": []},
                {"role": "assistant", "content": result.content, "images": []},
            ])

    assert [result.optimization["cache_status"] for result in results] == ["MISS", "HIT", "HIT", "HIT", "HIT"]
    assert len(calls) == 1


def test_context_dependent_retries_keep_conversation_in_cache_identity():
    cache = ResponseCache(ttl_seconds=60)
    service = ChatService(cache=cache)
    selected = ProviderCandidate("openai", "gpt-4o-mini", "test-key", "personal", 1)
    calls = []

    class FakeProvider:
        def generate(self, api_key, model, messages):
            calls.append(messages)
            return f"response {len(calls)}"

    history = [{"role": "user", "content": "What is a binary tree?", "images": []}, {"role": "assistant", "content": "A tree.", "images": []}]
    prompt = "What are its advantages?"
    with patch("app.ai.service.provider_for", return_value=FakeProvider()):
        first = service.generate(prompt, history, [], selected, [selected], cache_scope="employee:7")
        repeated_history = history + [{"role": "user", "content": prompt, "images": []}, {"role": "assistant", "content": first.content, "images": []}]
        second = service.generate(prompt, repeated_history, [], selected, [selected], cache_scope="employee:7")

    assert first.optimization["cache_status"] == "MISS"
    assert second.optimization["cache_status"] == "MISS"
    assert len(calls) == 2


def test_cache_miss_makes_only_one_provider_attempt_even_with_fallbacks():
    cache = ResponseCache(ttl_seconds=60)
    service = ChatService(cache=cache)
    selected = ProviderCandidate("openai", "gpt-4o-mini", "first-key", "personal", 1)
    fallback = ProviderCandidate("gemini", "gemini-2.5-flash", "second-key", "personal", 2)
    calls = []

    class FailingProvider:
        def generate(self, api_key, model, messages):
            calls.append((api_key, model))
            raise ProviderRequestError("provider", 429, model=model)

    with patch("app.ai.service.provider_for", return_value=FailingProvider()):
        try:
            service.generate("one request", [], [], selected, [selected, fallback])
        except HTTPException as exc:
            assert exc.status_code == 502
        else:
            raise AssertionError("Expected provider failure")

    assert calls == [("first-key", "gpt-4o-mini")]


def test_cache_failure_bypasses_cache_and_still_returns_provider_response():
    class BrokenCache:
        def context_key_for(self, **kwargs):
            raise RuntimeError("cache unavailable")

    service = ChatService(cache=BrokenCache())
    selected = ProviderCandidate("openai", "gpt-4o-mini", "test-key", "personal", 1)

    class FakeProvider:
        def generate(self, api_key, model, messages):
            return "provider response"

    with patch("app.ai.service.provider_for", return_value=FakeProvider()):
        result = service.generate("Explain cache failures", [], [], selected, [selected])

    assert result.content == "provider response"
