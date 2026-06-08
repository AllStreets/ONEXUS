"""End-to-end smoke for Phase 5 Aurora surfaces.

Confirms every surface mounted and the four hash-routes have JS handlers,
the mood endpoint is live, the classic /dashboard is preserved, and the
bespoke iconography is intact (zero emojis).
"""
from __future__ import annotations

import re


def test_aurora_index_loads(client):
    r = client.get("/aurora")
    assert r.status_code == 200
    body = r.text
    # v2 shell — persistent window-chrome layout with sidebar, main, and
    # cockpit rail. The four navigational entry points moved from header
    # buttons into the sidebar and chrome.
    assert 'id="nx-kernel-mark"' in body
    assert 'id="nx-mood-pill"' in body          # mood pill in chrome (toggles cockpit)
    assert 'id="nx-ws-list"' in body            # sidebar workspaces list
    assert 'id="nx-new-ws"' in body             # new workspace entry
    assert 'id="nx-open-catalog"' in body       # catalog entry
    assert 'id="nx-open-settings"' in body      # settings entry
    assert 'id="nx-cockpit-rail"' in body       # persistent cockpit rail


def test_aurora_icons_js_has_all_builtins(client):
    r = client.get("/aurora/static/icons.js")
    body = r.text
    # 10 built-in glyph keys
    for slug in ["council", "specter", "autonomic", "oracle", "wraith",
                 "legacy", "consciousness", "sentry", "echo", "agents"]:
        assert f"{slug}:" in body, f"missing glyph for {slug}"
    assert "KERNEL_MARK" in body
    assert "identityDisc" in body


def test_aurora_app_js_has_four_surface_routes(client):
    r = client.get("/aurora/static/app.js")
    body = r.text
    # v2 renderers — naming evolved: catalog replaces "spatial" as the
    # user-visible label, but the four surfaces remain.
    for marker in ["renderSwitcher", "renderConversation",
                   "toggleCockpitOverlay", "renderCatalog", "renderSettings"]:
        assert marker in body, f"missing {marker}"
    for hash_route in ["#/workspaces", "#/conversation/", "#/catalog", "#/settings"]:
        assert hash_route in body, f"missing route {hash_route}"


def test_no_emojis_in_aurora_assets(client):
    """User preference: bespoke icons, never emojis (see memory:feedback-design-language)."""
    emoji_pattern = re.compile(
        "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F02F]"
    )
    for path in ["/aurora", "/aurora/static/app.js",
                 "/aurora/static/icons.js", "/aurora/static/app.css",
                 "/aurora/static/tokens.css", "/aurora/static/mood.css"]:
        r = client.get(path)
        assert r.status_code == 200
        assert not emoji_pattern.search(r.text), f"emoji found in {path}"


def test_mood_endpoint_returns_valid_state(client):
    r = client.get("/api/mood/current")
    assert r.status_code == 200
    body = r.json()
    assert body["mood"] in {"calm_focus", "deep_flow", "routing", "deliberating",
                            "creative", "reflective", "watchful", "alert"}
    assert body["drift_seconds"] > 0


def test_classic_dashboard_still_works(client):
    """Spec §13.4 — classic dashboard preserved during the transition window."""
    r = client.get("/dashboard")
    assert r.status_code == 200


def test_permission_inbox_endpoints_live(client):
    """The Phase 4 endpoints are reachable from the new server."""
    r = client.get("/api/permissions/pending")
    assert r.status_code == 200
    assert "pending" in r.json()


def test_spatial_aggregator_returns_list(client):
    """The /api/spatial/agents aggregator returns at least the system agents."""
    r = client.get("/api/spatial/agents")
    assert r.status_code == 200
    assert "agents" in r.json()
