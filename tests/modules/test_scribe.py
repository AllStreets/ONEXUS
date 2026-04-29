# tests/modules/test_scribe.py
import pytest
from unittest.mock import AsyncMock
from nexus.modules.scribe import ScribeModule


@pytest.fixture
def scribe():
    return ScribeModule()


def test_scribe_attrs(scribe):
    assert scribe.name == "scribe"
    assert scribe.version == "0.1.0"
    assert scribe.description


def test_extract_participants(scribe):
    transcript = "Alice: I think we should proceed.\nBob: Agreed, let's do it.\nAlice: Great."
    participants = scribe._extract_participants(transcript)
    assert "Alice" in participants
    assert "Bob" in participants


def test_extract_action_items(scribe):
    text = "We decided to proceed. John will send the report by Friday. Sarah needs to review the contract."
    items = scribe._extract_action_items(text)
    assert len(items) >= 1
    assert any("report" in item.lower() or "review" in item.lower() for item in items)


def test_extract_decisions(scribe):
    text = "We decided to use Python for the backend. The team agreed that Friday is the deadline."
    decisions = scribe._extract_decisions(text)
    assert len(decisions) >= 1
    assert any("python" in d.lower() or "friday" in d.lower() for d in decisions)


def test_store_and_list_records(scribe):
    from nexus.modules.scribe import MeetingRecord
    record = MeetingRecord(
        summary="Test meeting",
        action_items=["Do thing"],
        decisions=["Decided stuff"],
        key_points=["Key point"],
        participants=["Alice"],
    )
    scribe.store_record(record)
    assert len(scribe.list_records()) == 1


@pytest.mark.asyncio
async def test_handle_returns_string(scribe):
    context = {"llm": None, "engram": None, "pulse": None}
    result = await scribe.handle("Alice: Let's launch on Monday.\nBob: Agreed.", context)
    assert isinstance(result, str)
    assert "[Scribe]" in result


@pytest.mark.asyncio
async def test_handle_with_llm(scribe):
    llm = AsyncMock()
    llm.complete.return_value = (
        "SUMMARY\nTeam discussed launch timeline.\n"
        "KEY POINTS\n- Launch set for Monday\n- Need QA sign-off\n"
        "ADDITIONAL ACTIONS\n- Run final regression tests\n"
        "ADDITIONAL DECISIONS\n"
    )
    context = {"llm": llm, "engram": None, "pulse": None}
    result = await scribe.handle(
        "Alice: We should launch Monday.\nBob: Agreed, needs QA first.", context
    )
    assert "launch" in result.lower() or "monday" in result.lower() or "Scribe" in result
    llm.complete.assert_called_once()


@pytest.mark.asyncio
async def test_handle_stores_record(scribe):
    context = {"llm": None, "engram": None, "pulse": None}
    await scribe.handle("Simple meeting notes.", context)
    assert len(scribe.list_records()) == 1
