# tests/test_batch6_integration.py
"""
Batch 6 integration: Council + Autonomic through Cortex.
"""
import pytest
from nexus.config import NexusConfig
from nexus.kernel.engram import Engram
from nexus.kernel.chronicle import Chronicle
from nexus.kernel.aegis import Aegis
from nexus.kernel.pulse import Pulse
from nexus.kernel.cortex import Cortex
from nexus.modules.general import GeneralModule
from nexus.modules.council import CouncilModule
from nexus.modules.autonomic import AutonomicModule
from nexus.modules.specter import SpecterModule
from nexus.modules.chronos import ChronosModule
from nexus.modules.serendipity import SerendipityModule


@pytest.fixture
def orchestration_system(tmp_config):
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

    council = CouncilModule()
    autonomic = AutonomicModule()

    delib_modules = {
        "specter": SpecterModule(),
        "chronos": ChronosModule(),
        "serendipity": SerendipityModule(),
    }
    council.set_modules(delib_modules)

    modules = {
        "general": GeneralModule(),
        "council": council,
        "autonomic": autonomic,
        **delib_modules,
    }

    for mod in modules.values():
        cortex.register_module(mod)
        aegis.set_policy(mod.name, allowed=True)

    return {"cortex": cortex, "council": council, "autonomic": autonomic}


@pytest.mark.asyncio
async def test_council_via_cortex(orchestration_system):
    cortex = orchestration_system["cortex"]
    response = await cortex.process("Council, deliberate on whether I should switch careers")
    assert "council" in response.lower() or "deliberation" in response.lower()


@pytest.mark.asyncio
async def test_autonomic_via_cortex(orchestration_system):
    cortex = orchestration_system["cortex"]
    response = await cortex.process("Show me what routines you've automated on my behalf")
    assert "autonomic" in response.lower() or "observing" in response.lower()


@pytest.mark.asyncio
async def test_autonomic_status_via_cortex(orchestration_system):
    autonomic = orchestration_system["autonomic"]
    autonomic.get_domain_trust("scheduling").trust_score = 50
    cortex = orchestration_system["cortex"]
    response = await cortex.process("Show autonomic trust status for all domains")
    assert "scheduling" in response.lower()


@pytest.mark.asyncio
async def test_council_deliberation_via_cortex(orchestration_system):
    cortex = orchestration_system["cortex"]
    response = await cortex.process("I need perspectives on this decision: should I invest in index funds?")
    assert "council" in response.lower() or "deliberation" in response.lower() or "participant" in response.lower()


@pytest.mark.asyncio
async def test_autonomic_kill_via_cortex(orchestration_system):
    autonomic = orchestration_system["autonomic"]
    autonomic.get_domain_trust("scheduling").trust_score = 80
    cortex = orchestration_system["cortex"]
    response = await cortex.process("Kill all autonomous permissions now")
    assert "revoked" in response.lower() or "autonomic" in response.lower()


@pytest.mark.asyncio
async def test_all_batch6_modules_registered(orchestration_system):
    cortex = orchestration_system["cortex"]
    modules = cortex.list_modules()
    assert "council" in modules
    assert "autonomic" in modules


@pytest.mark.asyncio
async def test_council_denied_without_permission(tmp_config):
    engram = Engram(tmp_config.db_path)
    engram.init_db()
    chronicle = Chronicle(tmp_config.db_path)
    chronicle.init_db()
    aegis = Aegis(tmp_config.db_path)
    aegis.init_db()
    pulse = Pulse()
    cortex = Cortex(engram=engram, chronicle=chronicle, aegis=aegis, pulse=pulse, config=tmp_config)
    cortex.register_module(CouncilModule())
    # Do NOT set policy -- should be denied
    response = await cortex.process("Council deliberate on this")
    assert "not allowed" in response.lower() or "denied" in response.lower() or "enable" in response.lower()
