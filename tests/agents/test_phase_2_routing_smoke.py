"""End-to-end smoke test for Phase 2 — manifest-driven routing.

Builds a real kernel (Cortex + Aegis + Chronicle + Engram + Pulse),
registers built-in manifests, registers the real cognitive modules,
and verifies that messages route to the expected built-ins via the
new manifest-driven classifier.
"""
from __future__ import annotations

import pytest

from nexus.kernel.aegis import Aegis
from nexus.kernel.cortex import Cortex
from nexus.kernel.engram import Engram
from nexus.kernel.chronicle import Chronicle
from nexus.kernel.pulse import Pulse
from nexus.config import NexusConfig

from nexus.modules.council import CouncilModule
from nexus.modules.specter import SpecterModule
from nexus.modules.oracle import OracleModule


@pytest.fixture
async def kernel(tmp_path):
    config = NexusConfig(data_dir=tmp_path)
    engram = Engram(str(tmp_path / "engram.db"))
    engram.init_db()
    chronicle = Chronicle(str(tmp_path / "chronicle.db"))
    chronicle.init_db()
    aegis = Aegis(str(tmp_path / "aegis.db"), chronicle=chronicle)
    aegis.init_db()
    pulse = Pulse()
    cortex = Cortex(engram, chronicle, aegis, pulse, config)
    cortex.register_builtin_manifests()

    # Register the three modules used in routing assertions
    council = CouncilModule()
    specter = SpecterModule()
    oracle = OracleModule()
    for m in (council, specter, oracle):
        cortex.register_module(m)
        aegis.set_policy(m.name, allowed=True, initial_trust=0.60)

    await cortex.initialize_modules()
    return cortex


@pytest.mark.asyncio
async def test_deliberate_query_routes_to_council(kernel):
    cortex = kernel
    await cortex.process("should i refactor the auth module?")
    routes = cortex._chronicle.query(source="cortex", action="route", limit=10)
    assert any(r["payload"].get("target") == "council" for r in routes)


@pytest.mark.asyncio
async def test_challenge_query_routes_to_specter(kernel):
    cortex = kernel
    await cortex.process("red team this design")
    routes = cortex._chronicle.query(source="cortex", action="route", limit=10)
    assert any(r["payload"].get("target") == "specter" for r in routes)


@pytest.mark.asyncio
async def test_aegis_has_manifest_for_unregistered_module(kernel):
    """Even modules not yet register_module()'d still have manifests in Aegis."""
    cortex = kernel
    aegis = cortex._aegis
    # Echo wasn't register_module()'d in this fixture, but its manifest is registered
    assert aegis.get_manifest("echo") is not None
