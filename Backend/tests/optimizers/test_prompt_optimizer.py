from app.config.model_pricing import estimate_input_cost, estimate_tokens
from app.optimizers.prompt_optimizer import PromptOptimizer


def optimizer():
    return PromptOptimizer()


def optimize(value):
    return optimizer().optimize(value, "openai", "gpt-4o-mini")


def test_removes_whitespace_and_repeated_words():
    result = optimize("  Explain   this   clearly clearly.  ")
    assert result.optimized == "Explain this clearly."
    assert result.saved_tokens > 0


def test_collapses_blank_lines_and_duplicate_sentences():
    result = optimize("First sentence. First sentence.\n\n\nSecond sentence.")
    assert result.optimized == "First sentence.\n\nSecond sentence."


def test_preserves_markdown_and_code_blocks():
    prompt = "# Title\n\nUse this:\n```python\n  x  =  1\nprint(x)\n```"
    result = optimize(prompt)
    assert result.optimized.startswith("# Title\n\nUse this:")
    assert "  x  =  1\nprint(x)" in result.optimized


def test_preserves_json_sql_urls_and_paths():
    json_text = '{"name": "TokenPilot", "items": [1, 2]}'
    assert optimize(json_text).optimized == json_text
    sql = "SELECT  *  FROM users WHERE id = 1;"
    assert optimize(sql).optimized == sql
    prompt = "Open https://example.com/a  and C:\\work\\file.py"
    assert optimize(prompt).optimized == "Open https://example.com/a and C:\\work\\file.py"


def test_statistics_and_costs_are_consistent():
    result = optimize("  hello   world  ")
    assert result.original_tokens == estimate_tokens(result.original, "openai", "gpt-4o-mini")
    assert result.optimized_tokens == estimate_tokens(result.optimized, "openai", "gpt-4o-mini")
    assert result.cost_before == estimate_input_cost(result.original_tokens, "openai", "gpt-4o-mini")
    assert result.cost_after == estimate_input_cost(result.optimized_tokens, "openai", "gpt-4o-mini")
    assert result.cost_saved >= 0


def test_verbose_natural_language_prompt_gets_semantically_compressed():
    prompt = ("I am currently learning about REST APIs in computer science and I would like you to provide me with a detailed explanation of what REST APIs are, "
              "how they work, what the main principles and constraints of REST architecture are, how HTTP methods such as GET, POST, PUT, PATCH, and DELETE are used, "
              "what HTTP status codes mean in this context, and finally provide a simple practical example showing how a client communicates with a REST API server.")
    result = optimize(prompt)
    assert result.optimization_accepted is True
    assert result.optimized_tokens < result.original_tokens
    assert "GET, POST, PUT, PATCH, and DELETE" in result.optimized
    assert "principles/constraints" in result.optimized


def test_semantic_compression_preserves_explicit_constraints():
    result = optimize("I would like you to please explain in detail REST APIs. Give exactly 3 examples and keep the answer under 200 words.")
    assert "exactly 3 examples" in result.optimized
    assert "under 200 words" in result.optimized
    assert result.optimized_tokens <= result.original_tokens


def test_semantic_compression_does_not_change_code_or_structured_content():
    code = "Explain this code:\n```python\n  value = 1\n```"
    assert optimize(code).optimized == code
    assert optimize('{"request": "Explain this in detail"}').optimized == '{"request": "Explain this in detail"}'


def test_semantic_compression_reduces_prose_around_untouched_code():
    code = "```python\napp.run(debug=True)\n```"
    prompt = "I would like you to provide me with a detailed explanation of this code and explain in order to show how it works:\n\n" + code
    result = optimize(prompt)
    assert code in result.optimized
    assert result.optimized_tokens < result.original_tokens
