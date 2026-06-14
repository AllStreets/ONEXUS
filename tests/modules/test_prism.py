"""Behavior tests for the Prism cross-domain synthesis module."""
from __future__ import annotations

import pytest

from nexus.kernel.aegis import Aegis
from nexus.kernel.chronicle import Chronicle
from nexus.kernel.engram import Engram
from nexus.modules.prism import CrossDomainSynthesizer, PrismModule
from nexus.workspaces.manager import WorkspaceManager


def _seed_partition(mgr, ws_id, facts):
    db = mgr.workspace_dir(ws_id) / "engram" / "episodic.sqlite"
    db.parent.mkdir(parents=True, exist_ok=True)
    eng = Engram(db)
    eng.init_db()
    for subject, relation, obj, conf in facts:
        eng.atlas.observe(subject, relation, obj, confidence=conf,
                          source_ref=f"chronicle:{ws_id}-{subject}")


@pytest.fixture
def ctx(tmp_path):
    ws_root = tmp_path / "workspaces"
    ws_root.mkdir()
    mgr = WorkspaceManager(ws_root)
    mgr.create(name="Alpha", workspace_id="alpha")
    mgr.create(name="Beta", workspace_id="beta")
    _seed_partition(mgr, "alpha", [
        ("acme", "ceo", "Jane Doe", 0.9),
        ("acme", "hq", "berlin", 0.9),
    ])
    _seed_partition(mgr, "beta", [
        ("acme", "product", "Widgets", 0.8),
        ("acme", "hq", "munich", 0.6),
    ])
    chronicle = Chronicle(str(tmp_path / "chronicle.db"))
    chronicle.init_db()
    aegis = Aegis(str(tmp_path / "aegis.db"), chronicle=chronicle)
    aegis.init_db()
    aegis.register_manifest(PrismModule.manifest())
    aegis.set_policy("prism", allowed=True, initial_trust=0.30)
    return {"llm": None, "chronicle": chronicle, "aegis": aegis,
            "workspace_manager": mgr}


# ── pure synthesizer ────────────────────────────────────────────────────────

def test_recurring_entities_surfaces_shared_subject():
    synth = CrossDomainSynthesizer()
    partitions = [
        ("alpha", [{"subject": "acme", "relation": "ceo", "object": "Jane",
                    "confidence": 0.9, "source_ref": "a1", "id": "1"}]),
        ("beta", [{"subject": "acme", "relation": "product", "object": "W",
                   "confidence": 0.8, "source_ref": "b1", "id": "2"}]),
    ]
    out = synth.recurring_entities(partitions, min_workspaces=2)
    assert len(out) == 1
    assert out[0]["subject"] == "acme"
    assert out[0]["workspaces"] == ["alpha", "beta"]
    assert any("alpha:" in c for c in out[0]["citations"])
    assert any("beta:" in c for c in out[0]["citations"])


def test_contradictions_surfaces_competing_objects():
    synth = CrossDomainSynthesizer()
    partitions = [
        ("alpha", [{"subject": "acme", "relation": "hq", "object": "berlin",
                    "confidence": 0.9, "source_ref": "a1"}]),
        ("beta", [{"subject": "acme", "relation": "hq", "object": "munich",
                   "confidence": 0.6, "source_ref": "b1"}]),
    ]
    out = synth.contradictions(partitions)
    assert len(out) == 1
    assert out[0]["subject"] == "acme" and out[0]["relation"] == "hq"
    objs = [c["object"] for c in out[0]["claims"]]
    assert "berlin" in objs and "munich" in objs
    # higher confidence first
    assert out[0]["claims"][0]["object"] == "berlin"


# ── module behavior ─────────────────────────────────────────────────────────

async def test_cross_partition_blocked_without_grant(ctx):
    prism = PrismModule()
    out = await prism.handle("prism synthesize recurring entities", ctx)
    low = out.lower()
    assert "approval" in low or "prompt" in low or "sensitive" in low
    assert "no partitions were read" in low


async def test_recurring_entity_surfaced_after_grant(ctx):
    ctx["aegis"].grant("prism", "engram.read.global", workspace_id=None)
    prism = PrismModule()
    out = await prism.handle("prism recurring entities across workspaces", ctx)
    assert "acme" in out
    assert "alpha" in out and "beta" in out


async def test_contradiction_surfaced_after_grant(ctx):
    ctx["aegis"].grant("prism", "engram.read.global", workspace_id=None)
    prism = PrismModule()
    out = await prism.handle("prism contradictions across workspaces", ctx)
    assert "berlin" in out and "munich" in out
    assert "CONTRADICTION" in out


async def test_synthesis_lands_in_chronicle(ctx):
    ctx["aegis"].grant("prism", "engram.read.global", workspace_id=None)
    prism = PrismModule()
    await prism.handle("prism recurring entities", ctx)
    assert ctx["chronicle"].query(source="prism", action="synthesis")
