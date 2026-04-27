# tests/test_batch4_integration.py
"""
Batch 4 integration: Advanced intelligence modules through Cortex.
"""
import pytest
from nexus.config import NexusConfig
from nexus.kernel.engram import Engram
from nexus.kernel.chronicle import Chronicle
from nexus.kernel.aegis import Aegis
from nexus.kernel.pulse import Pulse
from nexus.kernel.cortex import Cortex
from nexus.modules.general import GeneralModule
from nexus.modules.specter import SpecterModule
from nexus.modules.chronos import ChronosModule
from nexus.modules.dreamweaver import DreamweaverModule
from nexus.modules.serendipity import SerendipityModule
from nexus.modules.forge import ForgeModule


@pytest.fixture
def advanced_system(tmp_config):
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
        "specter": SpecterModule(),
        "chronos": ChronosModule(),
        "dreamweaver": DreamweaverModule(),
        "serendipity": SerendipityModule(),
        "forge": ForgeModule(),
    }

    for mod in modules.values():
        cortex.register_module(mod)
        aegis.set_policy(mod.name, allowed=True)

    return {"cortex": cortex, **modules}


@pytest.mark.asyncio
async def test_specter_via_cortex(advanced_system):
    cortex = advanced_system["cortex"]
    response = await cortex.process("Red team this: I want to sign a $100k contract with a new vendor")
    assert "counter" in response.lower() or "risk" in response.lower() or "assumption" in response.lower()


@pytest.mark.asyncio
async def test_chronos_via_cortex(advanced_system):
    cortex = advanced_system["cortex"]
    response = await cortex.process("Model the future timeline if I switch to freelancing")
    assert "branch" in response.lower() or "timeline" in response.lower()


@pytest.mark.asyncio
async def test_dreamweaver_via_cortex(advanced_system):
    dw = advanced_system["dreamweaver"]
    dw.ingest("Important Q4 planning session")
    cortex = advanced_system["cortex"]
    response = await cortex.process("Generate my morning brief from overnight synthesis")
    assert "brief" in response.lower() or "q4" in response.lower()


@pytest.mark.asyncio
async def test_serendipity_via_cortex(advanced_system):
    s = advanced_system["serendipity"]
    s.record_focus("logistics")
    s.add_knowledge("biology", "Slime mold network optimization", ["network", "optimization"])
    cortex = advanced_system["cortex"]
    response = await cortex.process("Show me something surprising and unexpected")
    assert "surprising" in response.lower() or "biology" in response.lower() or "connection" in response.lower()


@pytest.mark.asyncio
async def test_forge_via_cortex(advanced_system):
    cortex = advanced_system["cortex"]
    response = await cortex.process("Start a negotiation for freelance rate $100-$200")
    assert "negotiation" in response.lower() or "offer" in response.lower()


@pytest.mark.asyncio
async def test_all_advanced_modules_registered(advanced_system):
    cortex = advanced_system["cortex"]
    modules = cortex.list_modules()
    for name in ["general", "specter", "chronos", "dreamweaver", "serendipity", "forge"]:
        assert name in modules
