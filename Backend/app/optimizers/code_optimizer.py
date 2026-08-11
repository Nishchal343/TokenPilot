from dataclasses import dataclass
import re
import time
from pathlib import PurePath

from app.config.model_pricing import estimate_input_cost, estimate_tokens
from app.config.optimization import CODE_DEPENDENCY_DEPTH, CODE_IGNORED_DIRECTORIES, CODE_SUPPORTED_LANGUAGES, MAX_CODE_FILES, MAX_CODE_TOKENS


_FENCE_RE = re.compile(r"```(?P<language>[A-Za-z0-9_+#-]*)\s*\n(?P<code>[\s\S]*?)```", re.MULTILINE)
_WORD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_IMPORT_PATTERNS = {
    "python": [re.compile(r"^\s*(?:from|import)\s+([\w.]+)", re.MULTILINE)],
    "javascript": [re.compile(r"(?:from\s+|require\(['\"])([^'\")]+)", re.MULTILINE)],
    "typescript": [re.compile(r"(?:from\s+|require\(['\"])([^'\")]+)", re.MULTILINE)],
    "java": [re.compile(r"^\s*import\s+([\w.]+)", re.MULTILINE)],
    "c": [re.compile(r"^\s*#include\s*[<\"]([^>\"]+)", re.MULTILINE)],
    "cpp": [re.compile(r"^\s*#include\s*[<\"]([^>\"]+)", re.MULTILINE)],
    "go": [re.compile(r"^\s*import\s+(?:\([^)]*\)|\"([^\"]+)\")", re.MULTILINE | re.DOTALL)],
    "rust": [re.compile(r"^\s*(?:use|mod)\s+([\w:]+)", re.MULTILINE)],
}
_EXTENSIONS = {".py": "python", ".js": "javascript", ".jsx": "javascript", ".ts": "typescript", ".tsx": "typescript", ".java": "java", ".c": "c", ".h": "c", ".cpp": "cpp", ".cc": "cpp", ".hpp": "cpp", ".go": "go", ".rs": "rust", ".html": "html", ".css": "css", ".sql": "sql"}
_UNIT_RE = re.compile(r"(?m)^(?P<indent>\s*)(?P<header>(?:async\s+)?(?:def|class|function|fn|func|interface|type|struct|enum)\s+[A-Za-z_][\w]*)")


@dataclass(frozen=True)
class CodeSelection:
    prompt: str
    original_tokens: int
    optimized_tokens: int
    saved_tokens: int
    reduction_percent: float
    cost_before: float
    cost_after: float
    cost_saved: float
    files_received: int
    files_sent: int
    functions_selected: int
    dependencies_included: int
    optimization_ms: int

    def as_report(self, provider: str, model: str) -> dict:
        return {
            "code_original_tokens": self.original_tokens,
            "code_optimized_tokens": self.optimized_tokens,
            "code_tokens_saved": self.saved_tokens,
            "code_reduction_percent": self.reduction_percent,
            "code_cost_before": self.cost_before,
            "code_cost_after": self.cost_after,
            "code_cost_saved": self.cost_saved,
            "code_files_received": self.files_received,
            "code_files_sent": self.files_sent,
            "code_functions_selected": self.functions_selected,
            "code_dependencies_included": self.dependencies_included,
            "code_optimization_ms": self.optimization_ms,
            "code_provider": provider,
            "code_model": model,
            "stages": {"code": {"saved_tokens": self.saved_tokens}},
        }


class CodeOptimizer:
    """Selects relevant original code; it never edits, rewrites, or generates code."""

    def __init__(self, max_tokens: int = MAX_CODE_TOKENS, max_files: int = MAX_CODE_FILES, dependency_depth: int = CODE_DEPENDENCY_DEPTH, supported_languages: tuple = CODE_SUPPORTED_LANGUAGES, ignored_directories: tuple = CODE_IGNORED_DIRECTORIES):
        self.max_tokens = max_tokens
        self.max_files = max_files
        self.dependency_depth = dependency_depth
        self.supported_languages = {value.lower() for value in supported_languages}
        self.ignored_directories = {value.lower() for value in ignored_directories}

    def optimize_code(self, prompt: str, provider: str, model: str, code_files: list[dict] | None = None) -> CodeSelection:
        started = time.perf_counter()
        files = self._files_from_prompt(prompt) if not code_files else self._normalize_files(code_files)
        if not files:
            return CodeSelection(prompt, 0, 0, 0, 0.0, 0.0, 0.0, 0.0, 0, 0, 0, 0, round((time.perf_counter() - started) * 1000))
        query = self._query_from_prompt(prompt)
        selected, functions, dependencies = self.select_relevant_code(files, query)
        original_text = "\n\n".join(f"# FILE: {item['name']}\n{item['content']}" for item in files)
        optimized_text = "\n\n".join(f"# FILE: {item['name']}\n{item['content']}" for item in selected)
        optimized_prompt = self._rebuild_prompt(prompt, optimized_text, files)
        original_tokens = estimate_tokens(original_text, provider, model)
        optimized_tokens = estimate_tokens(optimized_text, provider, model)
        saved = max(0, original_tokens - optimized_tokens)
        before = estimate_input_cost(original_tokens, provider, model)
        after = estimate_input_cost(optimized_tokens, provider, model)
        return CodeSelection(optimized_prompt, original_tokens, optimized_tokens, saved, round((saved / original_tokens) * 100, 2) if original_tokens else 0.0, before, after, round(max(0.0, before - after), 8), len(files), len(selected), functions, dependencies, round((time.perf_counter() - started) * 1000))

    def split_prompt(self, prompt: str):
        files = self._files_from_prompt(prompt)
        return self._query_from_prompt(prompt), files if files else None

    def rebuild_prompt(self, query: str, files: list[dict] | None) -> str:
        if not files:
            return query
        code = "\n\n".join(f"# FILE: {item['name']}\n{item['content']}" for item in files)
        return self._rebuild_prompt(query, code, files)

    def detect_language(self, filename: str = "", content: str = "", declared: str | None = None) -> str:
        if declared:
            value = declared.lower()
            value = {"js": "javascript", "jsx": "javascript", "ts": "typescript", "tsx": "typescript", "py": "python"}.get(value, value)
            if value in self.supported_languages:
                return value
        return _EXTENSIONS.get(PurePath(filename).suffix.lower(), "unknown")

    def analyze_dependencies(self, item: dict, files: list[dict]) -> list[dict]:
        language = item["language"]
        patterns = _IMPORT_PATTERNS.get(language, [])
        names = {match for pattern in patterns for group in pattern.findall(item["content"]) for match in (group if isinstance(group, tuple) else (group,)) if match}
        result = []
        for candidate in files:
            stem = PurePath(candidate["name"]).stem.lower()
            candidate_path = candidate["name"].replace("\\", "/").lower()
            if any(part in candidate_path.split("/") for part in self.ignored_directories):
                continue
            if any(stem == value.split(".")[-1].lower() or candidate_path.endswith(value.lower()) for value in names):
                result.append(candidate)
        return result

    def select_relevant_code(self, files: list[dict], query: str) -> tuple[list[dict], int, int]:
        query_words = self._words(query)
        ranked = []
        for index, item in enumerate(files):
            if item["language"] not in self.supported_languages:
                continue
            words = self._words(item["name"] + " " + item["content"])
            score = len(words & query_words) / max(1, len(query_words))
            filename = item["name"].lower()
            filename_words = self._words(filename)
            if any(word in filename or any(word.startswith(name) or name.startswith(word) for name in filename_words) for word in query_words):
                score += 0.35
            ranked.append((score, -index, item))
        ranked.sort(reverse=True, key=lambda value: (value[0], value[1]))
        selected = [item for score, _, item in ranked[:self.max_files] if score > 0 or len(ranked) == 1]
        if not selected and ranked:
            selected = [ranked[0][2]]
        dependency_count = 0
        for _ in range(self.dependency_depth):
            additions = []
            for item in selected:
                additions.extend(self.analyze_dependencies(item, files))
            for item in additions:
                if item not in selected and len(selected) < self.max_files:
                    selected.append(item)
                    dependency_count += 1
        functions = 0
        trimmed = []
        used = 0
        for item in selected:
            content = item["content"]
            units = self._relevant_units(content, query_words)
            if units and len(units) < len(self._units(content)):
                content = "\n\n".join(units)
                functions += len(units)
            clone = {**item, "content": content}
            tokens = estimate_tokens(content, "openai", "gpt-4o-mini")
            if trimmed and used + tokens > self.max_tokens:
                continue
            trimmed.append(clone)
            used += tokens
        return trimmed, functions, dependency_count

    def calculate_statistics(self, original: str, optimized: str, provider: str, model: str) -> CodeSelection:
        original_tokens = estimate_tokens(original, provider, model)
        optimized_tokens = estimate_tokens(optimized, provider, model)
        saved = max(0, original_tokens - optimized_tokens)
        before = estimate_input_cost(original_tokens, provider, model)
        after = estimate_input_cost(optimized_tokens, provider, model)
        return CodeSelection(optimized, original_tokens, optimized_tokens, saved, round((saved / original_tokens) * 100, 2) if original_tokens else 0.0, before, after, round(max(0.0, before - after), 8), 0, 0, 0, 0, 0)

    @staticmethod
    def _words(value: str) -> set[str]:
        return {word.lower() for word in _WORD_RE.findall(value or "")}

    def _normalize_files(self, files):
        output = []
        for item in files:
            name = item.get("name", "snippet.txt")
            if any(part.lower() in self.ignored_directories for part in name.replace("\\", "/").split("/")):
                continue
            output.append({"name": name, "content": item.get("content", ""), "language": self.detect_language(name, item.get("content", ""), item.get("language"))})
        return output

    def _files_from_prompt(self, prompt):
        files = []
        for index, match in enumerate(_FENCE_RE.finditer(prompt or "")):
            language = self.detect_language(f"snippet_{index}.{match.group('language') or 'txt'}", match.group("code"), match.group("language"))
            files.append({"name": f"snippet_{index}.{match.group('language') or 'txt'}", "content": match.group("code"), "language": language})
        return files

    @staticmethod
    def _query_from_prompt(prompt):
        return _FENCE_RE.sub("", prompt or "").strip()

    @staticmethod
    def _rebuild_prompt(prompt, code, files):
        if not code:
            return prompt
        query = _FENCE_RE.sub("", prompt or "").strip()
        return f"{query}\n\nRelevant code:\n```\n{code}\n```" if query else f"Relevant code:\n```\n{code}\n```"

    @staticmethod
    def _units(content):
        matches = list(_UNIT_RE.finditer(content))
        if not matches:
            return [content]
        return [content[matches[i].start():matches[i + 1].start() if i + 1 < len(matches) else len(content)].strip() for i in range(len(matches))]

    def _relevant_units(self, content, query_words):
        units = self._units(content)
        if len(units) <= 1:
            return units
        return [unit for unit in units if self._words(unit) & query_words]
