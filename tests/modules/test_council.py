# tests/modules/test_council.py
import pytest
from nexus.modules.council import CouncilModule, DeliberationResult


@pytest.fixture
def council():
    return CouncilModule()


def test_council_attrs(council):
    assert council.name == "council"
    assert council.version == "0.1.0"
    assert council.description


def test_deliberation_result_fields():
    result = DeliberationResult(
        question="test?",
        recommendation="do it",
        confidence=0.8,
        consensus_view="agreed",
        dissenting_views=["nah"],
        key_uncertainties=["maybe"],
        participants=["specter"],
        rounds=3,
        transcript=[],
    )
    assert result.question == "test?"
    assert result.confidence == 0.8
    assert result.rounds == 3


def test_select_participants_includes_specter(council):
    """Specter (adversarial) is always included."""
    selected = council.select_participants("What should I eat for lunch?")
    assert "specter" in selected


def test_select_participants_min_count(council):
    selected = council.select_participants("Hello")
    assert len(selected) >= 3


def test_select_participants_max_count(council):
    selected = council.select_participants(
        "Should I decide on this risky plan to negotiate a deal about the future timeline and verify the data?"
    )
    assert len(selected) <= 5


def test_select_participants_relevant_modules(council):
    """Temporal question should include sandbox."""
    selected = council.select_participants("What is the future timeline for this project?")
    assert "sandbox" in selected
    assert "specter" in selected


from nexus.modules.specter import SpecterModule
from nexus.modules.sandbox import SandboxModule
from nexus.modules.serendipity import SerendipityModule


@pytest.fixture
def council_with_modules():
    c = CouncilModule()
    c.set_modules({
        "specter": SpecterModule(),
        "sandbox": SandboxModule(),
        "serendipity": SerendipityModule(),
    })
    return c


@pytest.mark.asyncio
async def test_deliberate_runs_rounds(council_with_modules):
    result = await council_with_modules.deliberate(
        question="Should I switch to freelancing?",
        context={"llm": None, "engram": None, "chronicle": None, "pulse": None},
        participants=["specter", "sandbox", "serendipity"],
    )
    assert isinstance(result, DeliberationResult)
    assert result.rounds == 3
    assert len(result.transcript) == 3
    assert result.participants == ["specter", "sandbox", "serendipity"]


@pytest.mark.asyncio
async def test_deliberate_no_modules():
    c = CouncilModule()
    c.set_modules({})
    result = await c.deliberate("test?", context={"llm": None}, participants=["nonexistent"])
    assert result.rounds == 0
    assert result.confidence == 0.0


@pytest.mark.asyncio
async def test_deliberate_transcript_has_responses(council_with_modules):
    result = await council_with_modules.deliberate(
        question="Should I switch to freelancing?",
        context={"llm": None, "engram": None, "chronicle": None, "pulse": None},
        participants=["specter", "chronos"],
    )
    for round_entry in result.transcript:
        assert "round" in round_entry
        assert "responses" in round_entry
        assert len(round_entry["responses"]) > 0


@pytest.mark.asyncio
async def test_deliberate_dissent_from_specter(council_with_modules):
    result = await council_with_modules.deliberate(
        question="Should I invest all savings in a risky contract?",
        context={"llm": None, "engram": None, "chronicle": None, "pulse": None},
        participants=["specter", "chronos", "serendipity"],
    )
    assert len(result.dissenting_views) > 0


@pytest.mark.asyncio
async def test_council_handle(council_with_modules):
    result = await council_with_modules.handle(
        "Deliberate: should I switch careers?",
        {"llm": None, "engram": None, "chronicle": None, "pulse": None},
    )
    assert "[Council]" in result
    assert "Deliberation complete" in result
    assert "Confidence" in result
    assert "Recommendation:" in result


@pytest.mark.asyncio
async def test_council_handle_includes_participants(council_with_modules):
    result = await council_with_modules.handle(
        "Council, weigh the pros and cons of remote work",
        {"llm": None, "engram": None, "chronicle": None, "pulse": None},
    )
    assert "Participants:" in result
    assert "Uncertainties:" in result
