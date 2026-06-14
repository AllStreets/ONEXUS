"""Tests for federation workspace sync (N3.2) — allowlist + loopback engine."""
from __future__ import annotations

import pytest

from nexus.agents.manifest import Manifest
from nexus.kernel.aegis import Aegis
from nexus.kernel.chronicle import Chronicle
from nexus.kernel.engram import Engram
from nexus.federation.sync import (
    LoopbackPeerClient, PeerAllowlist, WorkspaceSyncEngine,
)


# ── allowlist ───────────────────────────────────────────────────────────────

def test_allowlist_is_workspace_scoped(tmp_path):
    al = PeerAllowlist(tmp_path / "fed")
    al.allow("peer-b", "ws1")
    assert al.is_allowed("peer-b", "ws1") is True
    assert al.is_allowed("peer-b", "ws2") is False
    assert al.is_allowed("peer-unknown", "ws1") is False


def test_allowlist_persists_across_reloads(tmp_path):
    al = PeerAllowlist(tmp_path / "fed")
    al.allow("peer-b", "ws1")
    al2 = PeerAllowlist(tmp_path / "fed")
    al2.load()
    assert al2.is_allowed("peer-b", "ws1") is True


def test_allowlist_revoke(tmp_path):
    al = PeerAllowlist(tmp_path / "fed")
    al.allow("peer-b", "ws1")
    al.revoke("peer-b", "ws1")
    assert al.is_allowed("peer-b", "ws1") is False


# ── engine ──────────────────────────────────────────────────────────────────

def _fed_manifest():
    return Manifest.model_validate({
        "manifest_version": 1, "slug": "federation", "name": "federation",
        "tagline": "peer sync", "version": "1.0.0", "system": True,
        "publisher": {"type": "org", "handle": "nexus"}, "category": "system",
        "identity": {"mark": {"kind": "builtin:federation"}},
        "capabilities": {
            "tools": [{"name": "handle", "class": "Routine"}],
            "declared": {"Routine": ["federation.sync.workspace"]},
        },
        "runtime": {"transport": "in_process"},
        "trust": {"floor": 0.80, "default_tier": "EXECUTOR"},
    })


@pytest.fixture
def two_engines(tmp_path):
    def build(name):
        chronicle = Chronicle(str(tmp_path / f"{name}-chron.db"))
        chronicle.init_db()
        aegis = Aegis(str(tmp_path / f"{name}-aegis.db"), chronicle=chronicle)
        aegis.init_db()
        aegis.register_manifest(_fed_manifest())
        aegis.set_policy("federation", allowed=True, network=True, initial_trust=0.80)
        engrams: dict[str, Engram] = {}

        def engram_for(ws_id):
            if ws_id not in engrams:
                eng = Engram(tmp_path / f"{name}-{ws_id}.sqlite")
                eng.init_db()
                engrams[ws_id] = eng
            return engrams[ws_id]

        allowlist = PeerAllowlist(tmp_path / f"{name}-fed")
        engine = WorkspaceSyncEngine(
            instance_id=name, aegis=aegis, chronicle=chronicle,
            allowlist=allowlist, engram_for=engram_for)
        return engine, chronicle, engram_for

    eng_a, chron_a, ef_a = build("A")
    eng_b, chron_b, ef_b = build("B")
    # seed A's ws1 with a fact
    ef_a("ws1").atlas.observe("acme", "ceo", "Jane", confidence=0.9,
                              source_ref="chronicle:a1")
    return eng_a, chron_a, ef_a, eng_b, chron_b, ef_b


async def test_loopback_sync_merges_when_allowlisted(two_engines):
    eng_a, chron_a, _ef_a, eng_b, chron_b, ef_b = two_engines
    eng_a._allowlist.allow("B", "ws1")
    client = LoopbackPeerClient(eng_b.handle_inbound_atlas)
    result = await eng_a.push_workspace("B", "ws1", client)
    assert result["pushed"] == 1
    assert result["gated"] is False
    # fact landed in B's ws1 Engram
    beliefs = ef_b("ws1").atlas.beliefs("acme")
    assert any(b["object"] == "Jane" for b in beliefs)
    assert chron_a.query(source="federation", action="sync_push")
    assert chron_b.query(source="federation", action="sync_merge")


async def test_sync_blocked_when_not_allowlisted(two_engines):
    eng_a, _chron_a, _ef_a, eng_b, _chron_b, _ef_b = two_engines
    client = LoopbackPeerClient(eng_b.handle_inbound_atlas)
    result = await eng_a.push_workspace("B", "ws1", client)
    assert result["gated"] is True
    assert result["blocked"] == "not_allowlisted"
    assert result["pushed"] == 0


async def test_sync_blocked_by_kill_switch(two_engines):
    eng_a, _chron_a, _ef_a, eng_b, _chron_b, _ef_b = two_engines
    eng_a._allowlist.allow("B", "ws1")
    eng_a.set_sync_enabled(False)
    client = LoopbackPeerClient(eng_b.handle_inbound_atlas)
    result = await eng_a.push_workspace("B", "ws1", client)
    assert result["gated"] is True
    assert result["blocked"] == "kill_switch"
