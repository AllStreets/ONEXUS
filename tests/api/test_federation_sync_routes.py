"""API tests for federation sync endpoints (N3.2)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from nexus.api.server import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("NEXUS_FEDERATION_ENABLED", "1")
    monkeypatch.setenv("NEXUS_INSTANCE_ID", "instance-local")
    c = TestClient(create_app())
    if getattr(c.app.state.kernel, "federation_sync_engine", None) is None:
        pytest.skip("federation sync not initialized")
    return c


def test_allow_then_allowlist_returns_pair(client):
    r = client.post("/api/federation/sync/allow",
                    json={"peer_id": "peer-b", "workspace_id": "ws1"})
    assert r.status_code == 200
    r = client.get("/api/federation/sync/allowlist")
    assert r.status_code == 200
    entries = r.json()["allowlist"]
    assert any(e["peer_id"] == "peer-b" and e["workspace_id"] == "ws1" for e in entries)


def test_inbound_atlas_merges(client):
    r = client.post("/api/federation/sync/atlas", json={
        "workspace_id": "ws1",
        "facts": [{"subject": "acme", "relation": "ceo", "object": "Jane",
                   "confidence": 0.9, "fact_class": "default",
                   "source_ref": "chronicle:peer-a1"}]})
    assert r.status_code == 200
    assert r.json()["merged"] == 1


def test_push_to_non_allowlisted_blocked(client):
    r = client.post("/api/federation/sync/push",
                    json={"peer_id": "stranger", "workspace_id": "ws1"})
    assert r.status_code == 200
    body = r.json()
    assert body["gated"] is True
    assert body["blocked"] == "not_allowlisted"


def test_revoke_removes_pair(client):
    client.post("/api/federation/sync/allow",
                json={"peer_id": "peer-c", "workspace_id": "ws2"})
    r = client.delete("/api/federation/sync/allow/peer-c/ws2")
    assert r.status_code == 200
    r = client.get("/api/federation/sync/allowlist")
    entries = r.json()["allowlist"]
    assert not any(e["peer_id"] == "peer-c" for e in entries)
