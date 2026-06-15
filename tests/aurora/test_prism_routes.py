"""N2.1 — /api/prism/synthesis gated cross-partition route."""
from pathlib import Path

from nexus.kernel.engram import Engram
from nexus.workspaces.manager import WorkspaceManager


def _seed_two_partitions(client):
    kernel = client.app.state.kernel
    ws_root = Path(kernel.config.data_dir) / "workspaces"
    ws_root.mkdir(parents=True, exist_ok=True)
    mgr = WorkspaceManager(root=ws_root)
    for wid in ("alpha", "beta"):
        if mgr.get(wid) is None:
            mgr.create(name=wid.title(), workspace_id=wid)
    for wid, facts in (("alpha", [("acme", "hq", "berlin", 0.9)]),
                       ("beta", [("acme", "hq", "munich", 0.6)])):
        db = mgr.workspace_dir(wid) / "engram" / "episodic.sqlite"
        db.parent.mkdir(parents=True, exist_ok=True)
        eng = Engram(db)
        eng.init_db()
        for s, r, o, c in facts:
            eng.atlas.observe(s, r, o, confidence=c, source_ref=f"chronicle:{wid}")
    client.app.state.workspace_manager = mgr


def test_synthesis_gated_without_grant(client):
    _seed_two_partitions(client)
    r = client.get("/api/prism/synthesis")
    assert r.status_code == 200
    body = r.json()
    assert body["gated"] is True
    assert body["findings"] == []


def test_synthesis_open_after_grant(client):
    _seed_two_partitions(client)
    client.app.state.kernel.aegis.grant("prism", "engram.read.global", workspace_id=None)
    r = client.get("/api/prism/synthesis")
    assert r.status_code == 200
    body = r.json()
    assert body["gated"] is False
    # acme recurs across alpha+beta
    subjects = {f["subject"] for f in body["findings"]}
    assert "acme" in subjects
