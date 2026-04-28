import pytest
from unittest.mock import AsyncMock, MagicMock
from nexus.modules.symbiosis import SymbiosisModule

@pytest.fixture
def module():
    return SymbiosisModule()

@pytest.fixture
def context():
    return {
        "llm": AsyncMock(return_value="Strongest pathway: atlas -> cipher (0.92). Emerging: oracle -> prism (0.67)."),
        "engram": MagicMock(),
        "chronicle": MagicMock(),
        "pulse": MagicMock(publish=AsyncMock()),
    }

def test_module_attributes(module):
    assert module.name == "symbiosis"
    assert module.description
    assert module.version

@pytest.mark.asyncio
async def test_handle_returns_string(module, context):
    context["chronicle"].query.return_value = [
        {"source": "cortex", "action": "route", "payload": {"target": "atlas"}},
        {"source": "cortex", "action": "response", "payload": {"module": "atlas", "response_preview": "ok"}},
    ]
    result = await module.handle("show neural pathways", context)
    assert isinstance(result, str)

@pytest.mark.asyncio
async def test_handle_analyzes_routing_history(module, context):
    context["chronicle"].query.return_value = [
        {"source": "cortex", "action": "route", "payload": {"target": "atlas"}},
        {"source": "cortex", "action": "route", "payload": {"target": "cipher"}},
        {"source": "cortex", "action": "route", "payload": {"target": "atlas"}},
    ]
    await module.handle("symbiosis", context)
    context["llm"].assert_called_once()

@pytest.mark.asyncio
async def test_handle_stores_pathway_map(module, context):
    context["chronicle"].query.return_value = [{"source": "x", "action": "y", "payload": {}}]
    await module.handle("routing map", context)
    context["engram"].semantic.store.assert_called()
    call_args = context["engram"].semantic.store.call_args
    assert "symbiosis" in str(call_args)

@pytest.mark.asyncio
async def test_handle_publishes_update_event(module, context):
    context["chronicle"].query.return_value = [{"source": "x", "action": "y", "payload": {}}]
    await module.handle("pathways", context)
    context["pulse"].publish.assert_called()
    msg = context["pulse"].publish.call_args[0][0]
    assert msg.topic == "symbiosis.pathway_updated"

@pytest.mark.asyncio
async def test_handle_with_no_history(module, context):
    context["chronicle"].query.return_value = []
    result = await module.handle("show pathways", context)
    assert isinstance(result, str)
    context["llm"].assert_not_called()
