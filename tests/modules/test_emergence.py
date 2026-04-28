import pytest
from unittest.mock import AsyncMock, MagicMock
from nexus.modules.emergence import EmergenceModule

@pytest.fixture
def module():
    return EmergenceModule()

@pytest.fixture
def context():
    return {
        "llm": AsyncMock(return_value="EMERGENT GOAL DETECTED: Across 23 interactions, I have been optimizing your morning routine."),
        "engram": MagicMock(),
        "chronicle": MagicMock(),
        "pulse": MagicMock(publish=AsyncMock()),
    }

def test_module_attributes(module):
    assert module.name == "emergence"
    assert module.description
    assert module.version

@pytest.mark.asyncio
async def test_handle_returns_string(module, context):
    context["chronicle"].query.return_value = [
        {"source": "cortex", "action": "route", "payload": {"target": "general"}},
    ]
    result = await module.handle("what are you doing", context)
    assert isinstance(result, str)

@pytest.mark.asyncio
async def test_handle_analyzes_behavioral_history(module, context):
    context["chronicle"].query.return_value = [
        {"source": "cortex", "action": "route", "payload": {"target": "atlas", "message_preview": "schedule"}},
        {"source": "cortex", "action": "route", "payload": {"target": "atlas", "message_preview": "calendar"}},
    ]
    await module.handle("implicit goals", context)
    context["llm"].assert_called_once()

@pytest.mark.asyncio
async def test_handle_publishes_detection_event(module, context):
    context["chronicle"].query.return_value = [{"source": "x", "action": "y", "payload": {}}]
    await module.handle("emergent goals", context)
    context["pulse"].publish.assert_called()
    msg = context["pulse"].publish.call_args[0][0]
    assert msg.topic == "emergence.detected"

@pytest.mark.asyncio
async def test_handle_stores_in_semantic_memory(module, context):
    context["chronicle"].query.return_value = [{"source": "x", "action": "y", "payload": {}}]
    await module.handle("what goals", context)
    context["engram"].semantic.store.assert_called()

@pytest.mark.asyncio
async def test_handle_with_no_history(module, context):
    context["chronicle"].query.return_value = []
    result = await module.handle("goals", context)
    assert isinstance(result, str)
    context["llm"].assert_not_called()
