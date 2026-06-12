"""Behavior tests for the Atlas world-model module."""
from __future__ import annotations

import pytest

from nexus.kernel.aegis import Aegis
from nexus.kernel.chronicle import Chronicle
from nexus.kernel.engram import Engram
from nexus.modules.atlas import AtlasModule


@pytest.fixture
def ctx(tmp_path):
    engram = Engram(tmp_path / "engram.db")
    engram.init_db()
    chronicle = Chronicle(str(tmp_path / "chronicle.db"))
    chronicle.init_db()
    aegis = Aegis(str(tmp_path / "aegis.db"), chronicle=chronicle)
    aegis.init_db()
    aegis.register_manifest(AtlasModule.manifest())
    aegis.set_policy("atlas", allowed=True, initial_trust=0.30)
    return {"llm": None, "engram": engram, "chronicle": chronicle, "aegis": aegis}


async def test_observe_then_query_with_citation(ctx):
    atlas = AtlasModule()
    out = await atlas.handle("observe: acme | ceo | Jane Doe | 0.9", ctx)
    assert "Recorded" in out and "chronicle:" in out
    out2 = await atlas.handle("what do we know about acme", ctx)
    assert "Jane Doe" in out2
    assert "confidence" in out2
    assert "chronicle:" in out2          # citation to the observing event
    assert "learned" in out2


async def test_observe_lands_in_chronicle(ctx):
    atlas = AtlasModule()
    await atlas.handle("observe: acme | ceo | Jane Doe", ctx)
    assert ctx["chronicle"].query(source="atlas", action="observe")


async def test_contradictions_listed_with_competing_confidence(ctx):
    atlas = AtlasModule()
    await atlas.handle("observe: acme | hq | berlin | 0.9", ctx)
    await atlas.handle("observe: acme | hq | munich | 0.6", ctx)
    out = await atlas.handle("atlas: acme", ctx)
    assert "berlin" in out and "munich" in out
    assert out.index("berlin") < out.index("munich")   # higher confidence first


async def test_unknown_subject_reports_no_beliefs(ctx):
    atlas = AtlasModule()
    out = await atlas.handle("what do we know about zorblax", ctx)
    assert "No beliefs" in out


async def test_reads_are_gated_by_check_capability(ctx, tmp_path):
    bare = Aegis(str(tmp_path / "bare.db"))
    bare.init_db()  # no manifest -> DENY
    atlas = AtlasModule()
    out = await atlas.handle("what do we know about acme", dict(ctx, aegis=bare))
    assert "blocked by Aegis" in out
