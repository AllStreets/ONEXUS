"""N1 — Aegis emits live kernel.gate / aegis.trust_change events on Pulse."""
from __future__ import annotations

import asyncio

import pytest

from nexus.kernel.aegis import Aegis
from nexus.kernel.chronicle import Chronicle
from nexus.kernel.pulse import Pulse
from nexus.modules.oracle import OracleModule


@pytest.fixture
def aegis(tmp_path):
    chronicle = Chronicle(str(tmp_path / "db.sqlite"))
    chronicle.init_db()
    a = Aegis(str(tmp_path / "db.sqlite"), chronicle=chronicle)
    a.init_db()
    return a


async def test_check_capability_emits_kernel_gate(aegis):
    pulse = Pulse()
    aegis.set_pulse(pulse)
    aegis.register_manifest(OracleModule.manifest())
    received = []

    async def capture(msg):
        received.append(msg)

    pulse.subscribe("kernel.gate", capture)
    decision = aegis.check_capability("oracle", "engram.read.workspace")
    assert decision.verdict.value == "ALLOW"
    await asyncio.sleep(0.1)
    assert len(received) == 1
    p = received[0].payload
    assert p["agent"] == "oracle"
    assert p["capability"] == "engram.read.workspace"
    assert p["verdict"] == "ALLOW"
    assert p["permission_class"] == "Routine"


async def test_deny_verdict_is_emitted_too(aegis):
    pulse = Pulse()
    aegis.set_pulse(pulse)
    received = []

    async def capture(msg):
        received.append(msg)

    pulse.subscribe("kernel.gate", capture)
    decision = aegis.check_capability("ghost", "anything.at.all")
    assert decision.verdict.value == "DENY"
    await asyncio.sleep(0.1)
    assert received[0].payload["verdict"] == "DENY"


async def test_record_outcome_emits_trust_change(aegis):
    # Seed trust before attaching Pulse so the seeding emits nothing and the
    # failure outcome has room to drop (0.30 -> 0.08).
    aegis.set_trust("echo", 0.30)
    pulse = Pulse()
    aegis.set_pulse(pulse)
    received = []

    async def capture(msg):
        received.append(msg)

    pulse.subscribe("aegis.trust_change", capture)
    aegis.record_outcome("echo", False)
    await asyncio.sleep(0.1)
    assert len(received) == 1
    p = received[0].payload
    assert p["module"] == "echo"
    assert p["new_score"] < p["old_score"]
    assert "tier" in p


def test_no_pulse_attached_is_silent(aegis):
    # Sync context, no Pulse: decisions still work, nothing crashes.
    decision = aegis.check_capability("ghost", "anything.at.all")
    assert decision.verdict.value == "DENY"
    assert aegis.record_outcome("echo", True) > 0.0
