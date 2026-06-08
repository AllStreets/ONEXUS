"""Tests for the Cockpit overlay backend."""


def test_cockpit_pulse_rate_returns_window(client):
    r = client.get("/api/cockpit/pulse-rate")
    assert r.status_code == 200
    assert "points" in r.json()


def test_cockpit_snapshot_returns_bundle(client):
    r = client.get("/api/cockpit/snapshot")
    assert r.status_code == 200
    body = r.json()
    for key in ("pulse", "residents", "trust_gradient", "last_route", "chronicle_tail", "network", "engram_stats"):
        assert key in body, f"missing key {key!r}"


def test_aurora_app_js_has_cockpit(client):
    r = client.get("/aurora/static/app.js")
    assert "toggleCockpit" in r.text
    assert "Cockpit" in r.text or "cockpit" in r.text.lower()


def test_aurora_app_css_has_signal_aesthetic(client):
    r = client.get("/aurora/static/app.css")
    assert ".nx-cockpit" in r.text
    assert "scanline" in r.text.lower() or "nx-cockpit-scan" in r.text


def test_aurora_index_has_cockpit_button(client):
    r = client.get("/aurora")
    assert "nx-cockpit-btn" in r.text
