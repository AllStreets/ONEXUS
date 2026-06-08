"""T5 — Trust event temperature overlays: CSS + JS invariants."""


def test_trust_wash_rising_class_in_css(client):
    r = client.get("/aurora/static/mood.css")
    assert r.status_code == 200
    assert "nx-trust-wash-rising" in r.text


def test_trust_wash_falling_class_in_css(client):
    r = client.get("/aurora/static/mood.css")
    assert r.status_code == 200
    assert "nx-trust-wash-falling" in r.text


def test_trust_wash_collapse_class_in_css(client):
    r = client.get("/aurora/static/mood.css")
    assert r.status_code == 200
    assert "nx-trust-wash-collapse" in r.text


def test_nx_wash_fade_keyframe_in_css(client):
    r = client.get("/aurora/static/mood.css")
    assert "nx-wash-fade" in r.text


def test_poll_trust_events_in_app_js(client):
    r = client.get("/aurora/static/app.js")
    assert r.status_code == 200
    assert "pollTrustEvents" in r.text


def test_trust_overlay_logic_present_in_app_js(client):
    """Verify the classify logic (collapse/rising/falling) is in app.js."""
    r = client.get("/aurora/static/app.js")
    assert "nx-trust-wash-collapse" in r.text
    assert "nx-trust-wash-rising" in r.text
    assert "nx-trust-wash-falling" in r.text
