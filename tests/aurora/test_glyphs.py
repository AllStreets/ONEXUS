"""Regression tests for Aurora identity glyphs (N3.3 Task 12)."""
from __future__ import annotations

import re

BUILTIN_SLUGS = [
    "council", "specter", "autonomic", "oracle", "wraith", "legacy",
    "consciousness", "sentry", "echo", "agents", "sigil", "atlas",
    "prism", "chronos", "serendipity", "herald", "federation",
]

NEW_GRADIENTS = ["serendipity", "herald", "federation"]


def _icons_text(client):
    r = client.get("/aurora/static/icons.js")
    assert r.status_code == 200
    return r.text


def test_every_builtin_has_a_glyph(client):
    text = _icons_text(client)
    # extract GLYPHS object keys (slug: (s = ...) => `...`)
    for slug in BUILTIN_SLUGS:
        assert re.search(rf"\b{slug}:\s*\(s", text), f"missing glyph for {slug}"


def test_glyphs_are_nontrivial_svgs(client):
    text = _icons_text(client)
    # every built-in glyph body contains an <svg ...> with at least one
    # drawing primitive (path/circle/rect/ellipse/polygon/line)
    for slug in BUILTIN_SLUGS:
        m = re.search(rf"\b{slug}:\s*\(s[^`]*`(.*?)`", text, re.DOTALL)
        assert m, f"could not parse glyph body for {slug}"
        body = m.group(1)
        assert "<svg" in body, f"{slug} glyph has no <svg>"
        assert re.search(r"<(path|circle|rect|ellipse|polygon|line)", body), (
            f"{slug} glyph has no drawing primitive")


def test_new_gradients_present(client):
    text = _icons_text(client)
    for slug in NEW_GRADIENTS:
        assert re.search(rf"\b{slug}:\s*\[", text), f"missing gradient for {slug}"


def test_no_emoji_in_icons(client):
    text = _icons_text(client)
    pat = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF]")
    assert not pat.search(text)
