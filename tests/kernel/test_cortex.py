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
