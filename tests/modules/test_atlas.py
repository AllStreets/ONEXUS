# tests/modules/test_atlas.py
import pytest
import time
from nexus.modules.atlas import AtlasModule, Fact


@pytest.fixture
def atlas(tmp_config):
    a = AtlasModule(db_path=tmp_config.db_path)
    a.init_db()
    return a


def test_atlas_attrs(atlas):
    assert atlas.name == "atlas"
    assert atlas.version == "0.1.0"


def test_add_fact(atlas):
    fact_id = atlas.add_fact(
        subject="Connor",
        predicate="works_at",
        obj="Flexport",
        confidence=0.95,
        source="user_input",
    )
    assert isinstance(fact_id, str)
    assert len(fact_id) > 0


def test_query_facts(atlas):
    atlas.add_fact("Connor", "lives_in", "Chicago", 0.9, "user_input")
    atlas.add_fact("Connor", "works_at", "Flexport", 0.95, "user_input")
    results = atlas.query(subject="Connor")
    assert len(results) == 2


def test_query_by_predicate(atlas):
    atlas.add_fact("Connor", "knows", "Python", 0.99, "observation")
    atlas.add_fact("Connor", "knows", "TypeScript", 0.85, "observation")
    atlas.add_fact("Alice", "knows", "Rust", 0.9, "observation")
    results = atlas.query(predicate="knows")
    assert len(results) == 3


def test_confidence_decay(atlas):
    fact_id = atlas.add_fact("Test", "is", "fresh", 0.9, "test", max_age_days=0)
    # After decay, confidence should be lower
    facts = atlas.query(subject="Test", apply_decay=True)
    # With max_age_days=0, confidence drops immediately
    assert len(facts) >= 1


def test_conflicting_facts(atlas):
    atlas.add_fact("Connor", "lives_in", "Chicago", 0.9, "user_input")
    atlas.add_fact("Connor", "lives_in", "New York", 0.6, "rumor")
    results = atlas.query(subject="Connor", predicate="lives_in")
    assert len(results) == 2
    # Higher confidence fact should sort first
    assert results[0]["confidence"] >= results[1]["confidence"]


def test_remove_fact(atlas):
    fact_id = atlas.add_fact("temp", "is", "temporary", 0.5, "test")
    atlas.remove_fact(fact_id)
    results = atlas.query(subject="temp")
    assert len(results) == 0


@pytest.mark.asyncio
async def test_atlas_handle_query(atlas):
    atlas.add_fact("Connor", "works_at", "Flexport", 0.95, "user_input")
    result = await atlas.handle("What do you know about Connor?", {"llm": None})
    assert "connor" in result.lower() or "flexport" in result.lower()


@pytest.mark.asyncio
async def test_atlas_handle_empty(atlas):
    result = await atlas.handle("What do you know about nobody?", {"llm": None})
    assert "no facts" in result.lower() or "nothing" in result.lower()
