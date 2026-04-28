import pytest
from unittest.mock import AsyncMock, MagicMock
from nexus.modules.sandbox import SandboxModule

@pytest.fixture
def module():
    return SandboxModule()

@pytest.fixture
def context():
    return {
        "llm": AsyncMock(return_value="Simulation result: if you send this email, likely outcome is a positive reply within 2 hours."),
        "engram": MagicMock(),
        "chronicle": MagicMock(),
        "pulse": MagicMock(publish=AsyncMock()),
    }

def test_module_attributes(module):
    assert module.name == "sandbox"
    assert module.description
    assert module.version

@pytest.mark.asyncio
async def test_handle_returns_string(module, context):
    context["engram"].episodic.recall.return_value = [{"content": "past interaction"}]
    result = await module.handle("what if I send the email", context)
    assert isinstance(result, str)

@pytest.mark.asyncio
async def test_handle_uses_memories_for_simulation(module, context):
    context["engram"].episodic.recall.return_value = [
        {"content": "User sent similar email last week, got reply in 1 hour"},
    ]
    await module.handle("simulate sending proposal", context)
    context["llm"].assert_called_once()
    prompt = context["llm"].call_args[0][0]
    assert "similar email" in prompt

@pytest.mark.asyncio
async def test_handle_publishes_simulation_event(module, context):
    context["engram"].episodic.recall.return_value = [{"content": "data"}]
    await module.handle("what if", context)
    context["pulse"].publish.assert_called()
    msg = context["pulse"].publish.call_args[0][0]
    assert msg.topic == "sandbox.simulation"

@pytest.mark.asyncio
async def test_handle_logs_to_chronicle(module, context):
    context["engram"].episodic.recall.return_value = [{"content": "data"}]
    await module.handle("simulate", context)
    context["chronicle"].log.assert_called()
    assert context["chronicle"].log.call_args[0][0] == "sandbox"

@pytest.mark.asyncio
async def test_handle_does_not_modify_real_memory(module, context):
    """Sandbox should NOT store results in episodic memory — simulation only."""
    context["engram"].episodic.recall.return_value = [{"content": "data"}]
    await module.handle("hypothetical", context)
    context["engram"].episodic.store.assert_not_called()
