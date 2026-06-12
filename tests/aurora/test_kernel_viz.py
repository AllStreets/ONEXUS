"""N1.3 — Aurora live kernel visualization asset contracts."""
import re

_EMOJI = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF]")


def test_icons_have_sigil_radar_glyph(client):
    r = client.get("/aurora/static/icons.js")
    assert "sigil:" in r.text          # GLYPHS entry
    assert '"#ffb4a8"' in r.text       # sigil gradient registered


def test_icons_have_atlas_glyph(client):
    r = client.get("/aurora/static/icons.js")
    assert "atlas:" in r.text
    assert '"#7ee8b2"' in r.text


def test_capability_sheet_covers_sigil_and_atlas(client):
    r = client.get("/aurora/static/icons.js")
    assert "Threat radar" in r.text
    assert "World model" in r.text


def test_no_emoji_in_icons(client):
    assert not _EMOJI.search(client.get("/aurora/static/icons.js").text)


def test_index_has_kernel_viz_mount(client):
    r = client.get("/aurora")
    assert 'id="nx-kernel-viz"' in r.text
    assert "KERNEL" in r.text


def test_app_js_subscribes_kernel_topics_over_ws(client):
    r = client.get("/aurora/static/app.js")
    for topic in ("kernel.route", "kernel.gate", "sigil.detection"):
        assert topic in r.text, f"missing topic {topic}"
    assert "/api/events/ws" in r.text   # push transport, no polling


def test_app_js_has_per_module_sparklines_and_veil(client):
    r = client.get("/aurora/static/app.js")
    assert "moduleSparkSVG" in r.text
    assert "nx-emergency-veil" in r.text
    assert "radarPingHTML" in r.text


def test_app_css_kernel_viz_uses_capability_palette(client):
    r = client.get("/aurora/static/app.css")
    assert ".nx-kv-gate-dot" in r.text
    assert "--nx-routine" in r.text
    assert "--nx-trust-collapse" in r.text   # alert palette for emergencies


def test_radar_ping_respects_reduced_motion(client):
    r = client.get("/aurora/static/app.css")
    assert "nx-radar-ping" in r.text
    idx = r.text.rfind("prefers-reduced-motion")
    assert idx != -1
    assert "nx-radar-ping-dot" in r.text[idx:], "no reduced-motion guard for radar ping"


def test_no_emoji_in_kernel_viz_assets(client):
    for path in ("/aurora", "/aurora/static/app.js", "/aurora/static/app.css"):
        assert not _EMOJI.search(client.get(path).text), f"emoji in {path}"
