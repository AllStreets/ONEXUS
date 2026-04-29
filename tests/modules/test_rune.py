# tests/modules/test_rune.py
import pytest
from unittest.mock import AsyncMock
from nexus.modules.rune import RuneModule


@pytest.fixture
def rune():
    return RuneModule()


def test_rune_attrs(rune):
    assert rune.name == "rune"
    assert rune.version == "0.1.0"


def test_lookup_common_email(rune):
    pattern = rune.lookup_common("email")
    assert pattern is not None
    assert "@" in pattern


def test_lookup_common_url(rune):
    pattern = rune.lookup_common("url")
    assert pattern is not None
    assert "http" in pattern


def test_lookup_common_nonexistent(rune):
    assert rune.lookup_common("nonexistent") is None


def test_explain_pattern_simple(rune):
    explanation = rune.explain_pattern(r'\d+')
    assert "digit" in explanation
    assert "one or more" in explanation


def test_explain_pattern_groups(rune):
    explanation = rune.explain_pattern(r'(abc)')
    assert "capturing group" in explanation


def test_explain_pattern_quantifier(rune):
    explanation = rune.explain_pattern(r'a{3}')
    assert "exactly 3" in explanation


def test_explain_pattern_char_class(rune):
    explanation = rune.explain_pattern(r'[abc]')
    assert "any of" in explanation


def test_test_pattern_matches(rune):
    results = rune.test_pattern(r'\d+', ["123", "abc", "a1b"])
    assert results["123"] is True
    assert results["abc"] is False
    assert results["a1b"] is True


def test_test_pattern_invalid(rune):
    results = rune.test_pattern(r'[invalid', ["test"])
    assert results["test"] is False


def test_validate_pattern_valid(rune):
    valid, msg = rune.validate_pattern(r'\d{3}-\d{4}')
    assert valid is True


def test_validate_pattern_invalid(rune):
    valid, msg = rune.validate_pattern(r'[unclosed')
    assert valid is False
    assert "Invalid" in msg


def test_detect_intent(rune):
    assert rune.detect_intent("explain this regex") == "explain"
    assert rune.detect_intent("test this pattern") == "test"
    assert rune.detect_intent("build a pattern for emails") == "build"
    assert rune.detect_intent("show common patterns") == "lookup"


@pytest.mark.asyncio
async def test_handle_lookup(rune):
    context = {"llm": None, "engram": None}
    result = await rune.handle("show common email pattern", context)
    assert "[Rune]" in result
    assert "email" in result.lower()


@pytest.mark.asyncio
async def test_handle_explain(rune):
    context = {"llm": None, "engram": None}
    result = await rune.handle("explain this regex: '\\d{3}-\\d{4}'", context)
    assert "[Rune]" in result
    assert "digit" in result.lower() or "Pattern" in result


@pytest.mark.asyncio
async def test_handle_build_no_llm(rune):
    context = {"llm": None, "engram": None}
    result = await rune.handle("build a pattern for email addresses", context)
    assert "[Rune]" in result


@pytest.mark.asyncio
async def test_handle_stores_history(rune):
    context = {"llm": None, "engram": None}
    await rune.handle("explain regex '\\w+'", context)
    assert len(rune._history) == 1
