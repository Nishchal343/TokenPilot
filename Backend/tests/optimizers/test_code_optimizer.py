from app.optimizers.code_optimizer import CodeOptimizer


def optimizer(**kwargs):
    return CodeOptimizer(max_tokens=kwargs.pop("max_tokens", 500), max_files=kwargs.pop("max_files", 5), **kwargs)


def test_single_code_block_selects_relevant_function_without_modifying_text():
    code = "```python\ndef calculate_tax(amount):\n    return amount * 0.18\n\ndef unrelated_logging():\n    return 'log'\n```"
    result = optimizer().optimize_code(f"Fix calculate_tax.\n\n{code}", "openai", "gpt-4o-mini")
    assert "def calculate_tax(amount):\n    return amount * 0.18" in result.prompt
    assert "unrelated_logging" not in result.prompt
    assert result.saved_tokens > 0


def test_multiple_files_include_relevant_file_and_direct_dependency():
    files = [
        {"name": "auth.py", "content": "from jwt_helpers import decode_token\n\ndef authenticate(token):\n    return decode_token(token)", "language": "python"},
        {"name": "jwt_helpers.py", "content": "def decode_token(token):\n    return token", "language": "python"},
        {"name": "payments.py", "content": "def charge_card(card):\n    return True", "language": "python"},
    ]
    result = optimizer().optimize_code("Fix JWT authentication", "openai", "gpt-4o-mini", files)
    assert result.files_sent == 2
    assert "jwt_helpers.py" in result.prompt
    assert "payments.py" not in result.prompt


def test_react_and_typescript_languages_are_detected():
    code = "```tsx\nexport function Navbar() { return <nav>Home</nav> }\n```"
    result = optimizer().optimize_code(f"Fix the Navbar component\n\n{code}", "openai", "gpt-4o-mini")
    assert "Navbar" in result.prompt
    assert result.files_received == 1


def test_ignored_directories_are_not_sent():
    files = [
        {"name": "src/auth.py", "content": "def login():\n    pass", "language": "python"},
        {"name": "node_modules/pkg/index.js", "content": "function login() {}", "language": "javascript"},
    ]
    result = optimizer().optimize_code("Fix login", "openai", "gpt-4o-mini", files)
    assert result.files_received == 1
    assert "node_modules" not in result.prompt


def test_code_statistics_are_consistent():
    result = optimizer().calculate_statistics("def one():\n    pass\n\ndef two():\n    pass", "def one():\n    pass", "openai", "gpt-4o-mini")
    assert result.original_tokens >= result.optimized_tokens
    assert result.saved_tokens >= 0
    assert result.cost_saved >= 0
