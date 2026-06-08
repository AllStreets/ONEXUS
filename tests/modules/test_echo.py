# tests/modules/test_echo.py
import pytest
from nexus.modules.echo import EchoModule, BehavioralProfile


@pytest.fixture
def echo():
    return EchoModule()


def test_echo_attrs(echo):
    assert echo.name == "echo"
    assert echo.version == "1.0.0"


def test_observe_text_sample(echo):
    echo.observe("email", "Hey team, quick update on the Flexport integration. We're ahead of schedule and the API looks solid. Let's sync Thursday to finalize.")
    profile = echo.get_profile("email")
    assert isinstance(profile, BehavioralProfile)
    assert profile.sample_count == 1


def test_observe_multiple_samples(echo):
    echo.observe("email", "Quick update — shipping module is done.")
    echo.observe("email", "Following up on yesterday's call. Two action items.")
    echo.observe("email", "FYI the deadline moved to Friday. No blockers on our end.")
    profile = echo.get_profile("email")
    assert profile.sample_count == 3
    assert profile.avg_word_count > 0


def test_profile_captures_vocabulary(echo):
    echo.observe("slack", "lgtm ship it")
    echo.observe("slack", "nice, lgtm")
    echo.observe("slack", "ship it, looks good")
    profile = echo.get_profile("slack")
    assert "lgtm" in profile.top_phrases or "ship" in profile.top_phrases


def test_profile_captures_sentence_length(echo):
    echo.observe("report", "This is a very long and detailed sentence about the quarterly performance metrics and their implications for the next fiscal year.")
    echo.observe("report", "Another comprehensive analysis of the market conditions affecting our supply chain operations across multiple regions.")
    profile = echo.get_profile("report")
    assert profile.avg_sentence_length > 10


def test_list_domains(echo):
    echo.observe("email", "test")
    echo.observe("slack", "test")
    assert set(echo.list_domains()) == {"email", "slack"}


def test_match_style(echo):
    echo.observe("email", "Hey, quick heads up — the build is green. Ship when ready.")
    echo.observe("email", "Quick note: API changes landed. Should be backwards compatible.")
    echo.observe("email", "FYI pushed the hotfix. All tests passing.")
    score = echo.match_style("email", "Hey, just a quick note — PR is up. Looks good to merge.")
    assert isinstance(score, float)
    assert 0.0 <= score <= 1.0


@pytest.mark.asyncio
async def test_echo_handle(echo):
    echo.observe("email", "Test observation")
    result = await echo.handle("Show my behavioral profile", {"llm": None})
    assert "email" in result.lower() or "profile" in result.lower()


@pytest.mark.asyncio
async def test_echo_handle_empty(echo):
    result = await echo.handle("Show my profile", {"llm": None})
    assert "no observations" in result.lower() or "no behavioral" in result.lower()
