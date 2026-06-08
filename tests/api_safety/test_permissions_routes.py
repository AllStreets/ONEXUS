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
