"""Provider boundary: no route or UI code ever handles decrypted secrets."""
from abc import ABC, abstractmethod
import logging
import re
import time
import traceback
import httpx


logger = logging.getLogger(__name__)


class ProviderRequestError(Exception):
    """Safe provider failure; raw provider responses stay in backend logs."""

    def __init__(self, provider: str, status_code: int | None = None, *, url: str | None = None, model: str | None = None, response_body=None, request_payload=None, traceback_text=None):
        self.provider = provider
        self.status_code = status_code
        self.url = url
        self.model = model
        self.response_body = response_body
        self.request_payload = request_payload
        self.traceback_text = traceback_text
        super().__init__(f"{provider} request failed")


class AIProvider(ABC):
    @abstractmethod
    def complete(self, api_key: str, model: str, messages: list[dict]) -> str: ...


def openai_messages(messages: list[dict]) -> list[dict]:
    """Convert persisted image attachments to the OpenAI-compatible vision shape."""
    result = []
    for message in messages:
        images = message.get("images") or []
        if not images:
            result.append({"role": message["role"], "content": message["content"]})
            continue
        content = [{"type": "text", "text": message["content"]}]
        content.extend({"type": "image_url", "image_url": {"url": f"data:{image['mime_type']};base64,{image['data']}"}} for image in images)
        result.append({"role": message["role"], "content": content})
    return result


class OpenAIProvider(AIProvider):
    base_url = "https://api.openai.com/v1"

    def complete(self, api_key, model, messages):
        endpoint = self.base_url.rstrip("/")
        if not endpoint.endswith("/chat/completions"):
            endpoint += "/chat/completions"
        response = httpx.post(
            endpoint,
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": model, "messages": openai_messages(messages)}, timeout=60,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]


class GroqProvider(OpenAIProvider):
    base_url = "https://api.groq.com/openai/v1"

    def complete(self, api_key, model, messages):
        response = httpx.post(f"{self.base_url}/chat/completions", headers={"Authorization": f"Bearer {api_key}"}, json={"model": model, "messages": openai_messages(messages)}, timeout=60)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]


class GeminiProvider(AIProvider):
    DEFAULT_MODEL = "gemini-2.5-flash"
    MODEL_ALIASES = {
        "gemini": DEFAULT_MODEL,
        "gemini free tier": DEFAULT_MODEL,
        "free tier": DEFAULT_MODEL,
    }

    @classmethod
    def normalize_model(cls, model: str) -> str:
        normalized = model.strip().removeprefix("models/")
        normalized = cls.MODEL_ALIASES.get(normalized.lower(), normalized)
        # The UI previously retained the OpenAI default when Gemini was selected.
        # Never send a non-Gemini model id to Google's endpoint.
        if not normalized.lower().startswith("gemini-"):
            normalized = cls.DEFAULT_MODEL
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{1,119}", normalized):
            raise ProviderRequestError("Gemini", 400)
        return normalized

    def complete(self, api_key, model, messages):
        model = self.normalize_model(model)
        contents = []
        for item in messages:
            images = item.get("images") or []
            if item.get("role") not in {"user", "assistant"} or (not str(item.get("content", "")).strip() and not images):
                continue
            role = "model" if item["role"] == "assistant" else "user"
            text = str(item["content"])
            parts = ([{"text": text}] if text else []) + [{"inline_data": {"mime_type": image["mime_type"], "data": image["data"]}} for image in images]
            # Gemini chat contents must alternate user/model turns. A failed
            # request is not persisted as an assistant turn, so retries can
            # otherwise produce user -> user and Google returns HTTP 400.
            if contents and contents[-1]["role"] == role:
                contents[-1]["parts"].extend(parts)
            else:
                contents.append({"role": role, "parts": parts})
        if not contents:
            exc = ValueError("Gemini request has no non-empty user or model contents")
            trace = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            logger.error(
                "Gemini request validation exception provider=Gemini model=%s url=%s status=400 request_payload=%s response_body=None exception=%s traceback=%s",
                model, None, {"contents": contents}, exc, trace,
            )
            print(f"GEMINI COMPLETE EXCEPTION provider=Gemini model={model} url=None status=400 request_payload={{'contents': {contents}}} response_body=None exception={exc}\n{trace}", flush=True)
            raise ProviderRequestError("Gemini", 400, model=model, request_payload={"contents": contents}, traceback_text=trace) from exc

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        provider = "Gemini"
        request_payload = {"contents": contents}
        try:
            response = None
            for attempt in range(3):
                response = httpx.post(
                    url,
                    headers={"x-goog-api-key": api_key},
                    json=request_payload,
                    timeout=60,
                )
                if response.status_code not in {429, 500, 502, 503, 504} or attempt == 2:
                    break
                logger.warning(
                    "Transient Gemini response; retrying provider=%s model=%s status=%s attempt=%s/3",
                    provider, model, response.status_code, attempt + 1,
                )
                time.sleep(1.5 * (attempt + 1))
        except Exception as exc:
            trace = traceback.format_exc()
            logger.exception(
                "Gemini transport exception provider=%s model=%s url=%s status=%s request_payload=%s response_body=%s exception=%s traceback=%s",
                provider, model, url, None, request_payload, None, exc, trace,
            )
            print(f"GEMINI COMPLETE EXCEPTION provider={provider} model={model} url={url} status=None request_payload={request_payload} response_body=None exception={exc}\n{trace}", flush=True)
            raise ProviderRequestError(provider, url=url, model=model, request_payload=request_payload, traceback_text=trace) from exc
        if response.is_error:
            try:
                error_body = response.json()
            except ValueError:
                error_body = {"raw_response": response.text}
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                trace = traceback.format_exc()
                logger.exception(
                    "Gemini API rejection provider=%s model=%s url=%s status=%s request_payload=%s response_body=%s exception=%s traceback=%s",
                    provider, model, url, response.status_code, request_payload, error_body, exc, trace,
                )
                print(f"GEMINI COMPLETE EXCEPTION provider={provider} model={model} url={url} status={response.status_code} request_payload={request_payload} response_body={error_body} exception={exc}\n{trace}", flush=True)
                raise ProviderRequestError(provider, response.status_code, url=url, model=model, response_body=error_body, request_payload=request_payload, traceback_text=trace) from exc
        try:
            return response.json()["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            trace = traceback.format_exc()
            logger.exception(
                "Gemini response parsing exception provider=%s model=%s url=%s status=%s request_payload=%s response_body=%s exception=%s traceback=%s",
                provider, model, url, response.status_code, request_payload, response.text, exc, trace,
            )
            print(f"GEMINI COMPLETE EXCEPTION provider={provider} model={model} url={url} status={response.status_code} request_payload={request_payload} response_body={response.text} exception={exc}\n{trace}", flush=True)
            raise ProviderRequestError(provider, response.status_code, url=url, model=model, response_body=response.text, request_payload=request_payload, traceback_text=trace) from exc


class AnthropicProvider(AIProvider):
    def complete(self, api_key, model, messages):
        system = "\n".join(item["content"] for item in messages if item["role"] == "system")
        anthropic_messages = []
        for item in messages:
            if item["role"] == "system":
                continue
            images = item.get("images") or []
            if images:
                content = [{"type": "text", "text": item["content"]}] + [{"type": "image", "source": {"type": "base64", "media_type": image["mime_type"], "data": image["data"]}} for image in images]
            else:
                content = item["content"]
            anthropic_messages.append({"role": item["role"], "content": content})
        body = {"model": model, "max_tokens": 4096, "messages": anthropic_messages}
        if system: body["system"] = system
        response = httpx.post("https://api.anthropic.com/v1/messages", headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"}, json=body, timeout=60)
        response.raise_for_status()
        return "".join(part["text"] for part in response.json()["content"] if part.get("type") == "text")


class OpenAICompatibleProvider(OpenAIProvider):
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")


def provider_for(name: str, base_url: str | None = None) -> AIProvider:
    providers = {"openai": OpenAIProvider, "azure openai": OpenAIProvider, "groq": GroqProvider, "gemini": GeminiProvider, "claude": AnthropicProvider, "anthropic": AnthropicProvider}
    provider = providers.get(name.lower())
    if provider:
        return provider()
    compatible_defaults = {
        "openrouter": "https://openrouter.ai/api/v1",
        "deepseek": "https://api.deepseek.com",
        "mistral": "https://api.mistral.ai/v1",
        "xai": "https://api.x.ai/v1",
    }
    if name.lower() in compatible_defaults:
        return OpenAICompatibleProvider(base_url or compatible_defaults[name.lower()])
    if base_url:
        return OpenAICompatibleProvider(base_url)
    raise ValueError("Unsupported AI provider")
