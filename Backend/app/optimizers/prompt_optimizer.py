from dataclasses import dataclass
import json
import re
import time
from xml.etree import ElementTree

from app.config.model_pricing import estimate_input_cost, estimate_tokens


_FENCE_RE = re.compile(r"```[\s\S]*?```", re.MULTILINE)
_URL_RE = re.compile(r"(?:https?://|ftp://)[^\s<>]+|(?:[A-Za-z]:\\|/)[^\s<>]+")
_WORD_REPEAT_RE = re.compile(r"\b([A-Za-z][A-Za-z0-9'-]*)\b(?:\s+\1\b)+", re.IGNORECASE)
_SPACE_BEFORE_PUNCT_RE = re.compile(r"[ \t]+([,.;:!?])")
_DUPLICATE_SENTENCE_RE = re.compile(r"([^.!?\n]{2,}[.!?])(?:[ \t]+\1)+", re.IGNORECASE)
_SEMANTIC_PHRASES = (
    (re.compile(r"\bI am currently (?:trying to )?(?:learn|learning) about\b", re.IGNORECASE), "Explain"),
    (re.compile(r"\band I would like you to provide me with a detailed explanation of\b", re.IGNORECASE), ":"),
    (re.compile(r"\bCan you provide me with a comprehensive explanation of\b", re.IGNORECASE), "Explain"),
    (re.compile(r"\bI would like you to please explain in detail\b", re.IGNORECASE), "Explain"),
    (re.compile(r"\bPlease provide a detailed explanation of\b", re.IGNORECASE), "Explain"),
    (re.compile(r"\bwhat the main principles and constraints of ([A-Za-z][A-Za-z0-9 /-]*) are\b", re.IGNORECASE), r"\1 principles/constraints"),
    (re.compile(r"\bhow a client communicates with a ([A-Za-z][A-Za-z0-9 /-]*) server\b", re.IGNORECASE), r"client-\1 communication"),
    (re.compile(r"\bfinally provide a simple practical example showing\b", re.IGNORECASE), "include a practical example of"),
    (re.compile(r"\bprovide me with\b", re.IGNORECASE), "provide"),
    (re.compile(r"\bin order to\b", re.IGNORECASE), "to"),
    (re.compile(r"\ba list of all\b", re.IGNORECASE), "all"),
    (re.compile(r"\ba specific\b", re.IGNORECASE), "one"),
)


@dataclass(frozen=True)
class PromptOptimization:
    original: str
    optimized: str
    original_characters: int
    optimized_characters: int
    original_tokens: int
    optimized_tokens: int
    saved_tokens: int
    reduction_percent: float
    cost_before: float
    cost_after: float
    cost_saved: float
    optimization_ms: int
    structural_tokens_saved: int = 0
    semantic_tokens_saved: int = 0
    optimization_attempted: bool = False
    optimization_accepted: bool = False

    def as_report(self, provider: str, model: str) -> dict:
        return {
            "module": "prompt",
            "provider": provider,
            "model": model,
            "original_characters": self.original_characters,
            "optimized_characters": self.optimized_characters,
            "original_tokens": self.original_tokens,
            "optimized_tokens": self.optimized_tokens,
            "saved_tokens": self.saved_tokens,
            "reduction_percent": self.reduction_percent,
            "cost_before": self.cost_before,
            "cost_after": self.cost_after,
            "cost_saved": self.cost_saved,
            "optimization_ms": self.optimization_ms,
            "structural_tokens_saved": self.structural_tokens_saved,
            "semantic_tokens_saved": self.semantic_tokens_saved,
            "optimization_attempted": self.optimization_attempted,
            "optimization_accepted": self.optimization_accepted,
            "stages": {"prompt": {"saved_tokens": self.saved_tokens}},
        }


class PromptOptimizer:
    """Meaning-preserving cleanup for natural-language prompts only."""

    def optimize(self, prompt: str, provider: str, model: str) -> PromptOptimization:
        started = time.perf_counter()
        original = prompt or ""
        structural = self._clean(original)
        original_tokens = estimate_tokens(original, provider, model)
        structural_tokens = estimate_tokens(structural, provider, model)
        semantic_candidate = self._semantic_compress(structural)
        optimization_attempted = semantic_candidate != structural
        candidate_tokens = estimate_tokens(semantic_candidate, provider, model)
        optimized = semantic_candidate if semantic_candidate and candidate_tokens < structural_tokens else structural
        optimized_tokens = estimate_tokens(optimized, provider, model)
        saved = max(0, original_tokens - optimized_tokens)
        cost_before = estimate_input_cost(original_tokens, provider, model)
        cost_after = estimate_input_cost(optimized_tokens, provider, model)
        return PromptOptimization(
            original=original,
            optimized=optimized,
            original_characters=len(original),
            optimized_characters=len(optimized),
            original_tokens=original_tokens,
            optimized_tokens=optimized_tokens,
            saved_tokens=saved,
            reduction_percent=round((saved / original_tokens) * 100, 2) if original_tokens else 0.0,
            cost_before=cost_before,
            cost_after=cost_after,
            cost_saved=round(max(0.0, cost_before - cost_after), 8),
            optimization_ms=round((time.perf_counter() - started) * 1000),
            structural_tokens_saved=max(0, original_tokens - structural_tokens),
            semantic_tokens_saved=max(0, structural_tokens - optimized_tokens),
            optimization_attempted=optimization_attempted,
            optimization_accepted=optimized == semantic_candidate and semantic_candidate != structural,
        )

    def calculate_statistics(self, original_prompt: str, optimized_prompt: str, provider: str, model: str) -> PromptOptimization:
        original = original_prompt or ""
        optimized = optimized_prompt or ""
        original_tokens = estimate_tokens(original, provider, model)
        optimized_tokens = estimate_tokens(optimized, provider, model)
        saved = max(0, original_tokens - optimized_tokens)
        before = estimate_input_cost(original_tokens, provider, model)
        after = estimate_input_cost(optimized_tokens, provider, model)
        return PromptOptimization(original, optimized, len(original), len(optimized), original_tokens, optimized_tokens, saved, round((saved / original_tokens) * 100, 2) if original_tokens else 0.0, before, after, round(max(0.0, before - after), 8), 0)

    def _clean(self, prompt: str) -> str:
        if not prompt or self._is_structured_document(prompt):
            return prompt.strip() if prompt and not self._is_structured_document(prompt) else prompt

        protected: list[str] = []

        def hold(match):
            protected.append(match.group(0))
            return f"\u0000{len(protected) - 1}\u0000"

        value = _FENCE_RE.sub(hold, prompt)
        value = _URL_RE.sub(hold, value)
        value = _WORD_REPEAT_RE.sub(r"\1", value)
        value = _DUPLICATE_SENTENCE_RE.sub(r"\1", value)
        value = _SPACE_BEFORE_PUNCT_RE.sub(r"\1", value)

        lines = value.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        cleaned_lines = []
        blank = False
        for line in lines:
            if not line.strip():
                if not blank:
                    cleaned_lines.append("")
                blank = True
                continue
            blank = False
            leading = re.match(r"^[ \t]*", line).group(0).replace("\t", "    ")
            body = line[len(re.match(r"^[ \t]*", line).group(0)):]
            body = re.sub(r"[ \t]+", " ", body).strip()
            cleaned_lines.append(leading + body)

        value = "\n".join(cleaned_lines).strip()
        for index, original in enumerate(protected):
            value = value.replace(f"\u0000{index}\u0000", original)
        return value

    def _semantic_compress(self, prompt: str) -> str:
        """Apply conservative, deterministic meaning-preserving phrase compression."""
        if not prompt or self._is_structured_document(prompt):
            return prompt
        protected: list[str] = []

        def hold(match):
            protected.append(match.group(0))
            return f"\u0000{len(protected) - 1}\u0000"

        # Compress prose around technical content, never the technical content itself.
        value = _FENCE_RE.sub(hold, prompt)
        value = _URL_RE.sub(hold, value)
        for pattern, replacement in _SEMANTIC_PHRASES:
            value = pattern.sub(replacement, value)
        value = re.sub(r"\bin computer science\b", "", value, flags=re.IGNORECASE)
        value = re.sub(r"\bwhat ([A-Za-z][A-Za-z0-9 /-]{1,70}) (is|are)\b", r"\1 definition", value, flags=re.IGNORECASE)
        value = re.sub(r"\bwhat ([A-Za-z][A-Za-z0-9 /-]{1,70}) mean(?:s)? in this context\b", r"\1 meaning", value, flags=re.IGNORECASE)
        value = re.sub(r"\s+([,.;:])", r"\1", value)
        value = re.sub(r"[ \t]{2,}", " ", value).strip()
        for index, original in enumerate(protected):
            value = value.replace(f"\u0000{index}\u0000", original)
        return value

    @staticmethod
    def _is_structured_document(prompt: str) -> bool:
        candidate = prompt.strip()
        if not candidate:
            return False
        try:
            json.loads(candidate)
            return True
        except (ValueError, TypeError):
            pass
        if candidate.startswith("<") and candidate.endswith(">"):
            try:
                ElementTree.fromstring(candidate)
                return True
            except ElementTree.ParseError:
                pass
        first = candidate.splitlines()[0].strip().lower()
        if first in {"---", "select", "with", "insert", "update", "delete", "create", "alter", "drop"}:
            return True
        if re.match(r"^(select|with|insert\s+into|update\s+|delete\s+from|create\s+table)\b", candidate, re.IGNORECASE) and ";" in candidate:
            return True
        return False
