from dataclasses import dataclass
import re


@dataclass(frozen=True)
class Classification:
    level: str
    confidence: float
    estimated_tokens: int
    reason: str


class RequestClassifier:
    """Deterministic request classification; it never creates or alters content."""

    def classify(self, content: str, history: list[dict], images: list[dict]) -> Classification:
        text = str(content or "")
        words = len(re.findall(r"\S+", text))
        estimated_tokens = max(1, len(text) // 4)
        context_tokens = sum(max(1, len(str(item.get("content", ""))) // 4) for item in history)
        has_code = bool(re.search(r"```|\b(class|function|def|SELECT|import|const|async)\b", text, re.I))
        complex_task = bool(re.search(r"\b(architect|architecture|system design|research|multi[- ]step|analy[sz]e.*log|complex|large|entire application)\b", text, re.I))
        medium_task = bool(re.search(r"\b(debug|refactor|api|sql|database|document|integrat|implement|explain)\b", text, re.I))

        score = 0
        reasons = []
        if estimated_tokens > 1800 or context_tokens > 5000:
            score += 3; reasons.append("long request or conversation context")
        elif estimated_tokens > 450 or context_tokens > 1400:
            score += 2; reasons.append("moderate request or conversation context")
        if images:
            score += 1; reasons.append("uploaded media")
        if has_code:
            score += 1; reasons.append("code detected")
        if complex_task:
            score += 3; reasons.append("complex reasoning task")
        elif medium_task:
            score += 1; reasons.append("technical task")
        if words <= 8 and not has_code and not medium_task:
            score = max(0, score - 1); reasons.append("short request")

        level = "HIGH" if score >= 5 else "MEDIUM" if score >= 2 else "LOW"
        confidence = min(0.99, 0.55 + min(score, 6) * 0.07 + (0.08 if reasons else 0))
        return Classification(level, round(confidence, 2), estimated_tokens, "; ".join(reasons) or "general request")
