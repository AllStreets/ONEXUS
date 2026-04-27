# tests/modules/test_prism.py
import pytest
from nexus.modules.prism import PrismModule, Insight


@pytest.fixture
def prism():
    return PrismModule()


def test_prism_attrs(prism):
    assert prism.name == "prism"
    assert prism.version == "0.1.0"


def test_add_observation(prism):
    prism.add_observation(
        domain="calendar",
        content="Meeting with Acme Corp at 3pm",
        tags=["meeting", "acme"],
    )
    assert len(prism.list_observations()) == 1


def test_synthesize_finds_connection(prism):
    prism.add_observation("calendar", "Flight to NYC on Friday", ["travel", "nyc"])
    prism.add_observation("weather", "Hurricane warning for NYC this weekend", ["weather", "nyc", "alert"])
    prism.add_observation("crm", "Meeting with NYC client scheduled for Saturday", ["meeting", "nyc", "client"])

    insights = prism.synthesize()
    assert len(insights) >= 1
    # Should connect NYC travel + hurricane + meeting
    assert any("nyc" in i.tags for i in insights)


def test_synthesize_no_connection(prism):
    prism.add_observation("calendar", "Dentist appointment", ["health"])
    prism.add_observation("code", "Fixed linting errors", ["code", "cleanup"])
    insights = prism.synthesize()
    # No shared tags, no connection
    assert len(insights) == 0


def test_insight_has_domains(prism):
    prism.add_observation("email", "Vendor mentioned price increase", ["vendor", "pricing"])
    prism.add_observation("finance", "Q3 budget is tight", ["budget", "pricing"])
    insights = prism.synthesize()
    assert len(insights) >= 1
    assert len(insights[0].domains) >= 2


def test_clear_observations(prism):
    prism.add_observation("test", "data", ["tag"])
    prism.clear_observations()
    assert len(prism.list_observations()) == 0


@pytest.mark.asyncio
async def test_prism_handle_with_insights(prism):
    prism.add_observation("calendar", "Flight to London", ["travel", "london"])
    prism.add_observation("news", "London tube strike next week", ["london", "transport", "strike"])
    result = await prism.handle("synthesize", {"llm": None})
    assert "london" in result.lower() or "connection" in result.lower() or "insight" in result.lower()


@pytest.mark.asyncio
async def test_prism_handle_no_observations(prism):
    result = await prism.handle("synthesize", {"llm": None})
    assert "no observations" in result.lower() or "no insights" in result.lower()
