"""Provider-independent, context-scoped semantic response cache."""

from dataclasses import dataclass
import hashlib
import json
import logging
import math
import os
import re
import sqlite3
import threading
import time
from pathlib import Path
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
    cache_tier: str = "private"
    tenant_scope: str = ""


class ResponseCache:
    def __init__(self, ttl_seconds: int = RESPONSE_CACHE_TTL_SECONDS, max_entries: int = RESPONSE_CACHE_MAX_ENTRIES, semantic_threshold: float = RESPONSE_CACHE_SEMANTIC_THRESHOLD, clock: Callable[[], float] | None = None, persistence_path: str | None = None):
        self.ttl_seconds = max(1, int(ttl_seconds))
        self.max_entries = max(1, int(max_entries))
        self.semantic_threshold = max(0.0, min(1.0, float(semantic_threshold)))
        self._clock = clock or time.monotonic
        self._entries: dict[str, CacheEntry] = {}
        self._inflight: dict[str, threading.Event] = {}
        self._hits = self._misses = self._semantic_hits = self._semantic_misses = 0
        self._response_time_saved_ms = 0
        self._metrics: dict[tuple[str, str], dict[str, int]] = {}
        self._lock = threading.RLock()
        self._persistence_path = Path(persistence_path) if persistence_path else None
        if self._persistence_path:
            self._initialize_persistence()

    def _initialize_persistence(self) -> None:
        try:
            if not self._cache_cipher():
                logger.warning("CACHE persistence disabled because no encryption key is configured")
                self._persistence_path = None
                return
            self._persistence_path.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(self._persistence_path, timeout=10) as connection:
                connection.execute("CREATE TABLE IF NOT EXISTS response_cache (cache_key TEXT PRIMARY KEY, payload TEXT NOT NULL, created_at REAL NOT NULL DEFAULT 0)")
                columns = {row[1] for row in connection.execute("PRAGMA table_info(response_cache)").fetchall()}
                if "created_at" not in columns:
                    connection.execute("ALTER TABLE response_cache ADD COLUMN created_at REAL NOT NULL DEFAULT 0")
        except Exception:
            logger.exception("CACHE persistence initialization failed; using process memory only")
            self._persistence_path = None

    def _cache_cipher(self):
        secret = os.getenv("API_KEY_ENCRYPTION_KEY") or os.getenv("SECRET_KEY")
        if not secret:
            try:
                from app.core.config import settings
                secret = getattr(settings, "API_KEY_ENCRYPTION_KEY", None) or getattr(settings, "SECRET_KEY", None)
            except Exception:
                secret = None
        if not secret:
            return None
        try:
            import base64
            from cryptography.fernet import Fernet
            return Fernet(base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest()))
        except Exception:
            logger.exception("CACHE persistence encryption unavailable; using process memory only")
            return None

    def _encode_entry(self, entry: CacheEntry) -> str:
        payload = json.dumps({"content": entry.content, "provider": entry.provider, "model": entry.model, "created_at": entry.created_at, "provider_latency_ms": entry.provider_latency_ms, "optimization": entry.optimization, "normalized_query": entry.normalized_query, "embedding": list(entry.embedding), "context_key": entry.context_key, "cache_tier": entry.cache_tier, "tenant_scope": entry.tenant_scope}, ensure_ascii=False, default=str)
        cipher = self._cache_cipher()
        return cipher.encrypt(payload.encode()).decode() if cipher else payload

    def _decode_entry(self, payload: str) -> CacheEntry:
        cipher = self._cache_cipher()
        if cipher:
            payload = cipher.decrypt(payload.encode()).decode()
        value = json.loads(payload)
        return CacheEntry(value["content"], value["provider"], value["model"], float(value["created_at"]), int(value["provider_latency_ms"]), value["optimization"], value.get("normalized_query", ""), tuple(value.get("embedding", [])), value.get("context_key", ""), value.get("cache_tier", "private"), value.get("tenant_scope", ""))

    def _sync_persisted(self, now: float | None = None) -> None:
        if not self._persistence_path:
            return
        now = self._clock() if now is None else now
        try:
            with sqlite3.connect(self._persistence_path, timeout=10) as connection:
                rows = connection.execute("SELECT cache_key, payload FROM response_cache").fetchall()
                for key, payload in rows:
                    try:
                        entry = self._decode_entry(payload)
                    except Exception:
                        logger.warning("CACHE persistence entry ignored key_fingerprint=%s", key[:12])
                        continue
                    if now - entry.created_at >= self.ttl_seconds:
                        connection.execute("DELETE FROM response_cache WHERE cache_key = ?", (key,))
                        self._entries.pop(key, None)
                    else:
                        self._entries[key] = entry
        except Exception:
            logger.exception("CACHE persistence read failed; using process memory entries")

    def _persist_entry(self, key: str, entry: CacheEntry) -> None:
        if not self._persistence_path:
            return
        try:
            with sqlite3.connect(self._persistence_path, timeout=10) as connection:
                connection.execute("INSERT OR REPLACE INTO response_cache(cache_key, payload, created_at) VALUES (?, ?, ?)", (key, self._encode_entry(entry), entry.created_at))
                connection.execute("DELETE FROM response_cache WHERE cache_key IN (SELECT cache_key FROM response_cache ORDER BY created_at ASC LIMIT -1 OFFSET ?)", (self.max_entries,))
        except Exception:
            logger.exception("CACHE persistence write failed; response remains valid")

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

    def _metric(self, tier: str, tenant_scope: str) -> dict[str, int]:
        return self._metrics.setdefault((tier, tenant_scope), {"exact_hits": 0, "semantic_hits": 0, "semantic_misses": 0, "misses": 0, "tokens_saved": 0, "api_calls_avoided": 0})

    def _record(self, tier: str, tenant_scope: str, outcome: str, entry: CacheEntry | None = None) -> None:
        metric = self._metric(tier, tenant_scope)
        if outcome == "exact_hit": metric["exact_hits"] += 1
        elif outcome == "semantic_hit": metric["semantic_hits"] += 1
        elif outcome == "semantic_miss": metric["semantic_misses"] += 1
        elif outcome == "miss": metric["misses"] += 1
        if entry and outcome in {"exact_hit", "semantic_hit"}:
            metric["api_calls_avoided"] += 1
            metric["tokens_saved"] += max(0, int(entry.optimization.get("overall_optimized_tokens", entry.optimization.get("optimized_tokens", 0))))

    def lookup(self, key: str, *, semantic_query: str | None = None, context_key: str | None = None, cache_tier: str = "private", tenant_scope: str = "") -> CacheEntry | None:
        started = time.perf_counter()
        try:
            with self._lock:
                now = self._clock()
                self._sync_persisted(now)
                entry = self._entries.get(key)
                key_fingerprint = key[:12]
                elapsed = round(now - entry.created_at, 3) if entry else None
                expired = bool(entry and now - entry.created_at >= self.ttl_seconds)
                logger.info("CACHE_LOOKUP backend=memory instance=%s key_fingerprint=%s entry_exists=%s ttl_seconds=%s stored_at=%s elapsed_seconds=%s expired=%s", id(self), key_fingerprint, bool(entry), self.ttl_seconds, round(entry.created_at, 3) if entry else None, elapsed, expired)
                entry_in_scope = bool(entry and entry.cache_tier == cache_tier and entry.tenant_scope == tenant_scope)
                if entry and not entry_in_scope:
                    logger.info("CACHE_SCOPE_REJECTED key_fingerprint=%s requested_tier=%s requested_tenant=%s stored_tier=%s stored_tenant=%s", key_fingerprint, cache_tier, tenant_scope, entry.cache_tier, entry.tenant_scope)
                if entry_in_scope and now - entry.created_at < self.ttl_seconds:
                    self._hits += 1
                    self._record(cache_tier, tenant_scope, "exact_hit", entry)
                    self._response_time_saved_ms += max(0, entry.provider_latency_ms)
                    logger.info("%s_EXACT_HIT", cache_tier.upper())
                    logger.info("CACHE_HIT backend=memory key_fingerprint=%s lookup_ms=%s provider=%s model=%s", key_fingerprint, round((time.perf_counter() - started) * 1000, 2), entry.provider, entry.model)
                    return entry
                if entry and entry_in_scope:
                    self._entries.pop(key, None)
                    logger.info("CACHE_EXPIRED backend=memory key_fingerprint=%s", key_fingerprint)
                if semantic_query and context_key:
                    query_embedding = embedding_for(semantic_query)
                    best = None
                    best_score = 0.0
                    for candidate in self._entries.values():
                        if candidate.cache_tier != cache_tier or candidate.tenant_scope != tenant_scope:
                            continue
                        if candidate.context_key != context_key:
                            continue
                        if now - candidate.created_at >= self.ttl_seconds:
                            continue
                        score = cosine_similarity(query_embedding, candidate.embedding)
                        if score > best_score:
                            best, best_score = candidate, score
                    candidate_count = sum(1 for candidate in self._entries.values() if candidate.cache_tier == cache_tier and candidate.tenant_scope == tenant_scope and candidate.context_key == context_key and now - candidate.created_at < self.ttl_seconds)
                    if best and best_score >= self.semantic_threshold:
                        self._semantic_hits += 1
                        self._record(cache_tier, tenant_scope, "semantic_hit", best)
                        self._response_time_saved_ms += max(0, best.provider_latency_ms)
                        logger.info("%s_SEMANTIC_HIT", cache_tier.upper())
                        logger.info("SEMANTIC_CACHE_HIT query_fingerprint=%s context_fingerprint=%s candidate_count=%s similarity=%.4f threshold=%.4f lookup_ms=%s provider=%s model=%s", fingerprint(semantic_query), context_key[:12], candidate_count, best_score, self.semantic_threshold, round((time.perf_counter() - started) * 1000, 2), best.provider, best.model)
                        return best
                    self._semantic_misses += 1
                    self._record(cache_tier, tenant_scope, "semantic_miss")
                    logger.info("SEMANTIC_CACHE_MISS query_fingerprint=%s context_fingerprint=%s candidate_count=%s similarity=%.4f threshold=%.4f", fingerprint(semantic_query), context_key[:12], candidate_count, best_score, self.semantic_threshold)
                self._misses += 1
                self._record(cache_tier, tenant_scope, "miss")
                logger.info("%s_MISS", cache_tier.upper())
                logger.info("CACHE_MISS backend=memory key_fingerprint=%s lookup_ms=%s", key_fingerprint, round((time.perf_counter() - started) * 1000, 2))
                return None
        except Exception:
            logger.exception("CACHE ERROR during lookup; bypassing cache")
            return None

    def store(self, key: str, content: str, provider: str, model: str, provider_latency_ms: int, optimization: dict, *, semantic_query: str | None = None, context_key: str | None = None, cache_tier: str = "private", tenant_scope: str = "") -> bool:
        if not isinstance(content, str) or not content.strip():
            logger.info("CACHE BYPASS empty response")
            return False
        try:
            with self._lock:
                if len(self._entries) >= self.max_entries:
                    oldest_key = min(self._entries, key=lambda item: self._entries[item].created_at)
                    self._entries.pop(oldest_key, None)
                stored_at = self._clock()
                self._entries[key] = CacheEntry(content.strip(), provider, model, stored_at, max(0, int(provider_latency_ms)), dict(optimization), normalize_query(semantic_query or ""), embedding_for(semantic_query or ""), context_key or "", cache_tier, tenant_scope)
                stored = self._entries.get(key)
                self._persist_entry(key, stored)
                logger.info("CACHE_STORE backend=memory instance=%s key_fingerprint=%s context_fingerprint=%s provider=%s model=%s stored_at=%s ttl_seconds=%s stored=%s", id(self), key[:12], (context_key or "")[:12], provider, model, round(stored_at, 3), self.ttl_seconds, stored is not None)
                return stored is not None
        except Exception:
            logger.exception("CACHE ERROR during store; response remains valid")
            return False

    def invalidate(self, key: str) -> bool:
        with self._lock:
            removed = self._entries.pop(key, None) is not None
            if self._persistence_path:
                try:
                    with sqlite3.connect(self._persistence_path, timeout=10) as connection:
                        removed = connection.execute("DELETE FROM response_cache WHERE cache_key = ?", (key,)).rowcount > 0 or removed
                except Exception:
                    logger.exception("CACHE persistence invalidation failed")
            return removed

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._hits = self._misses = self._semantic_hits = self._semantic_misses = self._response_time_saved_ms = 0
            self._metrics.clear()
            if self._persistence_path:
                try:
                    with sqlite3.connect(self._persistence_path, timeout=10) as connection:
                        connection.execute("DELETE FROM response_cache")
                except Exception:
                    logger.exception("CACHE persistence clear failed")

    def tenant_stats(self, tenant_scope: str) -> dict[str, dict[str, int | float]]:
        with self._lock:
            self._sync_persisted()
            def result(tier: str):
                value = self._metrics.get((tier, tenant_scope), {})
                exact = int(value.get("exact_hits", 0)); semantic = int(value.get("semantic_hits", 0)); misses = int(value.get("misses", 0)); hits = exact + semantic
                entries = sum(1 for entry in self._entries.values() if entry.cache_tier == tier and entry.tenant_scope == tenant_scope)
                return {"hits": hits, "misses": misses, "semantic_misses": int(value.get("semantic_misses", 0)), "hit_rate": round(hits * 100 / (hits + misses), 2) if hits + misses else 0, "exact_hits": exact, "semantic_hits": semantic, "tokens_saved": int(value.get("tokens_saved", 0)), "api_calls_avoided": int(value.get("api_calls_avoided", 0)), "entries": entries, "size": entries, "ttl_seconds": self.ttl_seconds}
            global_stats = result("global"); private_stats = result("private")
            total_hits = global_stats["hits"] + private_stats["hits"]; total_misses = global_stats["misses"] + private_stats["misses"]
            return {"global_cache": global_stats, "private_cache": private_stats, "total_optimization": {"cache_hits": total_hits, "tokens_saved": global_stats["tokens_saved"] + private_stats["tokens_saved"], "api_calls_avoided": global_stats["api_calls_avoided"] + private_stats["api_calls_avoided"], "cache_hit_rate": round(total_hits * 100 / (total_hits + total_misses), 2) if total_hits + total_misses else 0}}

    def stats(self) -> dict[str, int | float]:
        with self._lock:
            self._sync_persisted()
            hits = self._hits + self._semantic_hits
            total = hits + self._misses
            return {"cache_hits": self._hits, "cache_misses": self._misses, "semantic_cache_hits": self._semantic_hits, "semantic_cache_misses": self._semantic_misses, "cache_hit_rate": round((hits / total) * 100, 2) if total else 0, "api_calls_avoided": hits, "average_response_time_saved_ms": round(self._response_time_saved_ms / hits, 2) if hits else 0, "response_time_saved_ms": self._response_time_saved_ms, "entries": len(self._entries)}


_default_cache_path = os.getenv("TOKENPILOT_RESPONSE_CACHE_PATH") or str(Path(__file__).resolve().parents[2] / ".cache" / "response_cache.sqlite3")
response_cache = ResponseCache(persistence_path=_default_cache_path)
