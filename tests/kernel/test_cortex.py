import pytest
from nexus.kernel.cortex import Cortex
from nexus.kernel.engram import Engram
from nexus.kernel.chronicle import Chronicle
from nexus.kernel.aegis import Aegis
from nexus.kernel.pulse import Pulse
from nexus.modules.general import GeneralModule


@pytest.fixture
def kernel_deps(tmp_config):
    engram = Engram(tmp_config.db_path)
    engram.init_db()
    chronicle = Chronicle(tmp_config.db_path)
    chronicle.init_db()
    aegis = Aegis(tmp_config.db_path)
    aegis.init_db()
    pulse = Pulse()
    return {
        "engram": engram,
        "chronicle": chronicle,
        "aegis": aegis,
        "pulse": pulse,
        "config": tmp_config,
    }


@pytest.fixture
def cortex(kernel_deps):
    c = Cortex(**kernel_deps)
    c.register_module(GeneralModule())
    kernel_deps["aegis"].set_policy("general", allowed=True)
    return c


@pytest.mark.asyncio
async def test_route_to_general(cortex):
    response = await cortex.process("Hello, how are you?")
    assert isinstance(response, str)
    assert len(response) > 0


@pytest.mark.asyncio
async def test_route_logs_to_chronicle(cortex, kernel_deps):
    await cortex.process("Test message")
    events = kernel_deps["chronicle"].query(source="cortex")
    assert len(events) >= 1
    actions = [e["action"] for e in events]
    assert "route" in actions


@pytest.mark.asyncio
async def test_route_stores_episodic_memory(cortex, kernel_deps):
    await cortex.process("Remember this: my favorite color is blue")
    results = kernel_deps["engram"].episodic.recall("favorite color")
    assert len(results) >= 1


@pytest.mark.asyncio
async def test_blocked_module_returns_error(kernel_deps):
    c = Cortex(**kernel_deps)
    c.register_module(GeneralModule())
    # general is NOT allowed in aegis
    response = await c.process("test")
    assert "denied" in response.lower() or "not allowed" in response.lower()


def test_register_module(kernel_deps):
    c = Cortex(**kernel_deps)
    mod = GeneralModule()
    c.register_module(mod)
    assert "general" in c.list_modules()


def test_list_modules_empty(kernel_deps):
    c = Cortex(**kernel_deps)
    assert c.list_modules() == []


from nexus.modules.oracle import OracleModule
from nexus.modules.sentry import SentryModule


@pytest.fixture
def multi_cortex(kernel_deps):
    """Cortex with multiple modules registered."""
    c = Cortex(**kernel_deps)
    c.register_module(GeneralModule())
    c.register_module(OracleModule())
    c.register_module(SentryModule())
    kernel_deps["aegis"].set_policy("general", allowed=True)
    kernel_deps["aegis"].set_policy("oracle", allowed=True)
    kernel_deps["aegis"].set_policy("sentry", allowed=True)
    return c


@pytest.mark.asyncio
async def test_route_to_oracle(multi_cortex):
    response = await multi_cortex.process("Check my triggers and alerts")
    assert "oracle" in response.lower() or "trigger" in response.lower() or "no active" in response.lower()


@pytest.mark.asyncio
async def test_route_to_sentry(multi_cortex):
    response = await multi_cortex.process("What is my cognitive state and focus level?")
    assert "sentry" in response.lower() or "focus" in response.lower() or "fatigue" in response.lower()


@pytest.mark.asyncio
async def test_route_fallback_to_general(multi_cortex):
    response = await multi_cortex.process("Tell me a joke")
    # No keyword match, falls back to general
    assert isinstance(response, str)
    assert len(response) > 0
