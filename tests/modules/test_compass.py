# tests/modules/test_compass.py
import pytest
from unittest.mock import AsyncMock
from nexus.agents.compass import CompassModule


@pytest.fixture
def compass():
    return CompassModule()


def test_compass_attrs(compass):
    assert compass.name == "compass"
    assert compass.version == "0.1.0"


def test_detect_skill_python(compass):
    assert compass.detect_skill("I want to learn Python") == "python"


def test_detect_skill_rust(compass):
    assert compass.detect_skill("Help me learn Rust programming") == "rust"


def test_detect_skill_unknown(compass):
    result = compass.detect_skill("I want to learn kubernetes")
    assert "kubernetes" in result.lower()


def test_detect_level_beginner(compass):
    assert compass.detect_level("I'm a complete beginner") == "beginner"


def test_detect_level_advanced(compass):
    assert compass.detect_level("I want to master advanced topics") == "advanced"


def test_detect_level_default(compass):
    assert compass.detect_level("teach me stuff") == "intermediate"


def test_generate_roadmap_python(compass):
    roadmap = compass.generate_roadmap("python", "beginner")
    assert roadmap.skill == "python"
    assert roadmap.total_weeks > 0
    assert len(roadmap.milestones) >= 3


def test_generate_roadmap_unknown(compass):
    roadmap = compass.generate_roadmap("haskell", "beginner")
    assert roadmap.skill == "haskell"
    assert len(roadmap.milestones) >= 3


@pytest.mark.asyncio
async def test_handle_returns_roadmap(compass):
    context = {"llm": None, "engram": None}
    result = await compass.handle("I want to learn Python from scratch", context)
    assert "[Compass]" in result
    assert "Python" in result
    assert "Phase" in result


@pytest.mark.asyncio
async def test_handle_stores_roadmap(compass):
    context = {"llm": None, "engram": None}
    await compass.handle("Learn Rust", context)
    assert len(compass._roadmaps) == 1
