"""Behavior tests for the Chronos counterfactual module."""
from __future__ import annotations

import pytest

from nexus.kernel.aegis import Aegis
from nexus.kernel.chronicle import Chronicle
from nexus.modules.chronos import ChronosModule


def _seed(c):
    c.log("aegis", "permission_granted",
          {"agent_slug": "wraith", "capability": "fs.write.workspace"})
    c.log("cortex", "route", {"target": "wraith", "message_preview": "write report"})
    c.log("cortex", "response", {"module": "wraith", "response_preview": "wrote report.md"})
    c.log("cortex", "route", {"target": "council", "message_preview": "decide offers"})
    c.log("cortex", "response", {"module": "council", "response_preview": "chose A"})


@pytest.fixture
def ctx(tmp_path):
    chronicle = Chronicle(str(tmp_path / "chronicle.db"))
    chronicle.init_db()
    _seed(chronicle)
    aegis = Aegis(str(tmp_path / "aegis.db"), chronicle=chronicle)
    aegis.init_db()
    aegis.register_manifest(ChronosModule.manifest())
    aegis.set_policy("chronos", allowed=True, initial_trust=0.30)
    return {"llm": None, "chronicle": chronicle, "aegis": aegis}


async def test_timeline_reports_branch_points(ctx):
    chronos = ChronosModule()
    out = await chronos.handle("chronos decision timeline", ctx)
    assert "Decision timeline" in out
    assert "*" in out                    # at least one branch point marked


async def test_counterfactual_reports_pruned_actions(ctx):
    chronos = ChronosModule()
    out = await chronos.handle("what if wraith permission_granted", ctx)
    assert "Counterfactual" in out
    assert "Would NOT have happened" in out
    assert "wraith" in out


async def test_query_lands_in_chronicle(ctx):
    chronos = ChronosModule()
    await chronos.handle("chronos decision timeline", ctx)
    assert ctx["chronicle"].query(source="chronos", action="query")


async def test_reads_are_gated_by_check_capability(ctx, tmp_path):
    bare = Aegis(str(tmp_path / "bare.db"))
    bare.init_db()  # no manifest -> DENY
    chronos = ChronosModule()
    out = await chronos.handle("chronos decision timeline", dict(ctx, aegis=bare))
    assert "blocked by Aegis" in out
