# tests/modules/test_kindle.py
import pytest
from unittest.mock import AsyncMock
from nexus.agents.kindle import KindleModule, ContentPiece


@pytest.fixture
def kindle():
    return KindleModule()


def test_kindle_attrs(kindle):
    assert kindle.name == "kindle"
    assert kindle.version == "0.1.0"


def test_detect_tone_explicit(kindle):
    assert kindle.detect_tone("Write in a professional tone") == "professional"
    assert kindle.detect_tone("Make it casual") == "casual"
    assert kindle.detect_tone("Use technical language") == "technical"
    assert kindle.detect_tone("Academic style please") == "academic"
    assert kindle.detect_tone("Marketing copy needed") == "marketing"


def test_detect_tone_from_format(kindle):
    assert kindle.detect_tone("Write a blog post about AI") == "casual"
    assert kindle.detect_tone("Create a report on Q3 results") == "professional"
    assert kindle.detect_tone("Write documentation for the API") == "technical"


def test_detect_tone_default(kindle):
    assert kindle.detect_tone("expand this text") == "professional"


def test_detect_format(kindle):
    assert kindle.detect_format("Write a blog post") == "blog"
    assert kindle.detect_format("Create documentation") == "docs"
    assert kindle.detect_format("Draft an email") == "email"
    assert kindle.detect_format("expand this") == "report"


def test_extract_bullets(kindle):
    text = "- First point\n- Second point\n* Third point\n1. Fourth point"
    bullets = kindle.extract_bullets(text)
    assert len(bullets) == 4
    assert "First point" in bullets[0]
    assert "Fourth point" in bullets[3]


def test_extract_bullets_empty(kindle):
    assert kindle.extract_bullets("No bullets here") == []


def test_extract_title_heading(kindle):
    text = "# My Great Title\n- point one\n- point two"
    assert kindle.extract_title(text) == "My Great Title"


def test_extract_title_plain(kindle):
    text = "How to Build Better Software\n- Use TDD\n- Review code"
    assert kindle.extract_title(text) == "How to Build Better Software"


def test_extract_title_fallback(kindle):
    text = "- a\n- b\n- c"
    assert kindle.extract_title(text) == "Untitled"


@pytest.mark.asyncio
async def test_handle_no_bullets_no_llm(kindle):
    context = {"llm": None, "engram": None}
    result = await kindle.handle("expand this text", context)
    assert "Provide bullet points" in result


@pytest.mark.asyncio
async def test_handle_with_bullets_no_llm(kindle):
    context = {"llm": None, "engram": None}
    text = "# AI Trends\n- Machine learning growth\n- LLM adoption\n- Edge computing"
    result = await kindle.handle(text, context)
    assert "[Kindle]" in result
    assert "Content Outline" in result
    assert "AI Trends" in result
    assert len(kindle._pieces) == 1


@pytest.mark.asyncio
async def test_handle_with_llm(kindle):
    mock_llm = AsyncMock()
    mock_llm.complete.return_value = "# AI Trends\n\nMachine learning is transforming industries..."
    context = {"llm": mock_llm, "engram": None}
    text = "Write a blog post\n- AI trends\n- LLM adoption"
    result = await kindle.handle(text, context)
    assert "[Kindle]" in result
    assert "Generated" in result
    mock_llm.complete.assert_called_once()


@pytest.mark.asyncio
async def test_handle_stores_piece(kindle):
    context = {"llm": None, "engram": None}
    text = "- point one\n- point two"
    await kindle.handle(text, context)
    assert len(kindle._pieces) == 1
    assert kindle._pieces[0].tone == "professional"
