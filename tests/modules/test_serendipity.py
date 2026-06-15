"""Behavior tests for the Serendipity anti-optimization module."""
from __future__ import annotations

import pytest

from nexus.kernel.aegis import Aegis
from nexus.kernel.chronicle import Chronicle
from nexus.kernel.engram import Engram
from nexus.modules.serendipity import SerendipityModule


@pytest.fixture
def ctx(tmp_path):
    eng = Engram(tmp_path / "engram.sqlite")
    eng.init_db()
    # The obvious top match: high confidence, query keywords.
    eng.atlas.observe("acme", "ceo", "Jane", confidence=0.95,
                      source_ref="chronicle:top")
    # Off-axis: low confidence (high novelty), unrelated keywords.
    eng.atlas.observe("nebula", "drifts", "quietly", confidence=0.1,
                      source_ref="chronicle:novel1")
    eng.atlas.observe("comet", "trails", "dust", confidence=0.15,
                      source_ref="chronicle:novel2")
    eng.atlas.observe("orbit", "decays", "slowly", confidence=0.2,
                      source_ref="chronicle:novel3")
    chronicle = Chronicle(str(tmp_path / "chronicle.db"))
    chronicle.init_db()
    aegis = Aegis(str(tmp_path / "aegis.db"), chronicle=chronicle)
    aegis.init_db()
    aegis.register_manifest(SerendipityModule.manifest())
    aegis.set_policy("serendipity", allowed=True, initial_trust=0.30)
    return {"llm": None, "engram": eng, "chronicle": chronicle, "aegis": aegis,
            "workspace_id": None}


async def test_surfaces_novel_not_top_match(ctx):
    mod = SerendipityModule()
    out = await mod.handle("acme ceo", ctx)
    # The high-confidence obvious match should NOT be surfaced.
    assert "Jane" not in out
    # high-novelty outliers surface
    assert "nebula" in out or "comet" in out or "orbit" in out


async def test_every_line_cites_a_source(ctx):
    mod = SerendipityModule()
    out = await mod.handle("anything", ctx)
    for line in out.splitlines():
        if line.strip().startswith("-"):
            assert "source" in line


async def test_discovery_lands_in_chronicle(ctx):
    mod = SerendipityModule()
    await mod.handle("acme", ctx)
    assert ctx["chronicle"].query(source="serendipity", action="discovery")


async def test_budget_cap_respected(ctx):
    mod = SerendipityModule()
    res = mod.discover(ctx, "acme", budget=2)
    assert len(res["items"]) <= 2


async def test_denied_read_returns_blocked_and_reads_nothing(tmp_path):
    eng = Engram(tmp_path / "engram.sqlite")
    eng.init_db()
    eng.atlas.observe("x", "y", "z", confidence=0.1, source_ref="chronicle:1")
    chronicle = Chronicle(str(tmp_path / "chronicle.db"))
    chronicle.init_db()
    aegis = Aegis(str(tmp_path / "aegis.db"), chronicle=chronicle)
    aegis.init_db()
    # No manifest registered -> check_capability DENIES.
    ctx = {"llm": None, "engram": eng, "chronicle": chronicle, "aegis": aegis,
           "workspace_id": None}
    mod = SerendipityModule()
    res = mod.discover(ctx, "x", budget=5)
    assert res["gated"] is True
    assert res["items"] == []
