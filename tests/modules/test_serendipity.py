# tests/modules/test_serendipity.py
import pytest
from nexus.modules.serendipity import SerendipityModule, SurprisingConnection


@pytest.fixture
def serendipity():
    return SerendipityModule()


def test_serendipity_attrs(serendipity):
    assert serendipity.name == "serendipity"
    assert serendipity.version == "0.1.0"


def test_record_focus_area(serendipity):
    serendipity.record_focus("supply chain logistics")
    serendipity.record_focus("warehouse optimization")
    assert len(serendipity.list_focus_areas()) == 2


def test_add_distant_knowledge(serendipity):
    serendipity.add_knowledge(
        domain="neuroscience",
        content="Neural pathways optimize routing efficiency similar to logistics networks",
        tags=["routing", "optimization", "networks"],
    )
    assert len(serendipity.list_knowledge()) == 1


def test_find_surprising_connections(serendipity):
    serendipity.record_focus("supply chain logistics")
    serendipity.record_focus("route optimization")
    serendipity.add_knowledge(
        "neuroscience",
        "Neural pathway routing mirrors supply chain optimization patterns",
        ["routing", "optimization", "pathways"],
    )
    serendipity.add_knowledge(
        "biology",
        "Ant colony optimization algorithms derived from foraging behavior",
        ["optimization", "swarm", "logistics"],
    )
    connections = serendipity.find_connections()
    assert len(connections) >= 1
    assert any(isinstance(c, SurprisingConnection) for c in connections)


def test_no_connections_without_knowledge(serendipity):
    serendipity.record_focus("cooking")
    connections = serendipity.find_connections()
    assert len(connections) == 0


def test_surprise_score(serendipity):
    serendipity.record_focus("machine learning")
    serendipity.add_knowledge(
        "archaeology",
        "Stratigraphy uses layered analysis similar to deep learning architectures",
        ["layers", "analysis", "pattern recognition"],
    )
    connections = serendipity.find_connections()
    if connections:
        assert 0.0 <= connections[0].surprise_score <= 1.0


def test_penalizes_obvious(serendipity):
    serendipity.record_focus("machine learning")
    serendipity.add_knowledge("AI", "New ML paper on transformers", ["machine", "learning", "transformers"])
    serendipity.add_knowledge("music", "Bach's fugues use recursive mathematical structures", ["recursive", "structure", "pattern"])
    connections = serendipity.find_connections()
    # The music connection should score higher surprise than the AI one (if AI one even passes)
    if len(connections) >= 2:
        ai_conn = [c for c in connections if "AI" in c.source_domain]
        music_conn = [c for c in connections if "music" in c.source_domain]
        if ai_conn and music_conn:
            assert music_conn[0].surprise_score >= ai_conn[0].surprise_score


@pytest.mark.asyncio
async def test_serendipity_handle(serendipity):
    serendipity.record_focus("logistics")
    serendipity.add_knowledge("biology", "Slime mold optimizes network paths", ["network", "optimization"])
    result = await serendipity.handle("Surprise me", {"llm": None})
    assert "connection" in result.lower() or "surprising" in result.lower() or "biology" in result.lower()


@pytest.mark.asyncio
async def test_serendipity_handle_empty(serendipity):
    result = await serendipity.handle("surprise me", {"llm": None})
    assert "no focus" in result.lower() or "no knowledge" in result.lower() or "nothing" in result.lower()
