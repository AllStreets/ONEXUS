# tests/modules/test_carve.py
import pytest
from unittest.mock import AsyncMock
from nexus.modules.carve import CarveModule, RefactorSuggestion


@pytest.fixture
def carve():
    return CarveModule()


def test_carve_attrs(carve):
    assert carve.name == "carve"
    assert carve.version == "0.1.0"


def test_measure_complexity_simple(carve):
    code = "x = 1\ny = 2\nprint(x + y)"
    metrics = carve.measure_complexity(code)
    assert metrics["total_lines"] == 3
    assert metrics["code_lines"] == 3
    assert metrics["complexity_rating"] == "low"


def test_measure_complexity_counts_functions(carve):
    code = "def foo():\n    pass\n\ndef bar():\n    pass\n\nasync def baz():\n    pass\n"
    metrics = carve.measure_complexity(code)
    assert metrics["functions"] == 3


def test_measure_complexity_counts_branches(carve):
    code = "\n".join([
        "if a:", "    pass",
        "elif b:", "    pass",
        "else:", "    pass",
        "for i in x:", "    pass",
        "while True:", "    break",
        "try:", "    pass",
        "except:", "    pass",
    ])
    metrics = carve.measure_complexity(code)
    assert metrics["branches"] >= 7
    assert metrics["complexity_rating"] == "medium" or metrics["complexity_rating"] == "high"


def test_measure_complexity_high(carve):
    branches = "\n".join(f"if x == {i}:\n    pass" for i in range(20))
    metrics = carve.measure_complexity(branches)
    assert metrics["complexity_rating"] == "high"


def test_measure_complexity_max_nesting(carve):
    code = "if a:\n    if b:\n        if c:\n            if d:\n                pass"
    metrics = carve.measure_complexity(code)
    assert metrics["max_nesting"] == 4


def test_find_suggestions_deep_nesting(carve):
    code = "if a:\n    if b:\n        if c:\n            if d:\n                x = 1"
    suggestions = carve.find_suggestions(code)
    assert any(s.category == "Reduce Nesting" for s in suggestions)


def test_find_suggestions_long_function(carve):
    lines = ["def long_func():"]
    lines.extend(["    x = 1"] * 35)
    code = "\n".join(lines)
    suggestions = carve.find_suggestions(code)
    assert any(s.category == "Extract Function" for s in suggestions)


def test_find_suggestions_chained_elif(carve):
    lines = ["if x == 'a':", "    pass"]
    for i in range(5):
        lines.extend([f"elif x == '{chr(98 + i)}':", "    pass"])
    code = "\n".join(lines)
    suggestions = carve.find_suggestions(code)
    assert any(s.category == "Replace Conditionals" for s in suggestions)


def test_find_suggestions_clean_code(carve):
    code = "def foo():\n    return 42\n\ndef bar():\n    return 99\n"
    suggestions = carve.find_suggestions(code)
    # Clean short code should produce no suggestions (or very few)
    nesting_or_extract = [s for s in suggestions if s.category in ("Reduce Nesting", "Extract Function", "Replace Conditionals")]
    assert len(nesting_or_extract) == 0


@pytest.mark.asyncio
async def test_handle_returns_analysis(carve):
    context = {"llm": None, "engram": None}
    code = "def foo():\n    if a:\n        if b:\n            if c:\n                if d:\n                    pass"
    result = await carve.handle(code, context)
    assert "[Carve]" in result
    assert "Complexity" in result


@pytest.mark.asyncio
async def test_handle_with_llm(carve):
    mock_llm = AsyncMock()
    mock_llm.complete.return_value = "def foo():\n    return 42"
    context = {"llm": mock_llm, "engram": None}
    result = await carve.handle("def foo():\n    x = 42\n    return x", context)
    assert "[Carve]" in result
    mock_llm.complete.assert_called_once()


@pytest.mark.asyncio
async def test_handle_stores_history(carve):
    context = {"llm": None, "engram": None}
    await carve.handle("x = 1", context)
    assert len(carve._history) == 1
