"""Tests for GET /api/cortex/modules — the always-on "agents on duty" roster."""


def test_modules_route_returns_roster(client):
    r = client.get("/api/cortex/modules")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"modules", "on_duty", "count"}
    # The full built-in cognitive roster is registered at kernel boot.
    assert "council" in body["modules"]
    assert "specter" in body["modules"]
    assert body["modules"] == sorted(body["modules"])


def test_on_duty_prepends_routing_and_counts(client):
    body = client.get("/api/cortex/modules").json()
    # Cortex's own routing layer is on duty whenever any module is.
    assert body["on_duty"][0] == "routing"
    assert body["on_duty"][1:] == body["modules"]
    assert body["count"] == len(body["on_duty"])
    assert body["count"] >= 2
