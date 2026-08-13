from dataclasses import dataclass
import logging
import re
import time
import uuid

from fastapi import HTTPException

from app.ai.classifier import RequestClassifier
from app.ai.routing import ProviderCandidate, ProviderRouter
from app.cache import ResponseCache, response_cache
from app.cache.response_cache import fingerprint
from app.optimizers import CodeOptimizer, ContextOptimizer, DocumentOptimizer, PromptOptimizer
from app.providers.registry import ProviderRequestError, provider_for

logger = logging.getLogger(__name__)
_CONTEXT_DEPENDENT_PROMPT = re.compile(r"\b(above|previous|earlier|continue|again|also|same|that|this|its)\b", re.IGNORECASE)


def _api_key_fingerprint(secret: str) -> str:
    if not secret:
        return "<missing>"
    return f"{secret[:8]}...{secret[-4:]}"


@dataclass(frozen=True)
class AIResult:
    content: str
    provider: str
    model: str
    request_id: str
    complexity: str
    confidence: float
    estimated_tokens: int
    latency_ms: int
    optimization: dict


class ChatService:
    def __init__(self, cache: ResponseCache | None = None):
        self.classifier = RequestClassifier()
        self.router = ProviderRouter()
        self.prompt_optimizer = PromptOptimizer()
        self.context_optimizer = ContextOptimizer()
        self.document_optimizer = DocumentOptimizer()
        self.code_optimizer = CodeOptimizer()
        self.cache = cache or response_cache

    @staticmethod
    def _cache_history(history: list[dict], current_prompt: str) -> tuple[list[dict], int]:
        """Ignore only the completed turn created by an identical retry.

        The provider still receives the complete optimized context. This affects
        only cache identity so sending the exact same message twice can reuse
        its first answer without weakening tenant or prior-context isolation.
        """
        result = list(history)
        removed = 0
        if not ChatService._is_self_contained_prompt(current_prompt):
            return result, removed
        while len(result) >= 2 and result[-2].get("role") == "user" and result[-1].get("role") == "assistant" and str(result[-2].get("content", "")).strip() == current_prompt.strip():
            result = result[:-2]
            removed += 1
        return result, removed

    @staticmethod
    def _is_self_contained_prompt(prompt: str) -> bool:
        """Standalone questions can safely reuse a tenant-scoped semantic answer."""
        return not bool(_CONTEXT_DEPENDENT_PROMPT.search(prompt or ""))

    def _build_report(self, optimization, context, document, code, provider: str, model: str, request_id: str) -> dict:
        report = optimization.as_report(provider, model)
        context_report = context.as_report(provider, model)
        report.update({key: value for key, value in context_report.items() if key != "stages"})
        report["stages"].update(context_report["stages"])
        report["context_messages_removed"] = context.messages_removed
        report["context_messages_preserved"] = context.messages_preserved
        report["context_optimization_ms"] = context.optimization_ms
        report["context_request_id"] = request_id
        code_report = code.as_report(provider, model)
        report.update({key: value for key, value in code_report.items() if key != "stages"})
        report["stages"].update(code_report["stages"])
        document_report = document.as_report(provider, model)
        report.update({key: value for key, value in document_report.items() if key != "stages"})
        report["stages"].update(document_report["stages"])
        report["prompt_original_tokens"] = report["original_tokens"]
        report["prompt_optimized_tokens"] = report["optimized_tokens"]
        report["prompt_tokens_saved"] = report["saved_tokens"]
        report["prompt_cost_before"] = report["cost_before"]
        report["prompt_cost_after"] = report["cost_after"]
        report["prompt_cost_saved"] = report["cost_saved"]
        for prefix in ("document", "code"):
            report[f"{prefix}_original_tokens"] = int(report.get(f"{prefix}_original_tokens", 0))
            report[f"{prefix}_optimized_tokens"] = int(report.get(f"{prefix}_optimized_tokens", 0))
            report[f"{prefix}_tokens_saved"] = int(report.get(f"{prefix}_tokens_saved", 0))
        module_original = report["prompt_original_tokens"] + report["original_context_tokens"] + report["document_original_tokens"] + report["code_original_tokens"]
        module_optimized = report["prompt_optimized_tokens"] + report["optimized_context_tokens"] + report["document_optimized_tokens"] + report["code_optimized_tokens"]
        module_saved = max(0, module_original - module_optimized)
        module_cost_before = report["prompt_cost_before"] + report["context_cost_before"] + report["document_cost_before"] + report["code_cost_before"]
        module_cost_after = report["prompt_cost_after"] + report["context_cost_after"] + report["document_cost_after"] + report["code_cost_after"]
        report["overall_original_tokens"] = module_original
        report["overall_optimized_tokens"] = module_optimized
        report["overall_tokens_saved"] = module_saved
        report["overall_reduction_percent"] = round((module_saved / module_original) * 100, 2) if module_original else 0
        report["overall_cost_before"] = round(module_cost_before, 8)
        report["overall_cost_after"] = round(module_cost_after, 8)
        report["overall_cost_saved"] = round(max(0.0, module_cost_before - module_cost_after), 8)
        report["original_tokens"] = module_original
        report["optimized_tokens"] = module_optimized
        report["saved_tokens"] = module_saved
        report["reduction_percent"] = report["overall_reduction_percent"]
        report["cost_before"] = report["overall_cost_before"]
        report["cost_after"] = report["overall_cost_after"]
        report["cost_saved"] = report["overall_cost_saved"]
        return report

    def _log_gemini_debug_report(self, request_id, candidate, optimization, optimized_prompt, exc):
        debug = getattr(exc, "debug_context", {})
        report = f"""========== GEMINI DEBUG REPORT ==========

Timestamp:
{time.strftime('%Y-%m-%dT%H:%M:%S%z')}

Request ID:
{request_id}

Provider:
{candidate.provider}

Model:
{candidate.model}

Endpoint:
{debug.get('endpoint', 'unknown')}

API Key Present:
{'YES' if debug.get('headers', {}).get('x-goog-api-key') not in (None, '<missing>') else 'NO'}

API Key Prefix:
{str(debug.get('headers', {}).get('x-goog-api-key', '<missing>')).replace('...', '')}

Cache Hit:
NO

AI Provider Called:
YES

Original Prompt Tokens:
{getattr(optimization, 'original_tokens', 'unknown')}

Optimized Prompt Tokens:
{getattr(optimization, 'optimized_tokens', 'unknown')}

Final Prompt:
{optimized_prompt[:1000]}

Generation Config:
{json.dumps(debug.get('request_body', {}).get('generationConfig'), ensure_ascii=False)}

HTTP Method:
POST

Request URL:
{debug.get('endpoint', 'unknown')}

HTTP Headers:
{json.dumps(debug.get('headers', {}), ensure_ascii=False)}

HTTP Request Body:
{json.dumps(debug.get('request_body', {}), ensure_ascii=False)}

================ RESPONSE ================

HTTP Status:
{exc.status_code or 'unknown'}

Response Headers:
{json.dumps(debug.get('response_headers', {}), ensure_ascii=False)}

Raw Response Body:
{debug.get('raw_response_body', exc.response_body or '<not captured>')}

================ ERROR ==================

Exception Type:
{type(exc).__name__}

Exception Message:
{exc}

Full Stack Trace:
{traceback.format_exc()}

================ SUMMARY =================

Was Gemini Called?
YES

Did Request Reach Gemini?
YES

Did Gemini Return a Response?
YES

Root Cause (Based on Logs):
Gemini returned HTTP {exc.status_code or 'unknown'}.

=========================================="""
        logger.error("\n%s", report)

    def generate(self, content: str, history: list[dict], images: list[dict], selected: ProviderCandidate, available: list[ProviderCandidate], documents: list[dict] | None = None, code_files: list[dict] | None = None, cache_scope: str | None = None, tenant_scope: str | None = None) -> AIResult:
        request_id = str(uuid.uuid4())
        classification = self.classifier.classify(content, history, images)
        selected_provider = selected.provider
        selected_model = selected.model
        embedded_document = self.document_optimizer.split_prompt(content)
        prompt_input = embedded_document[2] if embedded_document else content
        embedded_code_query, embedded_code = self.code_optimizer.split_prompt(prompt_input)
        if embedded_code:
            prompt_input = embedded_code_query
        optimization = self.prompt_optimizer.optimize(prompt_input, selected_provider, selected_model)
        optimized_content = self.document_optimizer.rebuild_prompt(optimization.optimized, embedded_document)
        if embedded_code and not documents:
            optimized_content = self.code_optimizer.rebuild_prompt(optimized_content, embedded_code)
        context = self.context_optimizer.select_context(history, optimized_content, selected_provider, selected_model)
        context = self.context_optimizer.compress_context(context, selected_provider, selected_model)
        cache_history, retry_turns_removed = self._cache_history(history, content)
        cache_context_selection = self.context_optimizer.select_context(cache_history, optimized_content, selected_provider, selected_model)
        cache_context = self.context_optimizer.compress_context(cache_context_selection, selected_provider, selected_model).messages
        semantic_context = [] if self._is_self_contained_prompt(content) else cache_context
        document = self.document_optimizer.optimize_document(optimized_content, selected_provider, selected_model, documents)
        optimized_document_prompt = document.prompt
        code = self.code_optimizer.optimize_code(optimized_document_prompt, selected_provider, selected_model, code_files)
        optimized_code_prompt = code.prompt
        messages = [*context.messages, {"role": "user", "content": optimized_code_prompt, "images": images}]
        candidates = self.router.candidates(selected, available, classification.level)
        cache_candidate = candidates[0]
        cache_key = cache_context_key = None
        global_key = global_context_key = None
        cache_tier = "private"
        cached = None
        cache_leader = False
        cache_started = time.perf_counter()
        try:
            cache_context_key = self.cache.context_key_for(context=semantic_context, documents=documents, code=code_files, images=images, scope=cache_scope, provider=cache_candidate.provider, model=cache_candidate.model)
            cache_key = self.cache.key_for(optimized_prompt=optimized_code_prompt, context=cache_context, documents=documents, code=code_files, images=images, scope=cache_scope, provider=cache_candidate.provider, model=cache_candidate.model)
            logger.info("CACHE_KEY_COMPONENTS request_id=%s backend=memory cache_instance=%s key_fingerprint=%s prompt_fingerprint=%s exact_context_fingerprint=%s semantic_context_fingerprint=%s documents_fingerprint=%s code_fingerprint=%s images_fingerprint=%s scope_fingerprint=%s provider=%s model=%s retry_turns_removed=%s self_contained=%s", request_id, id(self.cache), cache_key[:12], fingerprint(optimized_code_prompt), fingerprint(cache_context), fingerprint(semantic_context), fingerprint(documents or []), fingerprint(code_files or []), fingerprint(images or []), fingerprint(cache_scope or ""), cache_candidate.provider, cache_candidate.model, retry_turns_removed, self._is_self_contained_prompt(content))
            private_scope = tenant_scope or cache_scope or ""
            try:
                cached = self.cache.lookup(cache_key, semantic_query=optimized_code_prompt, context_key=cache_context_key, cache_tier="private", tenant_scope=private_scope)
            except Exception:
                logger.exception("CACHE ERROR request_id=%s tier=private; continuing to global lookup", request_id)
                cached = None
            global_eligible = self._is_self_contained_prompt(content) and not documents and not code_files and not images and bool(tenant_scope)
            if not cached and global_eligible:
                global_context_key = self.cache.context_key_for(context=[], documents=[], code=[], images=[], scope=tenant_scope, provider=cache_candidate.provider, model=cache_candidate.model)
                global_key = self.cache.key_for(optimized_prompt=optimized_code_prompt, context=[], documents=[], code=[], images=[], scope=tenant_scope, provider=cache_candidate.provider, model=cache_candidate.model)
                try:
                    cached = self.cache.lookup(global_key, semantic_query=optimized_code_prompt, context_key=global_context_key, cache_tier="global", tenant_scope=tenant_scope)
                except Exception:
                    logger.exception("CACHE ERROR request_id=%s tier=global; continuing to provider", request_id)
                    cached = None
                cache_tier = "global" if cached else "private"
            if not cached:
                cache_leader, in_flight = self.cache.begin(cache_key)
                if not cache_leader:
                    logger.info("CACHE COALESCED request_id=%s waiting_for_existing_request=true", request_id)
                    in_flight.wait(timeout=55)
                    cached = self.cache.lookup(cache_key, semantic_query=optimized_code_prompt, context_key=cache_context_key, cache_tier="private", tenant_scope=private_scope)
        except Exception:
            logger.exception("CACHE ERROR request_id=%s; bypassing cache and calling provider", request_id)
        if cached:
            report = self._build_report(optimization, context, document, code, cache_candidate.provider, cache_candidate.model, request_id)
            report["cache_status"] = "HIT"
            report["cache"] = {"status": "HIT", "tier": cache_tier, "api_call_avoided": True, "response_time_saved_ms": cached.provider_latency_ms}
            latency = round((time.perf_counter() - cache_started) * 1000)
            logger.info("AI cache request_id=%s cache=HIT provider=%s model=%s response_time_ms=%s api_call_avoided=true", request_id, cache_candidate.provider, cache_candidate.model, cached.provider_latency_ms)
            return AIResult(cached.content, cached.provider, cached.model, request_id, classification.level, classification.confidence, report["optimized_tokens"], latency, report)
        errors = []
        started = time.perf_counter()
        # A cache miss represents one user request. ProviderRouter chooses the
        # single provider/key for that request; do not turn one miss into
        # multiple upstream API calls through fallback candidates.
        for candidate in candidates[:1]:
            try:
                logger.info("PROVIDER_CALL request_id=%s", request_id)
                logger.info("AI provider invocation timestamp=%s file=%s function=%s request_id=%s source=%s record_id=%s provider=%s model=%s key_fingerprint=%s", time.time(), __file__, "ChatService.generate", request_id, candidate.source, candidate.key_id, candidate.provider, candidate.model, _api_key_fingerprint(candidate.secret))
                answer = provider_for(candidate.provider, candidate.base_url).generate(candidate.secret, candidate.model, messages)
                latency = round((time.perf_counter() - started) * 1000)
                report = self._build_report(optimization, context, document, code, candidate.provider, candidate.model, request_id)
                report["cache_status"] = "MISS"
                report["cache"] = {"status": "MISS", "api_call_avoided": False, "response_time_saved_ms": 0}
                if cache_key and isinstance(answer, str) and answer.strip():
                    self.cache.store(cache_key, answer, candidate.provider, candidate.model, latency, report, semantic_query=optimized_code_prompt, context_key=cache_context_key, cache_tier="private", tenant_scope=tenant_scope or cache_scope or "")
                    if global_key and global_context_key:
                        self.cache.store(global_key, answer, candidate.provider, candidate.model, latency, report, semantic_query=optimized_code_prompt, context_key=global_context_key, cache_tier="global", tenant_scope=tenant_scope or "")
                logger.info("AI cache request_id=%s cache=MISS provider=%s model=%s response_time_ms=%s api_call_avoided=false", request_id, candidate.provider, candidate.model, latency)
                logger.info("Code optimization request_id=%s language=%s files_received=%s files_sent=%s functions_selected=%s dependencies_included=%s original_tokens=%s optimized_tokens=%s tokens_saved=%s optimization_ms=%s", request_id, ",".join(sorted({item.get('language', 'unknown') for item in (code_files or [])})) or "embedded", code.files_received, code.files_sent, code.functions_selected, code.dependencies_included, code.original_tokens, code.optimized_tokens, code.saved_tokens, code.optimization_ms)
                logger.info("Document optimization request_id=%s document=%s original_tokens=%s optimized_tokens=%s chunks_selected=%s chunks_removed=%s percentage_saved=%.2f cost_saved=%.8f optimization_ms=%s", request_id, document.document_name, document.original_tokens, document.optimized_tokens, document.chunks_selected, document.chunks_removed, document.reduction_percent, document.cost_saved, document.optimization_ms)
                logger.info("Context optimization request_id=%s original_context_tokens=%s optimized_context_tokens=%s messages_removed=%s messages_preserved=%s percentage_saved=%.2f cost_saved=%.8f optimization_ms=%s", request_id, context.original_tokens, context.optimized_tokens, context.messages_removed, context.messages_preserved, context.reduction_percent, context.cost_saved, context.optimization_ms)
                logger.info("Prompt optimization request_id=%s timestamp=%s provider=%s model=%s original_tokens=%s optimized_tokens=%s saved_tokens=%s reduction_percent=%.2f cost_saved=%.8f optimization_ms=%s", request_id, time.time(), candidate.provider, candidate.model, report["original_tokens"], report["optimized_tokens"], report["saved_tokens"], report["reduction_percent"], report["cost_saved"], report["optimization_ms"])
                logger.info("AI request_id=%s complexity=%s provider=%s model=%s reason=%s confidence=%.2f estimated_tokens=%s latency_ms=%s", request_id, classification.level, candidate.provider, candidate.model, classification.reason, classification.confidence, report["optimized_tokens"], latency)
                return AIResult(answer, candidate.provider, candidate.model, request_id, classification.level, classification.confidence, report["optimized_tokens"], latency, report)
            except ProviderRequestError as exc:
                errors.append(f"{candidate.provider} (HTTP {exc.status_code or 'unknown'}): {exc}")
                logger.warning("AI provider error request_id=%s complexity=%s provider=%s model=%s status=%s error=%s", request_id, classification.level, candidate.provider, candidate.model, exc.status_code, exc)
            except Exception as exc:
                errors.append(f"{candidate.provider}: {exc}")
                logger.exception("AI provider unexpected error request_id=%s complexity=%s provider=%s model=%s", request_id, classification.level, candidate.provider, candidate.model)
            finally:
                if cache_leader and cache_key:
                    try:
                        self.cache.finish(cache_key)
                    except Exception:
                        logger.exception("CACHE ERROR request_id=%s while releasing single-flight request", request_id)
        logger.error("AI request failed request_id=%s complexity=%s errors=%s", request_id, classification.level, errors)
        raise HTTPException(502, {"request_id": request_id, "message": "All configured AI providers failed.", "errors": errors})
