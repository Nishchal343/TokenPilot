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
