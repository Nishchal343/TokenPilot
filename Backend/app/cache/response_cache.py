"""Provider-independent, context-scoped semantic response cache."""

from dataclasses import dataclass
import hashlib
import json
import logging
import math
import re
import threading
import time
from typing import Any, Callable

from app.config.optimization import RESPONSE_CACHE_MAX_ENTRIES, RESPONSE_CACHE_SEMANTIC_THRESHOLD, RESPONSE_CACHE_TTL_SECONDS

logger = logging.getLogger(__name__)
_STOP_WORDS = {"a", "an", "the", "me", "please", "about", "is", "are", "what", "tell", "explain", "simply", "simple", "can", "you", "and", "how", "it", "they", "their", "in", "terms", "purpose", "work"}
_SYNONYMS = {"apis": "api", "works": "work", "working": "work", "describe": "explain"}
_EMBEDDING_SIZE = 256


def fingerprint(value: Any) -> str:
    """Return a safe, deterministic identifier without exposing request data."""
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode()
    return hashlib.sha256(encoded).hexdigest()[:12]


def normalize_query(value: str) -> str:
    words = re.findall(r"[a-z0-9]+", str(value or "").lower())
    normalized = []
    for word in words:
        word = _SYNONYMS.get(word, word)
        if word not in _STOP_WORDS:
            normalized.append(word)
    return " ".join(normalized)


def embedding_for(value: str) -> tuple[float, ...]:
    """Deterministic local embedding; it never calls an AI provider."""
    normalized = normalize_query(value)
    vector = [0.0] * _EMBEDDING_SIZE
    features = normalized.split()
    features += [normalized[index:index + 3] for index in range(max(0, len(normalized) - 2))]
    for feature in features:
        digest = hashlib.blake2b(feature.encode(), digest_size=8).digest()
        index = int.from_bytes(digest, "big") % _EMBEDDING_SIZE
        vector[index] += 1.0
    magnitude = math.sqrt(sum(item * item for item in vector))
    return tuple(item / magnitude for item in vector) if magnitude else tuple(vector)


def cosine_similarity(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    return sum(a * b for a, b in zip(left, right))


@dataclass(frozen=True)
class CacheEntry:
    content: str
    provider: str
    model: str
    created_at: float
    provider_latency_ms: int
    optimization: dict
    normalized_query: str = ""
    embedding: tuple[float, ...] = ()
    context_key: str = ""


class ResponseCache:
    def __init__(self, ttl_seconds: int = RESPONSE_CACHE_TTL_SECONDS, max_entries: int = RESPONSE_CACHE_MAX_ENTRIES, semantic_threshold: float = RESPONSE_CACHE_SEMANTIC_THRESHOLD, clock: Callable[[], float] | None = None):
        self.ttl_seconds = max(1, int(ttl_seconds))
        self.max_entries = max(1, int(max_entries))
        self.semantic_threshold = max(0.0, min(1.0, float(semantic_threshold)))
        self._clock = clock or time.monotonic
        self._entries: dict[str, CacheEntry] = {}
        self._inflight: dict[str, threading.Event] = {}
        self._hits = self._misses = self._semantic_hits = self._semantic_misses = 0
        self._response_time_saved_ms = 0
        self._lock = threading.RLock()

    @staticmethod
    def context_key_for(*, context: list[dict], documents: Any, code: Any, provider: str, model: str, scope: str | None = None, images: list[dict] | None = None, system_prompt: str | None = None, generation_config: dict | None = None) -> str:
        payload = {"scope": scope, "context": context, "documents": documents or [], "code": code or [], "images": images or [], "provider": provider, "model": model, "system_prompt": system_prompt or "", "generation_config": generation_config or {}}
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode()).hexdigest()

    @staticmethod
    def key_for(*, optimized_prompt: str, context: list[dict], documents: Any, code: Any, provider: str, model: str, scope: str | None = None, images: list[dict] | None = None, system_prompt: str | None = None, generation_config: dict | None = None) -> str:
        context_key = ResponseCache.context_key_for(context=context, documents=documents, code=code, provider=provider, model=model, scope=scope, images=images, system_prompt=system_prompt, generation_config=generation_config)
        payload = {"context_key": context_key, "optimized_prompt": optimized_prompt}
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()

    def begin(self, key: str) -> tuple[bool, threading.Event]:
        with self._lock:
            event = self._inflight.get(key)
            if event:
                return False, event
            event = threading.Event()
            self._inflight[key] = event
            return True, event

    def finish(self, key: str) -> None:
        with self._lock:
            event = self._inflight.pop(key, None)
            if event:
                event.set()

    def lookup(self, key: str, *, semantic_query: str | None = None, context_key: str | None = None) -> CacheEntry | None:
        started = time.perf_counter()
        try:
            with self._lock:
                now = self._clock()
                entry = self._entries.get(key)
                key_fingerprint = key[:12]
                elapsed = round(now - entry.created_at, 3) if entry else None
                expired = bool(entry and now - entry.created_at >= self.ttl_seconds)
                logger.info("CACHE_LOOKUP backend=memory instance=%s key_fingerprint=%s entry_exists=%s ttl_seconds=%s stored_at=%s elapsed_seconds=%s expired=%s", id(self), key_fingerprint, bool(entry), self.ttl_seconds, round(entry.created_at, 3) if entry else None, elapsed, expired)
                if entry and now - entry.created_at < self.ttl_seconds:
                    self._hits += 1
                    self._response_time_saved_ms += max(0, entry.provider_latency_ms)
                    logger.info("CACHE_HIT backend=memory key_fingerprint=%s lookup_ms=%s provider=%s model=%s", key_fingerprint, round((time.perf_counter() - started) * 1000, 2), entry.provider, entry.model)
                    return entry
                if entry:
                    self._entries.pop(key, None)
                    logger.info("CACHE_EXPIRED backend=memory key_fingerprint=%s", key_fingerprint)
                if semantic_query and context_key:
                    query_embedding = embedding_for(semantic_query)
                    best = None
                    best_score = 0.0
                    for candidate in self._entries.values():
                        if candidate.context_key != context_key:
                            continue
                        if now - candidate.created_at >= self.ttl_seconds:
                            continue
                        score = cosine_similarity(query_embedding, candidate.embedding)
                        if score > best_score:
                            best, best_score = candidate, score
                    candidate_count = sum(1 for candidate in self._entries.values() if candidate.context_key == context_key and now - candidate.created_at < self.ttl_seconds)
                    if best and best_score >= self.semantic_threshold:
                        self._semantic_hits += 1
                        self._response_time_saved_ms += max(0, best.provider_latency_ms)
                        logger.info("SEMANTIC_CACHE_HIT query_fingerprint=%s context_fingerprint=%s candidate_count=%s similarity=%.4f threshold=%.4f lookup_ms=%s provider=%s model=%s", fingerprint(semantic_query), context_key[:12], candidate_count, best_score, self.semantic_threshold, round((time.perf_counter() - started) * 1000, 2), best.provider, best.model)
                        return best
                    self._semantic_misses += 1
                    logger.info("SEMANTIC_CACHE_MISS query_fingerprint=%s context_fingerprint=%s candidate_count=%s similarity=%.4f threshold=%.4f", fingerprint(semantic_query), context_key[:12], candidate_count, best_score, self.semantic_threshold)
                self._misses += 1
                logger.info("CACHE_MISS backend=memory key_fingerprint=%s lookup_ms=%s", key_fingerprint, round((time.perf_counter() - started) * 1000, 2))
                return None
        except Exception:
            logger.exception("CACHE ERROR during lookup; bypassing cache")
            return None

    def store(self, key: str, content: str, provider: str, model: str, provider_latency_ms: int, optimization: dict, *, semantic_query: str | None = None, context_key: str | None = None) -> bool:
        if not isinstance(content, str) or not content.strip():
            logger.info("CACHE BYPASS empty response")
            return False
        try:
            with self._lock:
                if len(self._entries) >= self.max_entries:
                    oldest_key = min(self._entries, key=lambda item: self._entries[item].created_at)
                    self._entries.pop(oldest_key, None)
                stored_at = self._clock()
                self._entries[key] = CacheEntry(content.strip(), provider, model, stored_at, max(0, int(provider_latency_ms)), dict(optimization), normalize_query(semantic_query or ""), embedding_for(semantic_query or ""), context_key or "")
                stored = self._entries.get(key)
                logger.info("CACHE_STORE backend=memory instance=%s key_fingerprint=%s context_fingerprint=%s provider=%s model=%s stored_at=%s ttl_seconds=%s stored=%s", id(self), key[:12], (context_key or "")[:12], provider, model, round(stored_at, 3), self.ttl_seconds, stored is not None)
                return stored is not None
        except Exception:
            logger.exception("CACHE ERROR during store; response remains valid")
            return False

    def invalidate(self, key: str) -> bool:
        with self._lock:
            return self._entries.pop(key, None) is not None

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._hits = self._misses = self._semantic_hits = self._semantic_misses = self._response_time_saved_ms = 0

    def stats(self) -> dict[str, int | float]:
        with self._lock:
            hits = self._hits + self._semantic_hits
            total = hits + self._misses
            return {"cache_hits": self._hits, "cache_misses": self._misses, "semantic_cache_hits": self._semantic_hits, "semantic_cache_misses": self._semantic_misses, "cache_hit_rate": round((hits / total) * 100, 2) if total else 0, "api_calls_avoided": hits, "average_response_time_saved_ms": round(self._response_time_saved_ms / hits, 2) if hits else 0, "response_time_saved_ms": self._response_time_saved_ms, "entries": len(self._entries)}


response_cache = ResponseCache()
