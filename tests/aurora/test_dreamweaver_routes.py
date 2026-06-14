"""N2.2 — /api/dreamweaver brief + run routes."""


def test_run_then_brief_reflects(client):
    r = client.post("/api/dreamweaver/run")
    assert r.status_code == 200
    body = r.json()
    assert "headline" in body
    # a morning_brief chronicle row was written
    kernel = client.app.state.kernel
    assert kernel.chronicle.query(source="dreamweaver", action="morning_brief")
    r2 = client.get("/api/dreamweaver/brief")
    assert r2.status_code == 200
    assert "headline" in r2.json()


def test_run_respects_kill_switch(client, monkeypatch):
    monkeypatch.setenv("NEXUS_DREAMWEAVER", "0")
    r = client.post("/api/dreamweaver/run")
    assert r.status_code == 200
    assert r.json().get("skipped") == "kill_switch"


def test_brief_default_when_none(client):
    r = client.get("/api/dreamweaver/brief")
    assert r.status_code == 200
    body = r.json()
    assert "headline" in body
