import pytest
from unittest.mock import AsyncMock, MagicMock
from nexus.modules.provenance import ProvenanceModule

@pytest.fixture
def module():
    return ProvenanceModule()

@pytest.fixture
def context():
    return {
        "llm": AsyncMock(return_value="Reasoning chain: input -> atlas analyzed facts -> cipher verified -> final conclusion."),
        "engram": MagicMock(),
        "chronicle": MagicMock(),
        "pulse": MagicMock(publish=AsyncMock()),
    }

def test_module_attributes(module):
    assert module.name == "provenance"
    assert module.description
    assert module.version

@pytest.mark.asyncio
async def test_handle_returns_string(module, context):
    context["chronicle"].query.return_value = [
        {"event_id": "abc123", "source": "cortex", "action": "route", "payload": {"target": "atlas"}},
        {"event_id": "def456", "source": "cortex", "action": "response", "payload": {"module": "atlas", "response_preview": "analysis"}},
    ]
    result = await module.handle("why do you think that", context)
    assert isinstance(result, str)

@pytest.mark.asyncio
async def test_handle_queries_chronicle(module, context):
    context["chronicle"].query.return_value = []
    await module.handle("show reasoning", context)
    context["chronicle"].query.assert_called()

@pytest.mark.asyncio
async def test_handle_builds_chain_from_logs(module, context):
    context["chronicle"].query.return_value = [
        {"event_id": "e1", "source": "cortex", "action": "route", "payload": {"target": "atlas"}},
        {"event_id": "e2", "source": "cortex", "action": "response", "payload": {"module": "atlas", "response_preview": "result"}},
    ]
    await module.handle("trace reasoning", context)
    context["llm"].assert_called_once()
    prompt = context["llm"].call_args[0][0]
    assert "atlas" in prompt

@pytest.mark.asyncio
async def test_handle_stores_chain_in_episodic(module, context):
    context["chronicle"].query.return_value = [{"event_id": "e1", "source": "x", "action": "y", "payload": {}}]
    await module.handle("provenance", context)
    context["engram"].episodic.store.assert_called()

@pytest.mark.asyncio
async def test_handle_with_no_logs(module, context):
    context["chronicle"].query.return_value = []
    result = await module.handle("why", context)
    assert isinstance(result, str)
    context["llm"].assert_not_called()
