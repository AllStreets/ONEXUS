# tests/modules/test_quarry.py
import pytest
from unittest.mock import AsyncMock
from nexus.modules.quarry import QuarryModule


@pytest.fixture
def quarry():
    return QuarryModule()


def test_quarry_attrs(quarry):
    assert quarry.name == "quarry"
    assert quarry.version == "0.1.0"


def test_extract_urls(quarry):
    text = "Visit https://example.com and http://test.org/page for more info"
    urls = quarry.extract_urls(text)
    assert len(urls) == 2
    assert "https://example.com" in urls


def test_extract_urls_deduplicates(quarry):
    text = "https://example.com and again https://example.com"
    assert len(quarry.extract_urls(text)) == 1


def test_extract_links(quarry):
    html = '<a href="https://example.com">Example</a> <a href="/about">About</a>'
    links = quarry.extract_links(html)
    assert len(links) == 2
    assert links[0]["url"] == "https://example.com"
    assert links[0]["text"] == "Example"


def test_extract_links_skips_anchors(quarry):
    html = '<a href="#section">Jump</a>'
    links = quarry.extract_links(html)
    assert len(links) == 0


def test_extract_headings(quarry):
    html = "<h1>Main Title</h1><h2>Subtitle</h2><h3>Section</h3>"
    headings = quarry.extract_headings(html)
    assert len(headings) == 3
    assert headings[0]["level"] == "h1"
    assert headings[0]["text"] == "Main Title"


def test_extract_metadata(quarry):
    html = '<title>My Page</title><meta name="description" content="A test page">'
    meta = quarry.extract_metadata(html)
    assert meta["title"] == "My Page"
    assert meta["description"] == "A test page"


def test_strip_tags(quarry):
    html = "<p>Hello <b>world</b></p><script>evil()</script>"
    text = quarry.strip_tags(html)
    assert "Hello" in text
    assert "world" in text
    assert "evil" not in text
    assert "<" not in text


def test_extract_tables(quarry):
    html = "<table><tr><td>A</td><td>B</td></tr><tr><td>1</td><td>2</td></tr></table>"
    tables = quarry.extract_tables(html)
    assert len(tables) == 1
    assert tables[0][0] == ["A", "B"]
    assert tables[0][1] == ["1", "2"]


@pytest.mark.asyncio
async def test_handle_html_content(quarry):
    context = {"llm": None, "engram": None}
    html = "<html><title>Test</title><h1>Hello</h1><a href='/link'>Click</a></html>"
    result = await quarry.handle(html, context)
    assert "[Quarry]" in result
    assert "Test" in result


@pytest.mark.asyncio
async def test_handle_url_only(quarry):
    context = {"llm": None, "engram": None}
    result = await quarry.handle("Extract data from https://example.com", context)
    assert "[Quarry]" in result
    assert "URLs Detected" in result


@pytest.mark.asyncio
async def test_handle_no_content(quarry):
    context = {"llm": None, "engram": None}
    result = await quarry.handle("extract some data", context)
    assert "Provide HTML" in result


@pytest.mark.asyncio
async def test_handle_stores_extraction(quarry):
    context = {"llm": None, "engram": None}
    html = "<html><title>Test</title><h1>Heading</h1></html>"
    await quarry.handle(html, context)
    assert len(quarry._extractions) == 1
