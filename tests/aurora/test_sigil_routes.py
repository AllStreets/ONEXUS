"""N1.1 — /api/sigil/detections queryable threat-radar log."""


def test_detections_route_empty(client):
    r = client.get("/api/sigil/detections")
    assert r.status_code == 200
    body = r.json()
    assert body["detections"] == []
    assert body["count"] == 0


def test_detections_reflect_chronicle(client):
    kernel = client.app.state.kernel
    kernel.chronicle.log("sigil", "detection", {
        "rule": "denied_burst", "severity": "high", "module": "wraith",
        "provenance": "ab" * 32,
    })
    r = client.get("/api/sigil/detections")
    body = r.json()
    assert body["count"] == 1
    d = body["detections"][0]
    assert d["rule"] == "denied_burst"
    assert d["module"] == "wraith"
    assert "timestamp" in d and "event_id" in d


def test_detections_rule_filter(client):
    kernel = client.app.state.kernel
    kernel.chronicle.log("sigil", "detection", {"rule": "denied_burst", "module": "wraith"})
    kernel.chronicle.log("sigil", "detection", {"rule": "trust_collapse", "module": "echo"})
    r = client.get("/api/sigil/detections?rule=trust_collapse")
    body = r.json()
    assert body["count"] == 1
    assert body["detections"][0]["rule"] == "trust_collapse"
