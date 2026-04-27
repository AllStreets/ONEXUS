# tests/modules/test_dreamweaver.py
import pytest
from nexus.modules.dreamweaver import DreamweaverModule, SynthesisReport


@pytest.fixture
def dreamweaver():
    return DreamweaverModule()


def test_dreamweaver_attrs(dreamweaver):
    assert dreamweaver.name == "dreamweaver"
    assert dreamweaver.version == "0.1.0"


def test_ingest_events(dreamweaver):
    dreamweaver.ingest("Had a meeting with Acme Corp about logistics partnership")
    dreamweaver.ingest("Read an article about supply chain disruptions in Asia")
    dreamweaver.ingest("Prospect mentioned they need faster shipping in Q4")
    assert dreamweaver.event_count() == 3


def test_synthesize_finds_patterns(dreamweaver):
    dreamweaver.ingest("Meeting: discussed Acme Corp shipping timeline")
    dreamweaver.ingest("News: port delays in Shanghai affecting Q4 deliveries")
    dreamweaver.ingest("Email: prospect needs Q4 delivery guarantee")
    dreamweaver.ingest("Calendar: supply chain review meeting Thursday")
    report = dreamweaver.synthesize()
    assert isinstance(report, SynthesisReport)
    assert len(report.insights) > 0


def test_synthesize_empty(dreamweaver):
    report = dreamweaver.synthesize()
    assert len(report.insights) == 0


def test_morning_brief(dreamweaver):
    dreamweaver.ingest("Closed deal with Acme Corp")
    dreamweaver.ingest("Competitor launched new product")
    dreamweaver.ingest("Team member requested PTO next week")
    brief = dreamweaver.morning_brief()
    assert isinstance(brief, str)
    assert len(brief) > 0


def test_clear_events(dreamweaver):
    dreamweaver.ingest("event 1")
    dreamweaver.ingest("event 2")
    dreamweaver.clear()
    assert dreamweaver.event_count() == 0


@pytest.mark.asyncio
async def test_dreamweaver_handle(dreamweaver):
    dreamweaver.ingest("Important meeting notes about Q4 planning")
    result = await dreamweaver.handle("Generate morning brief", {"llm": None})
    assert "brief" in result.lower() or "insight" in result.lower() or "q4" in result.lower()


@pytest.mark.asyncio
async def test_dreamweaver_handle_empty(dreamweaver):
    result = await dreamweaver.handle("morning brief", {"llm": None})
    assert "no events" in result.lower() or "nothing" in result.lower()
