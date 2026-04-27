"""
End-to-end test: user input -> Cortex routes -> General module responds ->
Engram stores memory -> Chronicle logs audit trail.
"""
import pytest
from nexus.config import NexusConfig
from nexus.kernel.engram import Engram
from nexus.kernel.chronicle import Chronicle
from nexus.kernel.aegis import Aegis
from nexus.kernel.pulse import Pulse
from nexus.kernel.cortex import Cortex
from nexus.modules.general import GeneralModule


@pytest.fixture
def nexus_system(tmp_config):
    """Full Nexus kernel with all components wired together."""
    engram = Engram(tmp_config.db_path)
    engram.init_db()
    chronicle = Chronicle(tmp_config.db_path)
    chronicle.init_db()
    aegis = Aegis(tmp_config.db_path)
    aegis.init_db()
    pulse = Pulse()

    cortex = Cortex(
        engram=engram,
        chronicle=chronicle,
        aegis=aegis,
        pulse=pulse,
        config=tmp_config,
    )

    general = GeneralModule()
    cortex.register_module(general)
    aegis.set_policy("general", allowed=True)

    # Mock LLM
    async def mock_llm(msg: str) -> str:
        return f"I understand your message about: {msg[:50]}"
    cortex.set_llm(mock_llm)

    return {
        "cortex": cortex,
        "engram": engram,
        "chronicle": chronicle,
        "aegis": aegis,
        "pulse": pulse,
    }


@pytest.mark.asyncio
async def test_full_loop(nexus_system):
    cortex = nexus_system["cortex"]
    engram = nexus_system["engram"]
    chronicle = nexus_system["chronicle"]

    # Send a message
    response = await cortex.process("What is the weather in Chicago?")

    # Module responded
    assert isinstance(response, str)
    assert len(response) > 0

    # Episodic memory recorded the interaction (FTS5 uses single token for reliable matching)
    memories = engram.episodic.recall("Chicago")
    assert len(memories) >= 1

    # Chronicle logged the routing and response
    route_events = chronicle.query(action="route")
    assert len(route_events) >= 1
    assert route_events[0]["payload"]["target"] == "general"

    response_events = chronicle.query(action="response")
    assert len(response_events) >= 1


@pytest.mark.asyncio
async def test_multiple_interactions_build_memory(nexus_system):
    cortex = nexus_system["cortex"]
    engram = nexus_system["engram"]

    await cortex.process("My name is Connor")
    await cortex.process("I work in logistics technology")
    await cortex.process("My favorite project is Nexus")

    memories = engram.episodic.recall("Connor")
    assert len(memories) >= 1
    memories = engram.episodic.recall("logistics")
    assert len(memories) >= 1


@pytest.mark.asyncio
async def test_denied_module_blocked(nexus_system):
    cortex = nexus_system["cortex"]
    aegis = nexus_system["aegis"]
    chronicle = nexus_system["chronicle"]

    # Deny general module
    aegis.set_policy("general", allowed=False)
    response = await cortex.process("This should be blocked")
    assert "not allowed" in response.lower() or "denied" in response.lower()

    # Chronicle logged the denial
    denials = chronicle.query(action="permission_denied")
    assert len(denials) >= 1


@pytest.mark.asyncio
async def test_offline_mode(tmp_config):
    """System works without LLM — returns offline response."""
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
    cortex.register_module(GeneralModule())
    aegis.set_policy("general", allowed=True)
    # No LLM set — offline mode

    response = await cortex.process("Hello")
    assert "offline" in response.lower() or "received" in response.lower()
