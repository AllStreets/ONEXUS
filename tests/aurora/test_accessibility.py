"""T7 — Accessibility automated invariants."""


def test_prefers_reduced_motion_disables_animation(client):
    r = client.get("/aurora/static/tokens.css")
    assert "prefers-reduced-motion" in r.text
    assert "animation-duration: 0.001ms" in r.text or "animation-duration: 0s" in r.text


def test_prefers_contrast_more_collapses_mesh(client):
    r = client.get("/aurora/static/mood.css")
    assert "prefers-contrast" in r.text


def test_prefers_reduced_data_drops_mesh(client):
    r = client.get("/aurora/static/tokens.css")
    assert "prefers-reduced-data" in r.text


def test_aurora_html_has_lang_attribute(client):
    r = client.get("/aurora")
    assert 'lang="en"' in r.text


def test_aurora_html_has_title(client):
    r = client.get("/aurora")
    assert "<title>ONEXUS</title>" in r.text


def test_no_emojis_in_any_aurora_asset(client):
    import re
    pat = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF]")
    for path in ["/aurora", "/aurora/static/tokens.css", "/aurora/static/mood.css",
                 "/aurora/static/app.css", "/aurora/static/app.js",
                 "/aurora/static/icons.js", "/aurora/static/md.js"]:
        r = client.get(path)
        assert not pat.search(r.text), f"emoji found in {path}"
