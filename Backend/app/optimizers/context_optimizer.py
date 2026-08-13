from dataclasses import dataclass
import re
import time

from app.config.model_pricing import estimate_input_cost, estimate_tokens
from app.config.optimization import MAX_CONTEXT_TOKENS, MIN_MESSAGES_TO_PRESERVE, PRIORITY_WEIGHTS, SIMILARITY_THRESHOLD


_WORD_RE = re.compile(r"[A-Za-z0-9_]{2,}")
_CODE_RE = re.compile(r"```|\b(class|def|function|const|let|var|import|api|endpoint|sql|query|jwt|token)\b", re.IGNORECASE)
_DOCUMENT_RE = re.compile(r"\b(document|file|pdf|docx|attachment|section|paragraph|report|specification)\b", re.IGNORECASE)
_FOLLOW_UP_RE = re.compile(r"\b(continue|again|also|that|this|it|above|previous|earlier|same|follow[- ]?up|now|next)\b", re.IGNORECASE)


@dataclass(frozen=True)
class ContextSelection:
    messages: list[dict]
    original_tokens: int
    optimized_tokens: int
    saved_tokens: int
    reduction_percent: float
    cost_before: float
    cost_after: float
    cost_saved: float
    messages_removed: int
    messages_preserved: int
    optimization_ms: int
    compression_applied: bool = False

    def as_report(self, provider: str, model: str) -> dict:
        return {
            "original_context_tokens": self.original_tokens,
            "optimized_context_tokens": self.optimized_tokens,
            "context_saved_tokens": self.saved_tokens,
            "context_reduction_percent": self.reduction_percent,
            "context_cost_before": self.cost_before,
            "context_cost_after": self.cost_after,
            "context_cost_saved": self.cost_saved,
            "context_messages_removed": self.messages_removed,
            "context_messages_preserved": self.messages_preserved,
            "context_optimization_ms": self.optimization_ms,
            "context_messages_before": self.messages_preserved + self.messages_removed,
            "context_messages_after": self.messages_preserved,
            "context_compression_applied": self.compression_applied,
            "context_provider": provider,
            "context_model": model,
            "stages": {"context": {"saved_tokens": self.saved_tokens}},
        }


class ContextOptimizer:
    """Selects relevant conversation history without generating or rewriting text."""

    def __init__(self, max_tokens: int = MAX_CONTEXT_TOKENS, minimum_messages: int = MIN_MESSAGES_TO_PRESERVE, threshold: float = SIMILARITY_THRESHOLD, weights: dict | None = None):
        self.max_tokens = max_tokens
        self.minimum_messages = minimum_messages
        self.threshold = threshold
        self.weights = weights or PRIORITY_WEIGHTS

    def select_context(self, history: list[dict], current_prompt: str, provider: str, model: str) -> ContextSelection:
        started = time.perf_counter()
        history = list(history or [])
        # Context statistics measure conversation history only. The current
        # request is measured by PromptOptimizer and must not be double-counted
        # in the overall report.
        original_tokens = sum(self._message_tokens(item, provider, model) for item in history)
        current_words = self._words(current_prompt)
        mandatory = [item for item in history if item.get("role") == "system" or item.get("project_instruction")]
        candidates = [item for item in history if item not in mandatory]
        scored = [(self._score(item, index, len(history), current_words), index, item) for index, item in enumerate(history) if item not in mandatory]
        scored.sort(key=lambda value: (value[0], value[1]), reverse=True)

        selected = list(mandatory)
        selected_ids = {id(item) for item in selected}
        current_tokens = estimate_tokens(current_prompt, provider, model)
        used = current_tokens + sum(self._message_tokens(item, provider, model) for item in selected)

        # Preserve a small recent working set first, provided the configured
        # window can accommodate it. The remaining budget is relevance-driven.
        recent = [item for item in reversed(candidates) if id(item) not in selected_ids][: self.minimum_messages]
        for item in reversed(recent):
            cost = self._message_tokens(item, provider, model)
            if used + cost <= self.max_tokens:
                selected.append(item)
                selected_ids.add(id(item))
                used += cost

        for score, _, item in scored:
            if id(item) in selected_ids or score < self.threshold:
                continue
            cost = self._message_tokens(item, provider, model)
            if used + cost <= self.max_tokens:
                selected.append(item)
                selected_ids.add(id(item))
                used += cost

        # Context must retain conversation order for provider APIs.
        selected.sort(key=lambda item: next((index for index, candidate in enumerate(history) if candidate is item), -1))
        optimized_tokens = sum(self._message_tokens(item, provider, model) for item in selected)
        saved = max(0, original_tokens - optimized_tokens)
        before = estimate_input_cost(original_tokens, provider, model)
        after = estimate_input_cost(optimized_tokens, provider, model)
        return ContextSelection(
            messages=selected,
            original_tokens=original_tokens,
            optimized_tokens=optimized_tokens,
            saved_tokens=saved,
            reduction_percent=round((saved / original_tokens) * 100, 2) if original_tokens else 0.0,
            cost_before=before,
            cost_after=after,
            cost_saved=round(max(0.0, before - after), 8),
            messages_removed=max(0, len(history) - len(selected)),
            messages_preserved=len(selected),
            optimization_ms=round((time.perf_counter() - started) * 1000),
        )

    def compress_context(self, selection: ContextSelection, provider: str, model: str) -> ContextSelection:
        """Remove only exact duplicate user/assistant turns from selected history.

        This is deliberately deterministic and conservative. It never rewrites
        message content, so code, JSON, SQL, URLs, and technical identifiers
        remain byte-for-byte unchanged. If compression fails or is not smaller,
        the original selection is returned.
        """
        messages = list(selection.messages)
        if len(messages) < 4:
            return selection
        try:
            duplicate_pairs: dict[tuple[str, str], int] = {}
            pair_indexes: set[int] = set()
            for index in range(len(messages) - 1):
                user, assistant = messages[index:index + 2]
                if user.get("role") != "user" or assistant.get("role") != "assistant":
                    continue
                pair = (self._message_fingerprint(user), self._message_fingerprint(assistant))
                if pair in duplicate_pairs:
                    first_index = duplicate_pairs[pair]
                    pair_indexes.update({first_index, first_index + 1})
                else:
                    duplicate_pairs[pair] = index
            if not pair_indexes:
                return selection
            compressed_messages = [message for index, message in enumerate(messages) if index not in pair_indexes]
            if not compressed_messages:
                return selection
            compressed_tokens = sum(self._message_tokens(item, provider, model) for item in compressed_messages)
            if compressed_tokens >= selection.optimized_tokens:
                return selection
            before = estimate_input_cost(selection.original_tokens, provider, model)
            after = estimate_input_cost(compressed_tokens, provider, model)
            return ContextSelection(
                messages=compressed_messages,
                original_tokens=selection.original_tokens,
                optimized_tokens=compressed_tokens,
                saved_tokens=max(0, selection.original_tokens - compressed_tokens),
                reduction_percent=round((max(0, selection.original_tokens - compressed_tokens) / selection.original_tokens) * 100, 2) if selection.original_tokens else 0.0,
                cost_before=before,
                cost_after=after,
                cost_saved=round(max(0.0, before - after), 8),
                messages_removed=selection.messages_removed + len(messages) - len(compressed_messages),
                messages_preserved=len(compressed_messages),
                optimization_ms=selection.optimization_ms,
                compression_applied=True,
            )
        except Exception:
            return selection

    @staticmethod
    def _message_fingerprint(message: dict) -> str:
        import hashlib
        import json
        value = {"role": message.get("role"), "content": message.get("content", ""), "images": message.get("images") or message.get("attachments") or []}
        return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode()).hexdigest()

    def calculate_statistics(self, history: list[dict], selected: list[dict], current_prompt: str, provider: str, model: str) -> ContextSelection:
        original_tokens = sum(self._message_tokens(item, provider, model) for item in history)
        optimized_tokens = sum(self._message_tokens(item, provider, model) for item in selected)
        saved = max(0, original_tokens - optimized_tokens)
        before = estimate_input_cost(original_tokens, provider, model)
        after = estimate_input_cost(optimized_tokens, provider, model)
        return ContextSelection(selected, original_tokens, optimized_tokens, saved, round((saved / original_tokens) * 100, 2) if original_tokens else 0.0, before, after, round(max(0.0, before - after), 8), max(0, len(history) - len(selected)), len(selected), 0)

    def _score(self, message: dict, index: int, total: int, current_words: set[str]) -> float:
        text = str(message.get("content", ""))
        words = self._words(text)
        similarity = len(words & current_words) / max(1, len(current_words))
        recency = (index + 1) / max(1, total)
        code = 1.0 if bool(_CODE_RE.search(text)) and bool(_CODE_RE.search(" ".join(current_words))) else 0.0
        documents = 1.0 if bool(_DOCUMENT_RE.search(text)) and bool(_DOCUMENT_RE.search(" ".join(current_words))) else 0.0
        follow_up = 1.0 if _FOLLOW_UP_RE.search(" ".join(current_words)) and index >= total - 4 else 0.0
        if message.get("images") or message.get("attachments"):
            documents = max(documents, 0.75)
        role_bonus = 0.08 if message.get("role") == "assistant" else 0.0
        return (self.weights["similarity"] * similarity + self.weights["recency"] * recency + self.weights["code"] * code + self.weights["documents"] * documents + self.weights["follow_up"] * follow_up + role_bonus)

    @staticmethod
    def _words(value: str) -> set[str]:
        return {word.lower() for word in _WORD_RE.findall(value or "")}

    @staticmethod
    def _message_tokens(message: dict, provider: str, model: str) -> int:
        return estimate_tokens(str(message.get("content", "")), provider, model) + sum(estimate_tokens(str(image), provider, model) for image in message.get("images", []) or [])
