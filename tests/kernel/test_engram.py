import pytest
from nexus.kernel.engram import Engram


@pytest.fixture
def engram(tmp_config):
    e = Engram(tmp_config.db_path)
    e.init_db()
    return e


def test_working_memory_set_get(engram):
    engram.working.set("current_task", "write tests")
    assert engram.working.get("current_task") == "write tests"


def test_working_memory_clear(engram):
    engram.working.set("temp", "data")
    engram.working.clear()
    assert engram.working.get("temp") is None


def test_episodic_store_and_recall(engram):
    engram.episodic.store("Had meeting with Alice about project X", source="calendar")
    results = engram.episodic.recall("meeting Alice")
    assert len(results) >= 1
    assert "Alice" in results[0]["content"]


def test_episodic_recall_with_limit(engram):
    for i in range(10):
        engram.episodic.store(f"Event number {i}", source="test")
    results = engram.episodic.recall("Event", limit=3)
    assert len(results) == 3


def test_episodic_has_timestamp(engram):
    engram.episodic.store("Timestamped event", source="test")
    results = engram.episodic.recall("Timestamped")
    assert "timestamp" in results[0]


def test_semantic_store_and_search(engram):
    engram.semantic.store("Python is a programming language", category="facts")
    engram.semantic.store("The capital of France is Paris", category="facts")
    results = engram.semantic.search("What programming languages exist?", limit=1)
    assert len(results) == 1
    assert "Python" in results[0]["content"]


def test_semantic_store_with_category(engram):
    engram.semantic.store("User prefers dark themes", category="preferences")
    results = engram.semantic.search("theme preference", category="preferences")
    assert len(results) >= 1
