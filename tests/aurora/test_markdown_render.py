"""FIX 1 — escape-first markdown rendering for agent messages (md.js).

Two layers of coverage:

1. Asset/contract tests via the FastAPI client — md.js ships, app.js wires
   it into renderMessageHTML, app.css styles the md elements.
2. Behavioural tests of the renderer itself, executed in Node (the renderer
   is an ES module with zero DOM dependencies). Skipped cleanly when node
   is not installed.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

_MD_JS = Path(__file__).resolve().parents[2] / "nexus" / "aurora" / "md.js"


# ── 1. asset / wiring contracts ──────────────────────────────────────────────

def test_md_js_is_served(client):
    r = client.get("/aurora/static/md.js")
    assert r.status_code == 200
    assert "application/javascript" in r.headers["content-type"]
    assert "renderMarkdown" in r.text


def test_md_js_is_escape_first(client):
    src = client.get("/aurora/static/md.js").text
    # The escaper must exist and the block walker must consume escaped text
    # (blockquote matching on "&gt;" only works if escaping ran first).
    assert "escapeMd" in src
    assert "&gt;" in src
    # Linkify must validate the scheme allowlist.
    assert "https?:" in src


def test_app_js_imports_and_uses_renderer(client):
    src = client.get("/aurora/static/app.js").text
    assert '/aurora/static/md.js' in src
    assert "renderMarkdown" in src
    assert "nx-msg-md" in src


def test_app_css_styles_md_elements(client):
    css = client.get("/aurora/static/app.css").text
    for sel in (".nx-msg-md", ".nx-md-pre", ".nx-md-code", ".nx-msg-md blockquote"):
        assert sel in css, f"missing CSS for {sel}"
    # md-rendered bodies must not inherit pre-wrap
    assert "white-space: normal" in css


# ── 2. renderer behaviour (node) ─────────────────────────────────────────────

_NODE = shutil.which("node")

_HARNESS = """
import {{ renderMarkdown, escapeMd }} from {md_url};
const out = {{}};
out.xss = renderMarkdown('<script>alert(1)</script><img src=x onerror=alert(1)>');
out.bold = renderMarkdown('**bold** word');
out.italic = renderMarkdown('plain *ital* end');
out.code = renderMarkdown('use `x < y` here');
out.fence = renderMarkdown('```python\\nprint("<hi>")\\n```');
out.h2 = renderMarkdown('## Section');
out.ul = renderMarkdown('- one\\n- two');
out.ol = renderMarkdown('1. first\\n2. second');
out.quote = renderMarkdown('> wise words');
out.link = renderMarkdown('[site](https://example.com)');
out.badlink = renderMarkdown('[bad](javascript:alert(1))');
out.paras = renderMarkdown('line one\\nline two\\n\\npara two');
out.sentinel = renderMarkdown('count <C0> and 3 spans `a` `b` `c`');
out.codeProtects = renderMarkdown('`**not bold**`');
out.escaped = escapeMd('<a href="x">&\\'');
console.log(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def rendered():
    if _NODE is None:
        pytest.skip("node not installed — JS behaviour tests skipped")
    script = _HARNESS.format(md_url=json.dumps(_MD_JS.as_uri()))
    proc = subprocess.run(
        [_NODE, "--input-type=module", "-e", script],
        capture_output=True, text=True, timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_xss_is_neutralised(rendered):
    out = rendered["xss"]
    # No live tags may survive — the payload is inert escaped text.
    assert "<script" not in out
    assert "<img" not in out
    assert "&lt;script&gt;" in out
    assert "&lt;img src=x onerror=alert(1)&gt;" in out


def test_bold_italic_inline_code(rendered):
    assert "<strong>bold</strong>" in rendered["bold"]
    assert "<em>ital</em>" in rendered["italic"]
    assert '<code class="nx-md-code">x &lt; y</code>' in rendered["code"]


def test_fenced_code_block(rendered):
    out = rendered["fence"]
    assert '<pre class="nx-md-pre" data-lang="python">' in out
    assert "print(&quot;&lt;hi&gt;&quot;)" in out
    # markdown transforms must not run inside code blocks
    assert "<strong>" not in out


def test_headings_lists_quotes(rendered):
    assert '<h2 class="nx-md-h">Section</h2>' in rendered["h2"]
    assert "<ul><li>one</li><li>two</li></ul>" in rendered["ul"]
    assert "<ol><li>first</li><li>second</li></ol>" in rendered["ol"]
    assert "<blockquote>wise words</blockquote>" in rendered["quote"]


def test_links_validated(rendered):
    good = rendered["link"]
    assert '<a href="https://example.com" target="_blank" rel="noopener">site</a>' in good
    bad = rendered["badlink"]
    assert "<a " not in bad
    assert "javascript:" in bad  # left as inert escaped text


def test_paragraphs_and_breaks(rendered):
    out = rendered["paras"]
    assert out.count("<p>") == 2
    assert "line one<br>line two" in out


def test_sentinels_cannot_be_forged(rendered):
    out = rendered["sentinel"]
    # literal "<C0>" typed by a user must render as escaped text, not as a
    # code-span placeholder; the three real spans must all survive.
    assert "&lt;C0&gt;" in out
    assert out.count('<code class="nx-md-code">') == 3
    assert "undefined" not in out


def test_inline_code_protects_contents(rendered):
    assert "<strong>" not in rendered["codeProtects"]
    assert "**not bold**" in rendered["codeProtects"]


def test_escaper_covers_all_dangerous_chars(rendered):
    assert rendered["escaped"] == "&lt;a href=&quot;x&quot;&gt;&amp;&#39;"
