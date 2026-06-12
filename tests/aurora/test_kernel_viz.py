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
