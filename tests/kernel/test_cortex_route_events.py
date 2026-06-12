"""N1 — Cortex publishes kernel.route for every routing decision."""
from __future__ import annotations

import asyncio

import pytest

from nexus.config import NexusConfig
from nexus.kernel.aegis import Aegis
from nexus.kernel.chronicle import Chronicle
from nexus.kernel.cortex import Cortex
from nexus.kernel.engram import Engram
from nexus.kernel.pulse import Pulse
from nexus.modules.council import CouncilModule


@pytest.fixture
def kernel(tmp_path):
    config = NexusConfig(data_dir=tmp_path)
    engram = Engram(tmp_path / "engram.db")
    engram.init_db()
    chronicle = Chronicle(str(tmp_path / "chronicle.db"))
    chronicle.init_db()
    aegis = Aegis(str(tmp_path / "aegis.db"), chronicle=chronicle)
    aegis.init_db()
    pulse = Pulse()
    cortex = Cortex(engram, chronicle, aegis, pulse, config)
    cortex.register_module(CouncilModule())
    aegis.set_policy("council", allowed=True, initial_trust=0.30)

    async def _mock_llm(msg: str) -> str:
        return "mock"

    cortex.set_llm(_mock_llm)
    return cortex, pulse


async def test_process_publishes_kernel_route(kernel):
    cortex, pulse = kernel
    received = []

    async def capture(msg):
        received.append(msg)

    pulse.subscribe("kernel.route", capture)
    await cortex.process("should i decide between two job offers?")
    await asyncio.sleep(0.2)
    assert len(received) == 1
    p = received[0].payload
    assert p["target"] == "council"
    assert p["trust_tier"] == "ADVISOR"
    assert isinstance(p["signals"], list) and p["signals"]
    assert p["message_preview"].startswith("should i decide")
