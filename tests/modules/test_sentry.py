# tests/modules/test_sentry.py
import pytest
from nexus.modules.sentry import SentryModule, CognitiveState


@pytest.fixture
def sentry():
    return SentryModule()


def test_sentry_attrs(sentry):
    assert sentry.name == "sentry"
    assert sentry.version == "0.1.0"


def test_default_state(sentry):
    state = sentry.get_state()
    assert isinstance(state, CognitiveState)
    assert 0.0 <= state.focus <= 1.0
    assert 0.0 <= state.fatigue <= 1.0
    assert 0.0 <= state.stress <= 1.0
    assert isinstance(state.flow, bool)


def test_update_signal_typing_speed(sentry):
    sentry.update_signal("typing_speed", 0.3)
    state = sentry.get_state()
    # Low typing speed increases fatigue estimate
    assert state.fatigue > 0.0


def test_update_signal_message_frequency(sentry):
    sentry.update_signal("message_frequency", 0.9)
    state = sentry.get_state()
    # High message frequency suggests engagement
    assert state.focus > 0.0


def test_update_signal_time_gap(sentry):
    sentry.update_signal("time_gap", 0.8)
    state = sentry.get_state()
    # Large time gap between messages suggests break/fatigue
    assert state.fatigue > 0.0


def test_flow_state_detection(sentry):
    # Simulate flow conditions: high focus, low fatigue, low stress
    sentry.update_signal("typing_speed", 0.9)
    sentry.update_signal("message_frequency", 0.8)
    sentry.update_signal("time_gap", 0.1)
    state = sentry.get_state()
    assert state.focus > 0.5


def test_state_to_dict(sentry):
    d = sentry.get_state().to_dict()
    assert "focus" in d
    assert "fatigue" in d
    assert "stress" in d
    assert "flow" in d


@pytest.mark.asyncio
async def test_sentry_handle(sentry):
    result = await sentry.handle("How am I doing?", {"llm": None})
    assert "focus" in result.lower() or "state" in result.lower()


@pytest.mark.asyncio
async def test_sentry_handle_with_signal(sentry):
    sentry.update_signal("typing_speed", 0.2)
    result = await sentry.handle("status", {"llm": None})
    assert "fatigue" in result.lower() or "focus" in result.lower()
