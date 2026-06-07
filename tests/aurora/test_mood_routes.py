"""Tests for /api/mood/current and /api/mood/observe."""


def test_mood_current_defaults_to_calm_focus(client):
    r = client.get("/api/mood/current")
    assert r.status_code == 200
    body = r.json()
    assert body["mood"] == "calm_focus"
    assert body["drift_seconds"] > 0
    assert "reason" in body


def test_mood_observe_changes_current(client):
    # Force a state change via the observe endpoint, then check current
    r = client.post("/api/mood/observe",
                    json={"trust_collapse": True})
    assert r.status_code == 200
    r2 = client.get("/api/mood/current")
    assert r2.json()["mood"] == "alert"


def test_mood_observe_unknown_field_400(client):
    r = client.post("/api/mood/observe", json={"banana": True})
    assert r.status_code == 400
