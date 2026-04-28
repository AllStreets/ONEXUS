# tests/modules/test_prism.py
import pytest
from unittest.mock import MagicMock
from nexus.modules.prism import PrismModule, Insight
from nexus.kernel.pulse import Pulse, Message


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


@pytest.mark.asyncio
async def test_prism_on_load_subscribes_to_pulse():
    prism = PrismModule()
    pulse = Pulse()
    await prism.on_load({"pulse": pulse})
    assert prism._sub_id is not None
    assert prism._sub_id in pulse._subs


@pytest.mark.asyncio
async def test_prism_on_unload_unsubscribes():
    prism = PrismModule()
    pulse = Pulse()
    await prism.on_load({"pulse": pulse})
    sub_id = prism._sub_id
    await prism.on_unload({"pulse": pulse})
    assert prism._sub_id is None
    assert sub_id not in pulse._subs


@pytest.mark.asyncio
async def test_prism_auto_collects_from_pulse():
    prism = PrismModule()
    msg = Message(
        topic="cortex.response",
        source="cortex",
        payload={"module": "oracle", "message": "check alerts now", "response": "No active alerts"},
    )
    await prism._on_response(msg)
    assert len(prism.list_observations()) == 1
    obs = prism.list_observations()[0]
    assert obs.domain == "oracle"


@pytest.mark.asyncio
async def test_prism_ignores_own_responses():
    prism = PrismModule()
    msg = Message(
        topic="cortex.response",
        source="cortex",
        payload={"module": "prism", "message": "test", "response": "test"},
    )
    await prism._on_response(msg)
    assert len(prism.list_observations()) == 0
