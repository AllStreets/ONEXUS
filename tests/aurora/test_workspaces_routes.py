"""Tests for /api/workspaces REST endpoints (Phase 5 Task 5)."""
import pytest


# ── helpers ──────────────────────────────────────────────────────────────────

def _create(client, workspace_id="ws-alpha", name="Alpha", tone="indigo"):
    return client.post("/api/workspaces", json={
        "workspace_id": workspace_id,
        "name": name,
        "tone": tone,
    })


# ── tests ─────────────────────────────────────────────────────────────────────

def test_list_empty(client):
    r = client.get("/api/workspaces")
    assert r.status_code == 200
    body = r.json()
    assert body["active"] is None
    assert body["workspaces"] == []


def test_create_workspace(client):
    r = _create(client)
    assert r.status_code == 200
    body = r.json()
    assert body["workspace_id"] == "ws-alpha"
    assert body["name"] == "Alpha"
    assert body["tone"] == "indigo"

    # GET list should now include it
    r2 = client.get("/api/workspaces")
    assert r2.status_code == 200
    ws_list = r2.json()["workspaces"]
    assert len(ws_list) == 1
    assert ws_list[0]["workspace_id"] == "ws-alpha"


def test_get_workspace_by_id(client):
    _create(client)
    r = client.get("/api/workspaces/ws-alpha")
    assert r.status_code == 200
    body = r.json()
    assert body["workspace_id"] == "ws-alpha"
    assert body["name"] == "Alpha"
    assert body["tone"] == "indigo"


def test_switch_makes_active(client):
    _create(client, workspace_id="ws-beta", name="Beta", tone="magenta")

    # Before switch: active is None
    r0 = client.get("/api/workspaces/active")
    assert r0.status_code == 200
    assert r0.json()["active"] is None

    # Switch
    r = client.post("/api/workspaces/ws-beta/switch")
    assert r.status_code == 200
    assert r.json()["active"] == "ws-beta"

    # GET /active should reflect
    r2 = client.get("/api/workspaces/active")
    assert r2.status_code == 200
    active = r2.json()["active"]
    assert active is not None
    assert active["workspace_id"] == "ws-beta"


def test_delete_workspace(client):
    _create(client)

    r = client.delete("/api/workspaces/ws-alpha")
    assert r.status_code == 200
    assert r.json()["ok"] is True

    # Subsequent GET returns 404
    r2 = client.get("/api/workspaces/ws-alpha")
    assert r2.status_code == 404


def test_create_invalid_tone_400(client):
    r = client.post("/api/workspaces", json={
        "workspace_id": "ws-bad",
        "name": "Bad",
        "tone": "rainbow",
    })
    assert r.status_code == 400
