# tests/modules/test_arbiter.py
import pytest
from unittest.mock import AsyncMock
from nexus.agents.arbiter import ArbiterModule


@pytest.fixture
def arbiter():
    return ArbiterModule()


def test_arbiter_attrs(arbiter):
    assert arbiter.name == "arbiter"
    assert arbiter.version == "0.1.0"
    assert arbiter.description


def test_parse_diff(arbiter):
    diff = (
        "diff --git a/file.py b/file.py\n"
        "--- a/file.py\n"
        "+++ b/file.py\n"
        "@@ -1,3 +1,4 @@\n"
        " import os\n"
        "+import sys\n"
        " def main():\n"
        "     pass\n"
    )
    hunks = arbiter._parse_diff(diff)
    assert len(hunks) == 1
    assert hunks[0]["file"] == "file.py"
    assert "import sys" in hunks[0]["added_lines"]


def test_detect_bare_except(arbiter):
    code = "try:\n    risky()\nexcept:\n    pass"
    comments = arbiter._detect_patterns(code)
    assert any(c.category == "Error Handling" for c in comments)


def test_detect_print_statement(arbiter):
    code = "print('debug output')"
    comments = arbiter._detect_patterns(code)
    assert any(c.category == "Code Quality" for c in comments)


def test_detect_long_lines(arbiter):
    code = "x = " + "a" * 130
    comments = arbiter._detect_patterns(code)
    assert any(c.category == "Style" for c in comments)


def test_clean_code_no_issues(arbiter):
    code = "def add(a, b):\n    return a + b"
    comments = arbiter._detect_patterns(code)
    assert len(comments) == 0


@pytest.mark.asyncio
async def test_handle_source_code(arbiter):
    context = {"llm": None, "engram": None}
    result = await arbiter.handle("def safe():\n    return 42", context)
    assert "[Arbiter]" in result
    assert "Source" in result


@pytest.mark.asyncio
async def test_handle_diff(arbiter):
    diff = (
        "diff --git a/app.py b/app.py\n"
        "--- a/app.py\n"
        "+++ b/app.py\n"
        "@@ -1,2 +1,3 @@\n"
        " import os\n"
        "+print('hello')\n"
        " def main(): pass\n"
    )
    context = {"llm": None, "engram": None}
    result = await arbiter.handle(diff, context)
    assert "[Arbiter]" in result
    assert "Diff" in result


@pytest.mark.asyncio
async def test_handle_with_llm(arbiter):
    llm = AsyncMock()
    llm.complete.return_value = "Code looks well-structured. No critical issues found."
    context = {"llm": llm, "engram": None}
    result = await arbiter.handle("def process(data):\n    return data.strip()", context)
    assert "AI Deep Review" in result or "[Arbiter]" in result
    llm.complete.assert_called_once()


@pytest.mark.asyncio
async def test_handle_stores_history(arbiter):
    context = {"llm": None, "engram": None}
    await arbiter.handle("x = 1", context)
    assert len(arbiter._review_history) == 1
