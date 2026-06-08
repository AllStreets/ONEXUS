"""Tests that /aurora serves the new dashboard shell + static assets."""


def test_aurora_index_returns_html(client):
    r = client.get("/aurora")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "NEXUS" in r.text
    # Bespoke iconography must NOT contain emojis (user preference)
    assert "🚀" not in r.text and "🔥" not in r.text


def test_aurora_serves_tokens_css(client):
    r = client.get("/aurora/static/tokens.css")
    assert r.status_code == 200
    assert "text/css" in r.headers["content-type"]
    assert "--nx-bg" in r.text  # design tokens present


def test_aurora_serves_mood_css(client):
    r = client.get("/aurora/static/mood.css")
    assert r.status_code == 200
    assert "nx-mood-calm-focus" in r.text
    assert "nx-mood-alert" in r.text


def test_aurora_serves_icons_js(client):
    r = client.get("/aurora/static/icons.js")
    assert r.status_code == 200
    assert "KERNEL_MARK" in r.text
    assert "GLYPHS" in r.text


def test_classic_dashboard_still_works(client):
    """The existing /dashboard route must keep working (backward compat per spec §13.4)."""
    r = client.get("/dashboard")
    assert r.status_code == 200
