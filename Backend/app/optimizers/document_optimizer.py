from dataclasses import dataclass
import io
import base64
import re
import time
from pathlib import PurePath
from xml.etree import ElementTree
import zipfile

from app.config.model_pricing import estimate_input_cost, estimate_tokens
from app.config.optimization import DOCUMENT_CHUNK_OVERLAP, DOCUMENT_CHUNK_SIZE, DOCUMENT_SIMILARITY_THRESHOLD, MAX_DOCUMENT_TOKENS, MAX_RETRIEVED_DOCUMENT_CHUNKS


_FILE_RE = re.compile(r"Please analyze this file \((?P<name>[^)]+)\):\s*\n\s*\n(?P<content>[\s\S]+)$", re.IGNORECASE)
_WORD_RE = re.compile(r"[A-Za-z0-9_]{2,}")
_HEADING_RE = re.compile(r"^\s{0,3}(?:#{1,6}\s+|(?:chapter|section)\s+\d+\b|\d+(?:\.\d+)*[.)]\s+)", re.IGNORECASE)
_PAGE_NUMBER_RE = re.compile(r"^\s*(?:page\s+)?\d+(?:\s+of\s+\d+)?\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class DocumentSelection:
    prompt: str
    original_tokens: int
    optimized_tokens: int
    saved_tokens: int
    reduction_percent: float
    cost_before: float
    cost_after: float
    cost_saved: float
    chunks_selected: int
    chunks_removed: int
    optimization_ms: int
    document_name: str | None = None

    def as_report(self, provider: str, model: str) -> dict:
        return {
            "document_original_tokens": self.original_tokens,
            "document_optimized_tokens": self.optimized_tokens,
            "document_tokens_saved": self.saved_tokens,
            "document_reduction_percent": self.reduction_percent,
            "document_cost_before": self.cost_before,
            "document_cost_after": self.cost_after,
            "document_cost_saved": self.cost_saved,
            "document_chunks_selected": self.chunks_selected,
            "document_chunks_removed": self.chunks_removed,
            "document_optimization_ms": self.optimization_ms,
            "document_name": self.document_name,
            "document_provider": provider,
            "document_model": model,
            "stages": {"document": {"saved_tokens": self.saved_tokens}},
        }


class DocumentOptimizer:
    """Retrieves relevant document chunks without generating or paraphrasing text."""

    def __init__(self, max_tokens: int = MAX_DOCUMENT_TOKENS, chunk_size: int = DOCUMENT_CHUNK_SIZE, chunk_overlap: int = DOCUMENT_CHUNK_OVERLAP, max_chunks: int = MAX_RETRIEVED_DOCUMENT_CHUNKS, threshold: float = DOCUMENT_SIMILARITY_THRESHOLD):
        self.max_tokens = max_tokens
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.max_chunks = max_chunks
        self.threshold = threshold

    def optimize_document(self, prompt: str, provider: str, model: str, documents: list[dict] | None = None) -> DocumentSelection:
        started = time.perf_counter()
        document = self._document_from_prompt(prompt) if not documents else self._first_document(documents, prompt)
        if not document:
            return self._empty(prompt, provider, model, round((time.perf_counter() - started) * 1000))
        name, raw_text, query, prefix = document
        text = self.extract_text(raw_text, name)
        chunks = self.chunk_document(text)
        unique_chunks = self._deduplicate(chunks)
        selected = self.retrieve_relevant_chunks(unique_chunks, query)
        selected_text = "\n\n".join(selected)
        optimized_prompt = f"{prefix}\n\n{selected_text}" if prefix else selected_text
        original_tokens = estimate_tokens(text, provider, model)
        optimized_tokens = estimate_tokens(selected_text, provider, model)
        saved = max(0, original_tokens - optimized_tokens)
        before = estimate_input_cost(original_tokens, provider, model)
        after = estimate_input_cost(optimized_tokens, provider, model)
        return DocumentSelection(optimized_prompt, original_tokens, optimized_tokens, saved, round((saved / original_tokens) * 100, 2) if original_tokens else 0.0, before, after, round(max(0.0, before - after), 8), len(selected), max(0, len(unique_chunks) - len(selected)), round((time.perf_counter() - started) * 1000), name)

    def split_prompt(self, prompt: str):
        """Separate the user's query from the legacy embedded-file payload."""
        return self._document_from_prompt(prompt)

    @staticmethod
    def rebuild_prompt(query: str, document: tuple | None) -> str:
        if not document:
            return query
        name, content, _, _ = document
        return f"{query}\n\nPlease analyze this file ({name}):\n\n{content}" if query else f"Please analyze this file ({name}):\n\n{content}"

    def extract_text(self, document: str | bytes, filename: str = "document.txt") -> str:
        suffix = PurePath(filename).suffix.lower()
        if isinstance(document, str):
            return document
        if suffix == ".docx":
            with zipfile.ZipFile(io.BytesIO(document)) as archive:
                root = ElementTree.fromstring(archive.read("word/document.xml"))
                return "\n".join("".join(node.itertext()) for node in root.iter() if node.tag.endswith("}p"))
        if suffix == ".pdf":
            try:
                from pypdf import PdfReader
                return "\n\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(document)).pages)
            except ImportError as exc:
                raise ValueError("PDF extraction requires the pypdf package.") from exc
        return document.decode("utf-8", errors="replace")

    def chunk_document(self, text: str) -> list[str]:
        lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        chunks, current = [], []
        for line in lines:
            if _HEADING_RE.match(line) and current:
                chunks.append("\n".join(current).strip())
                current = []
            if not line.strip() and current:
                # A heading owns the following paragraphs, so blank lines
                # inside a headed section do not split the section early.
                if not _HEADING_RE.match(current[0]):
                    chunks.append("\n".join(current).strip())
                    current = []
                else:
                    current.append(line)
            elif line.strip() or current:
                current.append(line)
        if current:
            chunks.append("\n".join(current).strip())
        result = []
        for chunk in chunks:
            if estimate_tokens(chunk, "openai", "gpt-4o-mini") <= self.chunk_size:
                result.append(chunk)
                continue
            words = chunk.split()
            step = max(1, self.chunk_size - self.chunk_overlap)
            for start in range(0, len(words), step):
                part = " ".join(words[start:start + self.chunk_size])
                if part:
                    result.append(part)
        return result or ([text.strip()] if text.strip() else [])

    def retrieve_relevant_chunks(self, chunks: list[str], query: str) -> list[str]:
        if not chunks:
            return []
        query_words = self._words(query)
        ranked = []
        for index, chunk in enumerate(chunks):
            words = self._words(chunk)
            score = len(words & query_words) / max(1, len(query_words))
            if _HEADING_RE.search(chunk[:120]):
                score += 0.05
            ranked.append((score, -index, chunk))
        ranked.sort(reverse=True)
        selected = [chunk for score, _, chunk in ranked if score > self.threshold][:self.max_chunks]
        if not selected:
            selected = [ranked[0][2]]
        output, used = [], 0
        for chunk in selected:
            tokens = estimate_tokens(chunk, "openai", "gpt-4o-mini")
            if output and used + tokens > self.max_tokens:
                continue
            if not output and tokens > self.max_tokens:
                words = chunk.split()
                chunk = " ".join(words[:max(1, self.max_tokens * 4)])
                tokens = estimate_tokens(chunk, "openai", "gpt-4o-mini")
            output.append(chunk)
            used += tokens
        return output

    def calculate_statistics(self, original: str, optimized: str, provider: str, model: str) -> DocumentSelection:
        original_tokens = estimate_tokens(original, provider, model)
        optimized_tokens = estimate_tokens(optimized, provider, model)
        saved = max(0, original_tokens - optimized_tokens)
        before = estimate_input_cost(original_tokens, provider, model)
        after = estimate_input_cost(optimized_tokens, provider, model)
        return DocumentSelection(optimized, original_tokens, optimized_tokens, saved, round((saved / original_tokens) * 100, 2) if original_tokens else 0.0, before, after, round(max(0.0, before - after), 8), 0, 0, 0)

    @staticmethod
    def _words(value: str) -> set[str]:
        return {word.lower() for word in _WORD_RE.findall(value or "")}

    @staticmethod
    def _deduplicate(chunks: list[str]) -> list[str]:
        seen, output = set(), []
        for chunk in chunks:
            normalized = re.sub(r"\s+", " ", chunk).strip().lower()
            if not normalized or _PAGE_NUMBER_RE.match(normalized) or normalized in seen:
                continue
            seen.add(normalized)
            output.append(chunk)
        return output

    @staticmethod
    def _document_from_prompt(prompt: str):
        match = _FILE_RE.search(prompt or "")
        if not match:
            return None
        name, content = match.group("name"), match.group("content")
        query = prompt[:match.start()].strip()
        prefix = f"{query}\n\nPlease analyze this file ({name}):" if query else f"Please analyze this file ({name}):"
        return name, content, query, prefix

    @staticmethod
    def _first_document(documents: list[dict], query: str):
        item = documents[0]
        raw = item.get("content", "")
        if item.get("data"):
            raw = base64.b64decode(item["data"])
        name = item.get("name", "document.txt")
        effective_query = item.get("query") or query
        return name, raw, effective_query, item.get("prefix") or f"{effective_query}\n\nPlease analyze the relevant sections from {name}:"

    @staticmethod
    def _empty(prompt, provider, model, elapsed):
        return DocumentSelection(prompt, 0, 0, 0, 0.0, 0.0, 0.0, 0.0, 0, 0, elapsed)
