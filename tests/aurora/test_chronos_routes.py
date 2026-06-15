"""N2.2 — /api/chronos timeline + counterfactual routes."""


def _seed(kernel):
    c = kernel.chronicle
    c.log("aegis", "permission_granted",
          {"agent_slug": "wraith", "capability": "fs.write.workspace"})
    c.log("cortex", "route", {"target": "wraith", "message_preview": "write report"})
    c.log("cortex", "response", {"module": "wraith", "response_preview": "wrote report.md"})


def test_timeline_route(client):
    _seed(client.app.state.kernel)
    r = client.get("/api/chronos/timeline")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] >= 3
    assert any(d["branch_point"] for d in body["timeline"])


def test_counterfactual_by_selector(client):
    _seed(client.app.state.kernel)
    r = client.post("/api/chronos/counterfactual",
                    json={"module": "wraith", "action": "permission_granted"})
    assert r.status_code == 200
    body = r.json()
    assert body["flipped"]["module"] == "wraith"
    pruned = {a["module"] for a in body["would_not_have_happened"]}
    assert pruned == {"wraith"}


def test_counterfactual_unknown_event(client):
    _seed(client.app.state.kernel)
    r = client.post("/api/chronos/counterfactual", json={"event_id": "does-not-exist"})
    assert r.status_code == 200
    assert r.json()["flipped"] is None
