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

def test_list_first_run_seeds_hello_world(client):
    # A fresh install is never empty: the router seeds a "Hello World"
    # workspace and makes it active so first-time visitors land somewhere.
    r = client.get("/api/workspaces")
    assert r.status_code == 200
    body = r.json()
    assert body["active"] == "hello-world"
    ws_ids = [w["workspace_id"] for w in body["workspaces"]]
    assert ws_ids == ["hello-world"]


def test_create_workspace(client):
    r = _create(client)
    assert r.status_code == 200
    body = r.json()
    assert body["workspace_id"] == "ws-alpha"
    assert body["name"] == "Alpha"
    assert body["tone"] == "indigo"

    # GET list should now include it (alongside the seeded hello-world)
    r2 = client.get("/api/workspaces")
    assert r2.status_code == 200
    ws_list = r2.json()["workspaces"]
    ws_ids = [w["workspace_id"] for w in ws_list]
    assert len(ws_list) == 2
    assert "ws-alpha" in ws_ids
    assert "hello-world" in ws_ids


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

    # Before switch: active is the seeded hello-world workspace
    r0 = client.get("/api/workspaces/active")
    assert r0.status_code == 200
    active0 = r0.json()["active"]
    assert active0 is not None
    assert active0["workspace_id"] == "hello-world"

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
