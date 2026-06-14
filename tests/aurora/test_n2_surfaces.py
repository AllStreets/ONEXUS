"""N2.3 — Aurora surface asset contracts (glyphs, views, no-emoji, reduced-motion)."""
import re

_EMOJI = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF]")


# ── Task 9: identity glyphs + capability sheets ─────────────────────────────

def test_icons_have_prism_glyph(client):
    r = client.get("/aurora/static/icons.js")
    assert "prism:" in r.text
    assert '"#d8b4ff"' in r.text


def test_icons_have_chronos_glyph(client):
    r = client.get("/aurora/static/icons.js")
    assert "chronos:" in r.text
    assert '"#b8c4ff"' in r.text


def test_capability_sheet_covers_prism_and_chronos(client):
    r = client.get("/aurora/static/icons.js").text
    assert "Cross-domain synthesis" in r
    assert "Counterfactual" in r or "counterfactual" in r


def test_no_emoji_in_icons(client):
    assert not _EMOJI.search(client.get("/aurora/static/icons.js").text)


def test_app_js_lists_prism_and_chronos_builtins(client):
    r = client.get("/aurora/static/app.js").text
    assert '"prism"' in r and '"chronos"' in r


# ── Task 10: morning-brief card + atlas graph + chronos timeline views ──────

def test_index_has_morning_brief_mount(client):
    r = client.get("/aurora").text
    assert 'id="nx-morning-brief"' in r
    assert "MORNING BRIEF" in r or "BRIEF" in r


def test_app_js_references_n2_surfaces(client):
    r = client.get("/aurora/static/app.js").text
    for needle in ("/api/dreamweaver/brief", "/api/atlas/graph", "renderAtlasGraph",
                   "renderMorningBrief", "/api/chronos/timeline",
                   "/api/chronos/counterfactual", "renderChronosTimeline",
                   "#/chronos", "#/atlas", "dreamweaver.brief", "/api/events/ws"):
        assert needle in r, f"missing {needle}"


def test_app_css_has_atlas_and_chronos_styles(client):
    r = client.get("/aurora/static/app.css").text
    for needle in (".nx-atlas-node", ".nx-atlas-edge", ".nx-atlas-node.decayed",
                   ".nx-chronos-branch"):
        assert needle in r, f"missing {needle}"
    idx = r.rfind("prefers-reduced-motion")
    assert idx != -1
    tail = r[idx:]
    assert "nx-atlas" in tail or "nx-chronos" in tail


def test_tokens_has_chronos_branch(client):
    r = client.get("/aurora/static/tokens.css").text
    assert "--nx-chronos-branch" in r


def test_no_emoji_in_n2_assets(client):
    for path in ("/aurora", "/aurora/static/app.js", "/aurora/static/app.css",
                 "/aurora/static/icons.js"):
        assert not _EMOJI.search(client.get(path).text), f"emoji in {path}"
