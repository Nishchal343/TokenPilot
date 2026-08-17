from abc import ABC, abstractmethod
import logging
import time
import httpx

from app.config.optimization import GEMINI_FALLBACK_MODEL

logger = logging.getLogger(__name__)


def configured_model(provider: str, model: str | None) -> str:
    value = (model or "").strip().removeprefix("models/")
    provider_name = provider.strip().lower()
    if provider_name == "gemini" and (not value.lower().startswith("gemini-") or value.lower() == "gemini-2.5-flash"):
        logger.warning("Gemini model normalized requested_model=%s effective_model=%s", value or "<missing>", GEMINI_FALLBACK_MODEL)
        return GEMINI_FALLBACK_MODEL
    if provider_name == "groq" and value.lower() in {"llama-3.3-70b-versatile", "llama-3.1-8b-instant"}:
        fallback = "openai/gpt-oss-120b"
        logger.warning("Groq deprecated model normalized requested_model=%s effective_model=%s", value, fallback)
        return fallback
    if provider_name == "groq" and (not value or value.lower().startswith(("gpt-", "gemini-", "claude-"))):
        fallback = "openai/gpt-oss-120b"
        logger.warning("Groq model normalized requested_model=%s effective_model=%s", value or "<missing>", fallback)
        return fallback
    return value


class ProviderRequestError(Exception):
    def __init__(self, provider: str, status_code: int | None = None, *, model=None, response_body=None, debug_context=None):
        self.provider = provider
        self.status_code = status_code
        self.model = model
        self.response_body = response_body
        self.debug_context = debug_context or {}
        super().__init__(f"{provider} request failed")


class AIProvider(ABC):
    @abstractmethod
    def generate(self, api_key: str, model: str, messages: list[dict]) -> str: ...


def _openai_messages(messages):
    result = []
    for item in messages:
        images = item.get("images") or []
        if not images:
            result.append({"role": item["role"], "content": item["content"]})
            continue
        content = [{"type": "text", "text": item.get("content", "")}]
        content.extend({"type": "image_url", "image_url": {"url": f"data:{image['mime_type']};base64,{image['data']}"}} for image in images)
        result.append({"role": item["role"], "content": content})
    return result


class OpenAICompatibleProvider(AIProvider):
    def __init__(self, base_url, provider_name="OpenAI-compatible"):
        self.base_url = base_url.rstrip("/")
        self.provider_name = provider_name

    def generate(self, api_key, model, messages):
        url = f"{self.base_url}/chat/completions"
        try:
            response = httpx.post(url, headers={"Authorization": f"Bearer {api_key}"}, json={"model": model, "messages": _openai_messages(messages)}, timeout=60)
            if response.is_error:
                raise ProviderRequestError(self.provider_name, response.status_code, model=model, response_body=response.text)
            return response.json()["choices"][0]["message"]["content"]
        except ProviderRequestError:
            raise
        except Exception as exc:
            logger.exception("Provider transport or response error url=%s error=%s", url, exc)
            raise ProviderRequestError(self.provider_name, model=model) from exc


class GeminiProvider(AIProvider):
    def generate(self, api_key, model, messages):
        model = configured_model("gemini", model)
        contents = []
        for item in messages:
            role = "model" if item["role"] == "assistant" else "user"
            parts = ([{"text": str(item.get("content", ""))}] if item.get("content") else []) + [{"inline_data": {"mime_type": image["mime_type"], "data": image["data"]}} for image in item.get("images") or []]
            if not parts:
                continue
            if contents and contents[-1]["role"] == role:
                contents[-1]["parts"].extend(parts)
            else:
                contents.append({"role": role, "parts": parts})
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        request_body = {"contents": contents}
        try:
            logger.info("Gemini API invocation file=%s function=%s timestamp=%s model=%s", __file__, "GeminiProvider.generate", time.time(), model)
            logger.info("Gemini request prepared model=%s message_count=%s content_parts=%s", model, len(contents), sum(len(item["parts"]) for item in contents))
            response = httpx.post(url, headers={"x-goog-api-key": api_key}, json=request_body, timeout=60)
            logger.info("Gemini response received model=%s status=%s", model, getattr(response, "status_code", "unknown"))
            if response.is_error:
                raise ProviderRequestError("Gemini", response.status_code, model=model, response_body=response.text)
            return response.json()["candidates"][0]["content"]["parts"][0]["text"]
        except ProviderRequestError:
            raise
        except Exception as exc:
            logger.exception("Gemini transport or response error model=%s error=%s", model, exc)
            raise ProviderRequestError("Gemini", model=model) from exc


class AnthropicProvider(AIProvider):
    def generate(self, api_key, model, messages):
        system = "\n".join(item["content"] for item in messages if item["role"] == "system")
        body_messages = [{"role": item["role"], "content": item["content"]} for item in messages if item["role"] != "system"]
        body = {"model": model, "max_tokens": 4096, "messages": body_messages}
        if system:
            body["system"] = system
        try:
            response = httpx.post("https://api.anthropic.com/v1/messages", headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"}, json=body, timeout=60)
            if response.is_error:
                raise ProviderRequestError("Anthropic", response.status_code, model=model, response_body=response.text)
            return "".join(part["text"] for part in response.json()["content"] if part.get("type") == "text")
        except ProviderRequestError:
            raise
        except Exception as exc:
            logger.exception("Anthropic transport or response error model=%s error=%s", model, exc)
            raise ProviderRequestError("Anthropic", model=model) from exc


def provider_for(name: str, base_url: str | None = None) -> AIProvider:
    value = name.strip().lower()
    if value == "gemini":
        return GeminiProvider()
    if value in {"claude", "anthropic"}:
        return AnthropicProvider()
    defaults = {"openai": "https://api.openai.com/v1", "groq": "https://api.groq.com/openai/v1", "openrouter": "https://openrouter.ai/api/v1", "deepseek": "https://api.deepseek.com/v1", "mistral": "https://api.mistral.ai/v1", "xai": "https://api.x.ai/v1"}
    if value in defaults or base_url:
        return OpenAICompatibleProvider(base_url or defaults[value], value)
    raise ValueError(f"Unsupported AI provider: {name}")
