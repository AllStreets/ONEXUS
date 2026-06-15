"""Behavior tests for the Sigil threat radar module."""
from __future__ import annotations

import asyncio

import pytest

from nexus.config import NexusConfig
from nexus.kernel.aegis import Aegis
from nexus.kernel.chronicle import Chronicle
from nexus.kernel.cortex import Cortex
from nexus.kernel.engram import Engram
from nexus.kernel.pulse import Message, Priority, Pulse
from nexus.modules.sigil import SigilModule


@pytest.fixture
def ctx(tmp_path):
    config = NexusConfig(data_dir=tmp_path)
    engram = Engram(tmp_path / "engram.db")
    engram.init_db()
    chronicle = Chronicle(str(tmp_path / "chronicle.db"))
    chronicle.init_db()
    aegis = Aegis(str(tmp_path / "aegis.db"), chronicle=chronicle)
    aegis.init_db()
    pulse = Pulse()
    cortex = Cortex(engram, chronicle, aegis, pulse, config)
    aegis.register_manifest(SigilModule.manifest())
    aegis.set_policy("sigil", allowed=True, initial_trust=0.30)
    return {"llm": None, "engram": engram, "chronicle": chronicle,
            "aegis": aegis, "pulse": pulse, "cortex": cortex}


async def test_trust_collapse_broadcasts_emergency_with_provenance(ctx):
    sigil = SigilModule()
    await sigil.on_load(ctx)
    received = []

    async def capture(msg):
        received.append(msg)

    ctx["pulse"].subscribe("sigil.detection", capture)
    await ctx["pulse"].publish(Message(
        topic="aegis.trust_change", source="aegis",
        payload={"module": "echo", "old_score": 0.30, "new_score": 0.08},
    ))
    await asyncio.sleep(0.3)
    assert len(received) == 1
    det = received[0]
    assert det.priority == Priority.EMERGENCY
    assert det.payload["rule"] == "trust_collapse"
    assert det.payload["activate_specter"] is True
    assert len(det.payload["provenance"]) == 64  # sha256 hex


async def test_detection_lands_in_chronicle(ctx):
    sigil = SigilModule()
    await sigil.on_load(ctx)
    await ctx["pulse"].publish(Message(
        topic="aegis.trust_change", source="aegis",
        payload={"module": "echo", "old_score": 0.55, "new_score": 0.30},
    ))
    await asyncio.sleep(0.3)
    rows = ctx["chronicle"].query(source="sigil", action="detection")
    assert rows and rows[0]["payload"]["rule"] == "trust_collapse"


async def test_on_load_is_gated_by_check_capability(ctx, tmp_path):
    bare = Aegis(str(tmp_path / "bare.db"))
    bare.init_db()  # no manifest registered -> DENY -> no subscriptions
    ctx2 = dict(ctx, aegis=bare)
    sigil = SigilModule()
    await sigil.on_load(ctx2)
    assert sigil._sub_ids == []


async def test_handle_reports_recent_detections(ctx):
    ctx["chronicle"].log("sigil", "detection", {
        "rule": "denied_burst", "severity": "high", "module": "wraith",
        "provenance": "ab" * 32,
    })
    sigil = SigilModule()
    out = await sigil.handle("sigil status", ctx)
    assert "denied_burst" in out and "wraith" in out


async def test_handle_radar_clear_when_no_detections(ctx):
    sigil = SigilModule()
    out = await sigil.handle("sigil status", ctx)
    assert "Radar clear" in out
