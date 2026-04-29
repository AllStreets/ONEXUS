# tests/modules/test_mnemonic.py
import pytest
from unittest.mock import AsyncMock
from nexus.agents.mnemonic import MnemonicModule, KnowledgeEntry


@pytest.fixture
def mnemonic():
    return MnemonicModule()


def test_mnemonic_attrs(mnemonic):
    assert mnemonic.name == "mnemonic"
    assert mnemonic.version == "0.1.0"


def test_store_entry(mnemonic):
    entry = mnemonic.store("Test Note", "This is a test note about Python", tags=["python", "test"])
    assert entry.id == 1
    assert entry.title == "Test Note"
    assert "python" in entry.tags


def test_store_auto_tags(mnemonic):
    entry = mnemonic.store("API Guide", "Building REST API endpoints with Python Flask")
    assert "python" in entry.tags
    assert "api" in entry.tags


def test_store_increments_id(mnemonic):
    e1 = mnemonic.store("First", "content")
    e2 = mnemonic.store("Second", "content")
    assert e2.id == e1.id + 1


def test_search_by_keyword(mnemonic):
    mnemonic.store("Python Tips", "Use list comprehensions for clean code")
    mnemonic.store("Rust Intro", "Ownership and borrowing in Rust")
    results = mnemonic.search("python")
    assert len(results) == 1
    assert results[0].title == "Python Tips"


def test_search_title_weighted(mnemonic):
    mnemonic.store("Python Guide", "A guide")
    mnemonic.store("General Tips", "Some python tips here")
    results = mnemonic.search("python")
    # Title match should rank higher
    assert results[0].title == "Python Guide"


def test_search_no_results(mnemonic):
    mnemonic.store("Test", "content")
    results = mnemonic.search("nonexistent")
    assert len(results) == 0


def test_get_entry(mnemonic):
    entry = mnemonic.store("Test", "content")
    found = mnemonic.get(entry.id)
    assert found is not None
    assert found.title == "Test"


def test_get_nonexistent(mnemonic):
    assert mnemonic.get(999) is None


def test_delete_entry(mnemonic):
    entry = mnemonic.store("Test", "content")
    assert mnemonic.delete(entry.id) is True
    assert mnemonic.get(entry.id) is None


def test_delete_nonexistent(mnemonic):
    assert mnemonic.delete(999) is False


def test_list_tags(mnemonic):
    mnemonic.store("A", "content", tags=["python", "api"])
    mnemonic.store("B", "content", tags=["python", "db"])
    tags = mnemonic.list_tags()
    assert tags["python"] == 2
    assert tags["api"] == 1


def test_detect_intent(mnemonic):
    assert mnemonic.detect_intent("remember this fact") == "store"
    assert mnemonic.detect_intent("save this information") == "store"
    assert mnemonic.detect_intent("find my notes on python") == "search"
    assert mnemonic.detect_intent("delete entry 5") == "delete"
    assert mnemonic.detect_intent("list all notes") == "list"
    assert mnemonic.detect_intent("what about databases") == "search"


@pytest.mark.asyncio
async def test_handle_store(mnemonic):
    context = {"llm": None, "engram": None}
    result = await mnemonic.handle("remember: Python uses indentation for blocks", context)
    assert "[Mnemonic]" in result
    assert "Stored" in result
    assert len(mnemonic._entries) == 1


@pytest.mark.asyncio
async def test_handle_search(mnemonic):
    context = {"llm": None, "engram": None}
    mnemonic.store("Python Tips", "Use virtual environments for isolation")
    result = await mnemonic.handle("find python tips", context)
    assert "[Mnemonic]" in result
    assert "Search Results" in result


@pytest.mark.asyncio
async def test_handle_list_empty(mnemonic):
    context = {"llm": None, "engram": None}
    result = await mnemonic.handle("list all notes", context)
    assert "empty" in result


@pytest.mark.asyncio
async def test_handle_list_entries(mnemonic):
    context = {"llm": None, "engram": None}
    mnemonic.store("Note 1", "content")
    mnemonic.store("Note 2", "content")
    result = await mnemonic.handle("list all entries", context)
    assert "2 entries" in result


@pytest.mark.asyncio
async def test_handle_delete(mnemonic):
    context = {"llm": None, "engram": None}
    entry = mnemonic.store("Test", "content")
    result = await mnemonic.handle(f"delete entry {entry.id}", context)
    assert "deleted" in result
