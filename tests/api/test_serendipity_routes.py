"""API tests for the Serendipity discover route (N3.3)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from nexus.api.server import create_app
from nexus.kernel.engram import Engram


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    c = TestClient(create_app())
    return c


def _seed_workspace(client, ws_id):
    kernel = client.app.state.kernel
    ws_root = kernel.config.data_dir / "workspaces" / ws_id / "engram"
    ws_root.mkdir(parents=True, exist_ok=True)
    eng = Engram(ws_root / "episodic.sqlite")
    eng.init_db()
    eng.atlas.observe("acme", "ceo", "Jane", confidence=0.95, source_ref="chronicle:top")
    eng.atlas.observe("nebula", "drifts", "quietly", confidence=0.1, source_ref="chronicle:n1")
    eng.atlas.observe("comet", "trails", "dust", confidence=0.15, source_ref="chronicle:n2")


def test_discover_returns_items_with_sources(client):
    _seed_workspace(client, "wsx")
    r = client.get("/api/serendipity/discover",
                   params={"q": "acme", "budget": 5, "workspace_id": "wsx"})
    assert r.status_code == 200
    body = r.json()
    assert body["query"] == "acme"
    assert body["gated"] is False
    assert isinstance(body["items"], list)
    for it in body["items"]:
        assert it["source"]


def test_discovery_lands_in_chronicle(client):
    _seed_workspace(client, "wsy")
    client.get("/api/serendipity/discover",
               params={"q": "acme", "budget": 3, "workspace_id": "wsy"})
    rows = client.app.state.kernel.chronicle.query(source="serendipity", action="discovery")
    assert rows
