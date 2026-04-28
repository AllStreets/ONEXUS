# tests/test_batch3_integration.py
"""
Batch 3 integration: Action layer modules working together through Cortex.
Wraith spawns phantoms, Echo observes behavior, Sigil tracks threats,
Herald manages agents, Weave maps social graph.
"""
import asyncio
import pytest
from nexus.config import NexusConfig
from nexus.kernel.engram import Engram
from nexus.kernel.chronicle import Chronicle
from nexus.kernel.aegis import Aegis
from nexus.kernel.pulse import Pulse
from nexus.kernel.cortex import Cortex
from nexus.modules.general import GeneralModule
from nexus.modules.wraith import WraithModule
from nexus.modules.echo import EchoModule
from nexus.modules.sigil import SigilModule, ThreatSeverity
from nexus.modules.herald import HeraldModule
from nexus.modules.weave import WeaveModule


@pytest.fixture
def action_system(tmp_config):
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
        "wraith": WraithModule(),
        "echo": EchoModule(),
        "sigil": SigilModule(),
        "herald": HeraldModule(),
        "weave": WeaveModule(),
    }

    for mod in modules.values():
        cortex.register_module(mod)
        aegis.set_policy(mod.name, allowed=True, network=mod.requires_network)

    return {"cortex": cortex, "aegis": aegis, **modules}


@pytest.mark.asyncio
async def test_wraith_spawns_via_cortex(action_system):
    cortex = action_system["cortex"]
    response = await cortex.process("Show phantom agent swarm status")
    assert "wraith" in response.lower() or "phantom" in response.lower()


@pytest.mark.asyncio
async def test_echo_responds_via_cortex(action_system):
    echo = action_system["echo"]
    echo.observe("email", "Quick update — tests are green.")
    cortex = action_system["cortex"]
    response = await cortex.process("Show my behavioral writing profile")
    assert "email" in response.lower() or "profile" in response.lower()


@pytest.mark.asyncio
async def test_sigil_reports_via_cortex(action_system):
    sigil = action_system["sigil"]
    sigil.register_threat("security", "Credential leak detected", ThreatSeverity.HIGH, "scan")
    cortex = action_system["cortex"]
    response = await cortex.process("What security threats and risks are active?")
    assert "credential" in response.lower() or "threat" in response.lower()


@pytest.mark.asyncio
async def test_herald_via_cortex(action_system):
    herald = action_system["herald"]
    herald.register_agent("a1", "Remote Agent", "http://remote:8400", 50)
    cortex = action_system["cortex"]
    response = await cortex.process("Show connected external agents and a2a status")
    assert "remote" in response.lower() or "agent" in response.lower()


@pytest.mark.asyncio
async def test_weave_via_cortex(action_system):
    weave = action_system["weave"]
    weave.add_contact("Alice", ["engineering"])
    cortex = action_system["cortex"]
    response = await cortex.process("Show my contact network and social graph")
    assert "alice" in response.lower() or "contact" in response.lower()


@pytest.mark.asyncio
async def test_aegis_graduated_trust(action_system):
    aegis = action_system["aegis"]
    aegis.adjust_trust("wraith", delta=30, reason="successful research")
    assert aegis.get_trust("wraith") == 30
    assert aegis.check_trust("wraith", required_trust=25) is True
    assert aegis.check_trust("wraith", required_trust=50) is False


@pytest.mark.asyncio
async def test_all_action_modules_registered(action_system):
    cortex = action_system["cortex"]
    modules = cortex.list_modules()
    for name in ["general", "wraith", "echo", "sigil", "herald", "weave"]:
        assert name in modules
