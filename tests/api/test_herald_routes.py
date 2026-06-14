"""API tests for the Herald negotiation routes."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from nexus.agents.manifest import Manifest
from nexus.api.server import create_app


def _initiator_manifest(slug, capability):
    return Manifest.model_validate({
        "manifest_version": 1, "slug": slug, "name": slug,
        "tagline": "test initiator", "version": "1.0.0", "system": False,
        "publisher": {"type": "org", "handle": "test"}, "category": "test",
        "identity": {"mark": {"kind": "svg", "gradient": ["#fff", "#000"]}},
        "capabilities": {
            "tools": [{"name": "handle", "class": "Routine"}],
            "declared": {"Routine": [capability]},
        },
        "runtime": {"transport": "in_process"},
        "trust": {"floor": 0.30, "default_tier": "ADVISOR"},
    })


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    return TestClient(create_app())


def test_offer_counter_accept_commit_flow(client):
    aegis = client.app.state.kernel.aegis
    aegis.register_manifest(_initiator_manifest("granted-agent", "engram.write.workspace"))

    r = client.post("/api/herald/offer", json={
        "initiator": "granted-agent", "responder": "agent-b",
        "capability": "engram.write.workspace", "workspace_id": "ws1",
        "terms": {"scope": "summaries"}, "value": 0.4})
    assert r.status_code == 200
    body = r.json()
    nid = body["negotiation_id"]
    assert body["status"] == "open"

    r = client.post(f"/api/herald/{nid}/counter",
                    json={"by": "agent-b", "terms": {"ttl_s": 300}, "value": 0.3})
    assert r.status_code == 200
    assert r.json()["current_value"] == 0.3

    r = client.post(f"/api/herald/{nid}/respond", json={"action": "accept", "by": "agent-b"})
    assert r.status_code == 200
    assert r.json()["status"] == "accepted"

    r = client.post(f"/api/herald/{nid}/commit", json={"by": "granted-agent"})
    assert r.status_code == 200
    assert r.json()["committed"] is True


def test_commit_denied_on_undeclared(client):
    aegis = client.app.state.kernel.aegis
    aegis.register_manifest(_initiator_manifest("limited-agent", "engram.read.workspace"))
    r = client.post("/api/herald/offer", json={
        "initiator": "limited-agent", "responder": "agent-b",
        "capability": "fs.write.workspace", "workspace_id": "ws1",
        "terms": {}, "value": 0.4})
    nid = r.json()["negotiation_id"]
    client.post(f"/api/herald/{nid}/respond", json={"action": "accept", "by": "agent-b"})
    r = client.post(f"/api/herald/{nid}/commit", json={"by": "limited-agent"})
    assert r.status_code == 200
    assert r.json()["committed"] is False


def test_list_open_negotiations(client):
    r = client.post("/api/herald/offer", json={
        "initiator": "agent-a", "responder": "agent-b",
        "capability": "engram.write.workspace", "workspace_id": "ws1",
        "terms": {}, "value": 0.4})
    nid = r.json()["negotiation_id"]
    r = client.get("/api/herald")
    assert r.status_code == 200
    ids = [n["negotiation_id"] for n in r.json()["negotiations"]]
    assert nid in ids


def test_get_unknown_negotiation_404(client):
    r = client.get("/api/herald/deadbeef")
    assert r.status_code == 404
