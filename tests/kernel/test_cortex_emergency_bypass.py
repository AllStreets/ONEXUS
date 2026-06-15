"""N1 — emergency-priority Pulse messages bypass normal routing in Cortex."""
from __future__ import annotations

import asyncio

import pytest

from nexus.config import NexusConfig
from nexus.kernel.aegis import Aegis
from nexus.kernel.chronicle import Chronicle
from nexus.kernel.cortex import Cortex, specter_autoactivation_enabled
from nexus.kernel.engram import Engram
from nexus.kernel.pulse import Message, Priority, Pulse
from nexus.modules.specter import SpecterModule


def _build(tmp_path):
    config = NexusConfig(data_dir=tmp_path)
    engram = Engram(tmp_path / "engram.db")
    engram.init_db()
    chronicle = Chronicle(str(tmp_path / "chronicle.db"))
    chronicle.init_db()
    aegis = Aegis(str(tmp_path / "aegis.db"), chronicle=chronicle)
    aegis.init_db()
    pulse = Pulse()
    cortex = Cortex(engram, chronicle, aegis, pulse, config)
    cortex.register_module(SpecterModule())
    aegis.set_policy("specter", allowed=True, initial_trust=0.30)

    async def _mock_llm(msg: str) -> str:
        return "adversarial read: looks suspicious"

    cortex.set_llm(_mock_llm)
    cortex.attach_emergency_bypass()
    return cortex, pulse, chronicle, config


def _detection(activate=True):
    return Message(
        topic="sigil.detection", source="sigil", priority=Priority.EMERGENCY,
        payload={"rule": "trust_collapse", "module": "echo",
                 "evidence": [{"old_score": 0.30, "new_score": 0.08}],
                 "activate_specter": activate},
    )


async def test_emergency_bypass_logs_and_activates_specter(tmp_path):
    cortex, pulse, chronicle, _ = _build(tmp_path)
    await pulse.publish(_detection())
    await asyncio.sleep(0.3)
    assert chronicle.query(source="cortex", action="emergency_bypass")
    activated = chronicle.query(source="cortex", action="specter_auto_activated")
    assert activated and activated[0]["payload"]["rule"] == "trust_collapse"


async def test_normal_priority_messages_do_not_bypass(tmp_path):
    cortex, pulse, chronicle, _ = _build(tmp_path)
    await pulse.publish(Message(topic="sigil.detection", source="sigil",
                                payload={"activate_specter": True}))
    await asyncio.sleep(0.2)
    assert chronicle.query(source="cortex", action="emergency_bypass") == []


async def test_env_kill_switch_blocks_autoactivation(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_SIGIL_SPECTER_AUTOACTIVATE", "0")
    cortex, pulse, chronicle, _ = _build(tmp_path)
    await pulse.publish(_detection())
    await asyncio.sleep(0.3)
    assert chronicle.query(source="cortex", action="emergency_bypass")
    assert chronicle.query(source="cortex", action="specter_auto_activated") == []
    skipped = chronicle.query(source="cortex", action="specter_autoactivation_skipped")
    assert skipped and skipped[0]["payload"]["reason"] == "kill_switch"


async def test_file_kill_switch_blocks_autoactivation(tmp_path):
    cortex, pulse, chronicle, config = _build(tmp_path)
    (config.data_dir / "sigil-specter.kill").write_text("disabled by operator\n")
    assert specter_autoactivation_enabled(config) is False
    await pulse.publish(_detection())
    await asyncio.sleep(0.3)
    assert chronicle.query(source="cortex", action="specter_auto_activated") == []
