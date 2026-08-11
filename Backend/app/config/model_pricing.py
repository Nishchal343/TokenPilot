from decimal import Decimal, ROUND_HALF_UP
import math
import re


# USD per one million input tokens. Costs are converted to INR at the boundary
# because the existing TokenPilot dashboard displays rupees. Keep both pricing
# and the exchange rate here so future pricing updates remain isolated.
USD_TO_INR = Decimal("83.50")
MODEL_PRICING = {
    "gemini": {"default": Decimal("0.30")},
    "openai": {"default": Decimal("2.50"), "gpt-4o-mini": Decimal("0.15"), "gpt-5": Decimal("1.25")},
    "anthropic": {"default": Decimal("3.00"), "claude-3-5-haiku": Decimal("0.80")},
    "openrouter": {"default": Decimal("2.00")},
    "groq": {"default": Decimal("0.59")},
    "default": {"default": Decimal("1.00")},
}


def _provider_key(provider: str) -> str:
    value = (provider or "default").lower()
    return "anthropic" if value in {"anthropic", "claude"} else value


def input_price_per_million(provider: str, model: str) -> Decimal:
    provider_prices = MODEL_PRICING.get(_provider_key(provider), MODEL_PRICING["default"])
    model_value = (model or "").lower()
    for name, price in provider_prices.items():
        if name != "default" and name in model_value:
            return price
    return provider_prices["default"]


def estimate_tokens(text: str, provider: str, model: str) -> int:
    """Use tiktoken when available, with a provider-aware deterministic fallback."""
    try:
        import tiktoken
        encoding_name = "cl100k_base" if _provider_key(provider) != "gemini" else "o200k_base"
        encoding = tiktoken.get_encoding(encoding_name)
        return max(0, len(encoding.encode(text or "")))
    except Exception:
        # Character/token ratios differ by tokenizer; this fallback remains
        # deterministic and varies slightly by provider family.
        ratio = 3.6 if _provider_key(provider) == "anthropic" else 4.0 if _provider_key(provider) in {"openai", "openrouter", "groq"} else 4.2
        return math.ceil(len(text or "") / ratio) if text else 0


def estimate_input_cost(tokens: int, provider: str, model: str) -> float:
    value = (Decimal(max(0, tokens)) / Decimal(1_000_000)) * input_price_per_million(provider, model) * USD_TO_INR
    return float(value.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP))
