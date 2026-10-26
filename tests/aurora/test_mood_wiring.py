"""Tests that kernel Pulse events update the mood engine (Phase 5 T10)."""

import pytest


def test_mood_observe_still_works(client):
    """T4's /api/mood/observe path still works after T10 wiring."""
    r = client.post("/api/mood/observe", json={"trust_collapse": True})
    assert r.status_code == 200
    assert r.json()["mood"] == "alert"


def test_server_pulse_subscribers_registered(client):
    """The aurora server should expose evidence the mood wiring is in place
    by some inspection — e.g., calling /api/mood/current right after startup
    returns a valid response (smoke check that the lifespan ran)."""
    r = client.get("/api/mood/current")
    assert r.status_code == 200
    assert "mood" in r.json()


def test_mood_signals_initialized_on_startup(client):
    """After lifespan, app.state.mood_signals should be set and
    /api/mood/current should return a valid mood string."""
    r = client.get("/api/mood/current")
    assert r.status_code == 200
    body = r.json()
    valid_moods = {
        "calm_focus", "deep_flow", "routing", "deliberating",
        "creative", "reflective", "watchful", "alert",
    }
    assert body["mood"] in valid_moods
    assert isinstance(body.get("drift_seconds"), int)
    assert "reason" in body


def _mood_after(client, predicate, tries=40):
    import time
    for _ in range(tries):
        mood = client.get("/api/mood/current").json()["mood"]
        if predicate(mood):
            return mood
        time.sleep(0.05)
    return mood


def test_revoking_an_agent_turns_the_shell_alert(client):
    """A revoke drops trust to 0 and collapses grants; the README and the
    trust diagram promise the shell turns to alert. The Pulse handler used to
    latch the flag without a timestamp, so the TTL treated it as stale and the
    mood never changed."""
    with client:
        assert client.get("/api/mood/current").json()["mood"] == "calm_focus"
        assert client.post("/api/trust/specter/revoke").json()["revoked"] is True
        assert _mood_after(client, lambda m: m == "alert") == "alert"


def test_a_rise_below_half_is_not_a_collapse(client):
    """Modules start at 0.30; nudging one up to 0.34 must not raise the alarm."""
    with client:
        client.post("/api/trust/oracle/adjust", json={"delta": 0.04, "reason": "test"})
        assert _mood_after(client, lambda m: m == "alert", tries=10) == "calm_focus"


def test_a_route_sets_the_active_agent_for_the_mood(client):
    """Cortex publishes its routing decisions as kernel.route. The mood
    listener was subscribed to cortex.route, a topic nothing publishes, so a
    route never reached the mood engine."""
    import asyncio
    import time

    from nexus.kernel.pulse import Message

    with client:
        kernel = client.app.state.kernel
        client.portal.call(
            kernel.pulse.publish,
            Message(topic="kernel.route", source="cortex", payload={"target": "council"}),
        )
        for _ in range(40):
            if getattr(client.app.state.mood_signals, "active_agent", None) == "council":
                break
            time.sleep(0.05)
        assert client.app.state.mood_signals.active_agent == "council"
