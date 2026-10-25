"""Tests for /api/permissions/* and /api/agents/install."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from nexus.api.server import create_app
from nexus.kernel.aegis import PermissionRequest, PermissionInbox


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    app = create_app()
    return TestClient(app)


def test_permissions_pending_empty(client):
    resp = client.get("/api/permissions/pending")
    assert resp.status_code == 200
    assert resp.json() == {"pending": []}


def test_permissions_decide_unknown_ticket(client):
    resp = client.post(
        "/api/permissions/decide",
        json={"ticket_id": "nonexistent", "decision": "allow_once"},
    )
    assert resp.status_code == 404


def test_agents_install_validates_manifest(client, tmp_path):
    manifest = {
        "manifest_version": 1, "slug": "demo", "name": "demo",
        "version": "0.1.0", "system": False,
        "publisher": {"type": "org", "handle": "test"}, "category": "test",
        "identity": {"mark": {"kind": "svg", "gradient": ["#fff", "#000"]}},
        "intents": [],
        "capabilities": {"tools": [{"name": "handle", "class": "Routine"}],
                         "declared": {"Routine": ["engram.read.workspace"]}},
        "runtime": {"transport": "stdio", "command": "demo-mcp"},
    }
    resp = client.post("/api/agents/install", json={"manifest": manifest, "confirm": False})
    assert resp.status_code == 200
    body = resp.json()
    assert body["plan"]["slug"] == "demo"
    # confirm=False means dry-run; nothing persisted
    assert not (tmp_path / "agents" / "demo").exists()


def test_agents_install_confirm_persists(client, tmp_path):
    manifest = {
        "manifest_version": 1, "slug": "real", "name": "real",
        "version": "0.1.0", "system": False,
        "publisher": {"type": "org", "handle": "test"}, "category": "test",
        "identity": {"mark": {"kind": "svg", "gradient": ["#fff", "#000"]}},
        "intents": [],
        "capabilities": {"tools": [{"name": "handle", "class": "Routine"}],
                         "declared": {"Routine": ["engram.read.workspace"]}},
        "runtime": {"transport": "stdio", "command": "real-mcp"},
    }
    resp = client.post("/api/agents/install", json={"manifest": manifest, "confirm": True})
    assert resp.status_code == 200
    assert (tmp_path / "agents" / "real" / "manifest.json").exists()


def test_deny_is_logged_in_the_shape_the_cockpit_counts(client):
    """Pressing Deny must leave a chronicle row the cockpit's "denied"
    counter recognises: source aegis, action permission_revoked, decision
    deny. The rail used to count only gate verdicts, so a user deny never
    moved it."""
    with client:
        ticket = client.post("/api/permissions/seed", json={
            "agent_slug": "oracle", "capability": "fs.write",
            "permission_class": "Sensitive", "target": "src/kernel/cortex.py",
        }).json()["ticket_id"]
        assert client.post("/api/permissions/decide", json={
            "ticket_id": ticket, "decision": "deny",
        }).json() == {"ok": True}
        entries = client.get("/api/chronicle?source=aegis&limit=50").json()["entries"]
    denies = [e for e in entries if e["action"] == "permission_revoked"]
    assert denies and denies[0]["payload"]["decision"] == "deny"
    assert denies[0]["payload"]["target"] == "src/kernel/cortex.py"

    js = client.get("/aurora/static/app.js").text
    assert 'e.action === "permission_revoked"' in js
    assert 'String(p.decision || "").toLowerCase() === "deny"' in js
