# tests/test_batch5_integration.py
"""
Batch 5 integration: Network + platform modules through Cortex.
"""
import pytest
from nexus.config import NexusConfig
from nexus.kernel.engram import Engram
from nexus.kernel.chronicle import Chronicle
from nexus.kernel.aegis import Aegis
from nexus.kernel.pulse import Pulse
from nexus.kernel.cortex import Cortex
from nexus.modules.general import GeneralModule
from nexus.modules.collective import CollectiveModule
from nexus.modules.legacy import LegacyModule


@pytest.fixture
def network_system(tmp_config):
    engram = Engram(tmp_config.db_path)
    engram.init_db()
    chronicle = Chronicle(tmp_config.db_path)
    chronicle.init_db()
    aegis = Aegis(tmp_config.db_path)
    aegis.init_db()
    pulse = Pulse()

    cortex = Cortex(
        engram=engram, chronicle=chronicle, aegis=aegis,
        pulse=pulse, config=tmp_config,
    )

    modules = {
        "general": GeneralModule(),
        "collective": CollectiveModule(),
        "legacy": LegacyModule(),
    }

    for mod in modules.values():
        cortex.register_module(mod)
        aegis.set_policy(mod.name, allowed=True, network=mod.requires_network)

    return {"cortex": cortex, **modules}


@pytest.mark.asyncio
async def test_collective_via_cortex(network_system):
    cortex = network_system["cortex"]
    response = await cortex.process("Show federated learning peer status")
    assert "collective" in response.lower() or "federated" in response.lower() or "peer" in response.lower()


@pytest.mark.asyncio
async def test_legacy_via_cortex(network_system):
    leg = network_system["legacy"]
    leg.record_decision("hiring", "Hired A", "positive", ["culture"])
    leg.record_decision("hiring", "Hired B", "positive", ["culture"])
    cortex = network_system["cortex"]
    response = await cortex.process("Crystallize my hiring decision framework")
    assert "hiring" in response.lower() or "pattern" in response.lower() or "framework" in response.lower()


@pytest.mark.asyncio
async def test_all_network_modules_registered(network_system):
    cortex = network_system["cortex"]
    modules = cortex.list_modules()
    for name in ["general", "collective", "legacy"]:
        assert name in modules
