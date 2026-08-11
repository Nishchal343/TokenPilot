from app.optimizers.document_optimizer import DocumentOptimizer
from app.ai.routing import ProviderCandidate
from app.ai.service import ChatService
from unittest.mock import patch


def optimizer(**kwargs):
    return DocumentOptimizer(max_tokens=kwargs.pop("max_tokens", 500), chunk_size=kwargs.pop("chunk_size", 80), max_chunks=kwargs.pop("max_chunks", 3), threshold=kwargs.pop("threshold", 0.05), **kwargs)


def test_selects_relevant_markdown_section_and_preserves_formatting():
    prompt = "Explain JWT authentication.\n\nPlease analyze this file (guide.md):\n\n# JWT Authentication\nUse bearer tokens and validate claims.\n\n# Docker\nBuild the image with docker compose."
    result = optimizer().optimize_document(prompt, "openai", "gpt-4o-mini")
    assert "JWT Authentication" in result.prompt
    assert "docker compose" not in result.prompt
    assert result.saved_tokens > 0


def test_deduplicates_repeated_headers_and_page_numbers():
    text = "Header\n\nJWT section details.\n\nHeader\n\nJWT section details.\n\nPage 1\n\nPage 1"
    chunks = optimizer()._deduplicate(optimizer().chunk_document(text))
    assert len(chunks) < len(optimizer().chunk_document(text))
    assert all(chunk.strip() != "Page 1" for chunk in chunks)


def test_preserves_tables_code_urls_and_structured_text():
    text = "# API\n\n| Name | Value |\n| --- | --- |\n| url | https://example.com |\n\n```python\nvalidate_jwt()\n```\n\n{\"issuer\": \"tokenpilot\"}"
    result = optimizer(max_chunks=5).optimize_document(f"Explain the API URL and validation code.\n\nPlease analyze this file (spec.md):\n\n{text}", "openai", "gpt-4o-mini")
    assert "https://example.com" in result.prompt
    assert "validate_jwt()" in result.prompt


def test_supports_docx_text_extraction_without_frontend_changes():
    import io
    import zipfile

    xml = '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>JWT policy</w:t></w:r></w:p></w:body></w:document>'
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("word/document.xml", xml)
    assert "JWT policy" in optimizer().extract_text(stream.getvalue(), "policy.docx")


def test_statistics_are_calculated_from_original_and_selected_text():
    result = optimizer().calculate_statistics("one two three four", "one two", "openai", "gpt-4o-mini")
    assert result.original_tokens >= result.optimized_tokens
    assert result.saved_tokens >= 0
    assert result.cost_saved >= 0


def test_service_aggregates_prompt_context_and_document_without_double_counting():
    service = ChatService()
    selected = ProviderCandidate("openai", "gpt-4o-mini", "test-key", "personal", 1)

    class FakeProvider:
        def generate(self, api_key, model, messages):
            assert "JWT authentication" in messages[-1]["content"]
            return "done"

    content = "Explain JWT authentication.\n\nPlease analyze this file (guide.md):\n\n# JWT\nJWT authentication uses bearer tokens.\n\n# Docker\nDocker builds images."
    with patch("app.ai.service.provider_for", return_value=FakeProvider()):
        result = service.generate(content, [], [], selected, [selected])

    report = result.optimization
    assert report["original_tokens"] == report["prompt_original_tokens"] + report["original_context_tokens"] + report["document_original_tokens"]
    assert report["saved_tokens"] == report["prompt_tokens_saved"] + report["context_saved_tokens"] + report["document_tokens_saved"]
    assert report["document_tokens_saved"] > 0
