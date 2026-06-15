"""Aurora v3 responsive layout contract (N3.3 Task 13).

The v3 grid shell + container-query density + accessibility strings must
hold, and the new Herald + federation-sync panels must be present in app.js.
No emoji anywhere in the Aurora assets.
"""
from __future__ import annotations

import re


def _css(client):
    return client.get("/aurora/static/app.css").text


def _js(client):
    return client.get("/aurora/static/app.js").text


def test_grid_shell_present(client):
    css = _css(client)
    assert "grid-template-columns" in css
    assert "minmax(0" in css
    assert "100dvh" in css


def test_container_queries_present(client):
    css = _css(client)
    assert "container-type" in css
    assert "@container" in css


def test_responsive_breakpoints_present(client):
    css = _css(client)
    assert "1440px" in css
    assert "1200px" in css
    assert "980px" in css


def test_accessibility_strings_preserved(client):
    tokens = client.get("/aurora/static/tokens.css").text
    mood = client.get("/aurora/static/mood.css").text
    assert "prefers-reduced-motion" in tokens
    assert "prefers-reduced-data" in tokens
    assert "prefers-contrast" in mood


def test_negotiation_and_sync_panels_present(client):
    js = _js(client)
    assert "herald" in js.lower()
    assert "nx-herald-panel" in js or "renderHerald" in js
    assert "nx-fedsync-panel" in js or "renderFederationSync" in js


def test_no_emoji_in_aurora_assets(client):
    pat = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF]")
    for path in ["/aurora", "/aurora/static/app.css", "/aurora/static/app.js",
                 "/aurora/static/icons.js"]:
        r = client.get(path)
        assert not pat.search(r.text), f"emoji in {path}"
