"""NEXUS v1.0 acceptance smoke.

A single test exercising every surface + every gate. If this passes,
the release is consistent end-to-end.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nexus.api.server import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    return TestClient(create_app())


def test_v1_acceptance(client, tmp_path):
    """The shipped OS — every surface live, every gate honoured."""
    # 1. Aurora shell loads — window chrome + sidebar + cockpit rail + all
    #    navigation entry points present (v2 layout: persistent 3-column shell).
    r = client.get("/aurora")
    assert r.status_code == 200
    for marker in ['id="nx-kernel-mark"',         # breathing kernel orb
                   'id="nx-mood-pill"',           # mood pill in chrome (toggles cockpit overlay)
                   'id="nx-clock"',               # live clock
                   'id="nx-ws-list"',             # sidebar workspace pills
                   'id="nx-new-ws"',              # + new workspace (⌘N)
                   'id="nx-recent-agents"',       # recent agents block
                   'id="nx-open-catalog"',        # browse catalog link
                   'id="nx-open-settings"',       # settings link (⌘,)
                   'id="nx-user-footer"',         # user identity footer
                   'id="nx-main"',                # main canvas slot
                   'id="nx-cockpit-rail"',        # persistent cockpit rail
                   'id="nx-trust-card"',          # trust sparkline mount
                   'id="nx-perm-log"',            # recent permissions log
                   'id="nx-mood-card"',           # ambient mood mesh
                   'id="nx-agent-discs"']:        # built-in agents disc row
        assert marker in r.text, f"missing {marker}"

    # 2. Classic dashboard backward-compat
    r = client.get("/dashboard")
    assert r.status_code == 200

    # 3. Mood endpoint live, returns a valid 8-mood state
    r = client.get("/api/mood/current")
    assert r.status_code == 200
    valid_moods = {"calm_focus", "deep_flow", "routing", "deliberating",
                   "creative", "reflective", "watchful", "alert"}
    assert r.json()["mood"] in valid_moods

    # 4. Workspaces CRUD
    r = client.post("/api/workspaces", json={
        "workspace_id": "release-test",
        "name": "Release Test",
        "tone": "indigo",
    })
    assert r.status_code in (200, 409), r.text
    r = client.post("/api/workspaces/release-test/switch")
    assert r.status_code == 200
    r = client.get("/api/workspaces")
    body = r.json()
    assert any(w["workspace_id"] == "release-test" for w in body["workspaces"])
    assert body["active"] == "release-test"

    # 5. Send a message
    r = client.post("/api/messages", json={"message": "should i decide?"})
    assert r.status_code == 200
    assert "response" in r.json()

    # 6. Permission inbox surfaces empty initially
    r = client.get("/api/permissions/pending")
    assert r.status_code == 200
    assert "pending" in r.json()

    # 7. Install plan validates a manifest (dry run)
    manifest = {
        "manifest_version": 1, "slug": "release-demo", "name": "release-demo",
        "version": "0.1.0", "system": False,
        "publisher": {"type": "org", "handle": "test"}, "category": "test",
        "identity": {"mark": {"kind": "svg", "gradient": ["#fff", "#000"]}},
        "intents": [],
        "capabilities": {
            "tools": [{"name": "handle", "class": "Routine"}],
            "declared": {"Routine": ["engram.read.workspace"]},
        },
        "runtime": {"transport": "stdio", "command": "demo-mcp"},
    }
    r = client.post("/api/agents/install", json={"manifest": manifest, "confirm": False})
    assert r.status_code == 200
    assert r.json()["plan"]["slug"] == "release-demo"

    # 8. Spatial aggregator returns system + installed agents
    r = client.get("/api/spatial/agents")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body.get("agents"), list)

    # 9. Cockpit endpoints reachable
    r = client.get("/api/cockpit/snapshot")
    assert r.status_code == 200
    body = r.json()
    for key in ("pulse", "residents", "trust_gradient",
                "chronicle_tail", "network", "engram_stats"):
        assert key in body, f"missing cockpit panel: {key}"

    # 10. Phase 6 invariant — no kernel module other than Aegis imports httpx
    kernel_dir = Path("nexus/kernel")
    for f in kernel_dir.glob("*.py"):
        if f.name in ("__init__.py", "aegis.py"):
            continue
        text = f.read_text()
        assert "import httpx" not in text and "from httpx" not in text, (
            f"{f}: kernel module must not import httpx"
        )
        assert "urlopen" not in text
        assert "requests.get" not in text and "requests.post" not in text

    # 10b. N3.2 invariant — the federation sync engine must NOT touch the
    #      network. Real peer HTTP stays in FederationProtocol._http
    #      (KernelHttpClient -> aegis.network()). sync.py imports no transport.
    sync_src = Path("nexus/federation/sync.py").read_text()
    # Strip the module docstring (which names httpx/socket in prose) before the
    # import scan so the invariant checks real imports, not documentation.
    import ast
    sync_tree = ast.parse(sync_src)
    sync_no_doc = ast.get_docstring(sync_tree)
    code_only = sync_src
    if sync_no_doc:
        code_only = sync_src.replace(f'"""{sync_no_doc}"""', "", 1)
    assert "import httpx" not in code_only and "from httpx" not in code_only
    assert "import socket" not in code_only and "from socket" not in code_only

    # 11. Zero-emoji invariant in Aurora assets
    pat = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF]")
    for path in ["/aurora", "/aurora/static/tokens.css", "/aurora/static/mood.css",
                 "/aurora/static/app.css", "/aurora/static/app.js",
                 "/aurora/static/icons.js"]:
        r = client.get(path)
        assert not pat.search(r.text), f"emoji in {path}"

    # 12. Accessibility — media queries present
    r = client.get("/aurora/static/tokens.css")
    assert "prefers-reduced-motion" in r.text
    assert "prefers-reduced-data" in r.text
    r = client.get("/aurora/static/mood.css")
    assert "prefers-contrast" in r.text
