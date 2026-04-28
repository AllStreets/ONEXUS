import pytest
from unittest.mock import AsyncMock, MagicMock
from nexus.modules.consciousness import ConsciousnessModule

@pytest.fixture
def module():
    return ConsciousnessModule()

@pytest.fixture
def context():
    return {
        "llm": AsyncMock(return_value="Journal Entry: My confidence in data analysis has increased after 3 successful Atlas sessions this week."),
        "engram": MagicMock(),
        "chronicle": MagicMock(),
        "pulse": MagicMock(publish=AsyncMock()),
    }

def test_module_attributes(module):
    assert module.name == "consciousness"
    assert module.description
    assert module.version

@pytest.mark.asyncio
async def test_handle_returns_string(module, context):
    context["chronicle"].query.return_value = [
        {"source": "cortex", "action": "response", "payload": {"module": "atlas"}},
    ]
    result = await module.handle("how are you", context)
    assert isinstance(result, str)

@pytest.mark.asyncio
async def test_handle_uses_chronicle_for_reflection(module, context):
    context["chronicle"].query.return_value = [
        {"source": "aegis", "action": "trust_change", "payload": {"module": "atlas", "delta": 5}},
        {"source": "cortex", "action": "response", "payload": {"module": "cipher"}},
    ]
    await module.handle("journal", context)
    context["llm"].assert_called_once()
    prompt = context["llm"].call_args[0][0]
    assert "atlas" in prompt or "cipher" in prompt

@pytest.mark.asyncio
async def test_handle_stores_journal_entry(module, context):
    context["chronicle"].query.return_value = [{"source": "x", "action": "y", "payload": {}}]
    await module.handle("self reflect", context)
    context["engram"].episodic.store.assert_called()
    call_args = context["engram"].episodic.store.call_args
    assert "consciousness" in str(call_args)

@pytest.mark.asyncio
async def test_handle_publishes_entry_event(module, context):
    context["chronicle"].query.return_value = [{"source": "x", "action": "y", "payload": {}}]
    await module.handle("introspect", context)
    context["pulse"].publish.assert_called()
    msg = context["pulse"].publish.call_args[0][0]
    assert msg.topic == "consciousness.entry"

@pytest.mark.asyncio
async def test_handle_logs_to_chronicle(module, context):
    context["chronicle"].query.return_value = [{"source": "x", "action": "y", "payload": {}}]
    await module.handle("how are you", context)
    context["chronicle"].log.assert_called()
    assert context["chronicle"].log.call_args[0][0] == "consciousness"
