"""Behavior tests for the Herald negotiation module."""
from __future__ import annotations

import pytest

from nexus.agents.manifest import Manifest
from nexus.kernel.aegis import Aegis
from nexus.kernel.chronicle import Chronicle
from nexus.kernel.pulse import Pulse
from nexus.modules.herald import HeraldModule


def _initiator_manifest():
    """A small agent that declares engram.write.workspace as Routine so the
    commit gate ALLOWs it."""
    return Manifest.model_validate({
        "manifest_version": 1, "slug": "agent-a", "name": "agent-a",
        "tagline": "test initiator", "version": "1.0.0", "system": False,
        "publisher": {"type": "org", "handle": "test"}, "category": "test",
        "identity": {"mark": {"kind": "svg", "gradient": ["#fff", "#000"]}},
        "capabilities": {
            "tools": [{"name": "handle", "class": "Routine"}],
            "declared": {"Routine": ["engram.write.workspace"]},
        },
        "runtime": {"transport": "in_process"},
        "trust": {"floor": 0.30, "default_tier": "ADVISOR"},
    })


@pytest.fixture
def ctx(tmp_path):
    chronicle = Chronicle(str(tmp_path / "chronicle.db"))
    chronicle.init_db()
    aegis = Aegis(str(tmp_path / "aegis.db"), chronicle=chronicle)
    aegis.init_db()
    aegis.register_manifest(_initiator_manifest())
    aegis.set_policy("agent-a", allowed=True, initial_trust=0.30)
    pulse = Pulse()
    return {"llm": None, "chronicle": chronicle, "aegis": aegis, "pulse": pulse}


async def test_offer_publishes_pulse(ctx):
    seen = []

    async def _capture(m):
        seen.append(m)

    ctx["pulse"].subscribe("herald.*", _capture)
    herald = HeraldModule()
    neg = await herald.open_negotiation(
        ctx, initiator="agent-a", responder="agent-b",
        capability="engram.write.workspace", workspace_id="ws1",
        terms={"scope": "summaries"}, value=0.4)
    await ctx["pulse"].drain()
    assert neg["status"] == "open"
    assert any(m.topic == "herald.offer" for m in seen)


async def test_accept_then_commit_allows_on_granted_initiator(ctx):
    herald = HeraldModule()
    neg = await herald.open_negotiation(
        ctx, initiator="agent-a", responder="agent-b",
        capability="engram.write.workspace", workspace_id="ws1",
        terms={}, value=0.4)
    nid = neg["negotiation_id"]
    await herald.counter(ctx, nid, by="agent-b", terms={"ttl_s": 300}, value=0.3)
    await herald.respond(ctx, nid, action="accept", by="agent-b")
    result = await herald.commit(ctx, nid, by="agent-a")
    assert result["committed"] is True
    assert result["verdict"] == "ALLOW"


async def test_commit_denied_on_undeclared_capability(ctx):
    herald = HeraldModule()
    neg = await herald.open_negotiation(
        ctx, initiator="agent-a", responder="agent-b",
        capability="fs.write.workspace", workspace_id="ws1",
        terms={}, value=0.4)
    nid = neg["negotiation_id"]
    await herald.respond(ctx, nid, action="accept", by="agent-b")
    result = await herald.commit(ctx, nid, by="agent-a")
    assert result["committed"] is False
    assert result["verdict"] == "DENY"


async def test_full_transcript_lands_in_chronicle(ctx):
    herald = HeraldModule()
    neg = await herald.open_negotiation(
        ctx, initiator="agent-a", responder="agent-b",
        capability="engram.write.workspace", workspace_id="ws1",
        terms={}, value=0.4)
    nid = neg["negotiation_id"]
    await herald.counter(ctx, nid, by="agent-b", terms={"ttl_s": 300}, value=0.3)
    await herald.respond(ctx, nid, action="accept", by="agent-b")
    await herald.commit(ctx, nid, by="agent-a")
    rows = ctx["chronicle"].query(source="herald", action="transcript")
    assert rows
    kinds = [t["kind"] for t in rows[0]["payload"]["transcript"]]
    assert "offer" in kinds and "counter" in kinds
    assert "accept" in kinds and "commit" in kinds
