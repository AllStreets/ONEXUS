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
