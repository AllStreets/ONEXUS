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


def test_swarm_templates_returns_curated_swarms(client):
    r = client.get("/api/cortex/templates")
    assert r.status_code == 200
    body = r.json()
    assert "templates" in body
    ids = {t["id"] for t in body["templates"]}
    # The four roadmap swarms (VISION-AGENTIC-OS §6) ship by default.
    assert {"research", "build", "monitor", "negotiate"} <= ids


def test_swarm_templates_only_offer_registered_modules(client):
    registered = set(client.get("/api/cortex/modules").json()["modules"])
    for tpl in client.get("/api/cortex/templates").json()["templates"]:
        assert tpl["agents"], f"template {tpl['id']} has no runnable agents"
        # A template must never offer an agent this kernel can't actually run.
        assert set(tpl["agents"]) <= registered
        assert isinstance(tpl["prompt"], str) and tpl["prompt"]
