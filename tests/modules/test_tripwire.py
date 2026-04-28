import pytest
from unittest.mock import AsyncMock, MagicMock
from nexus.modules.tripwire import TripwireModule


@pytest.fixture
def module():
    return TripwireModule()


@pytest.fixture
def context():
    pulse = MagicMock()
    pulse.publish = AsyncMock()
    return {
        "llm": AsyncMock(return_value="CONTRADICTION DETECTED (confidence: 85%): You usually reject meetings before 10am, but you're accepting one now."),
        "engram": MagicMock(),
        "chronicle": MagicMock(),
        "pulse": pulse,
    }


def test_module_attributes(module):
    assert module.name == "tripwire"
    assert module.description
    assert module.version


@pytest.mark.asyncio
async def test_handle_returns_string(module, context):
    context["chronicle"].query.return_value = [
        {"source": "cortex", "action": "route", "payload": {"message_preview": "reject meeting"}},
    ]
    result = await module.handle("show my patterns", context)
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_handle_analyzes_decision_history(module, context):
    context["chronicle"].query.return_value = [
        {"source": "cortex", "action": "route", "payload": {"message_preview": "accept meeting at 8am"}},
        {"source": "cortex", "action": "route", "payload": {"message_preview": "reject morning call"}},
    ]
    await module.handle("check patterns", context)
    context["llm"].assert_called_once()


@pytest.mark.asyncio
async def test_handle_publishes_alert_on_contradiction(module, context):
    context["chronicle"].query.return_value = [{"source": "x", "action": "y", "payload": {}}]
    await module.handle("analyze", context)
    context["pulse"].publish.assert_called()
    msg = context["pulse"].publish.call_args[0][0]
    assert msg.topic == "tripwire.alert"


@pytest.mark.asyncio
async def test_handle_stores_pattern_model(module, context):
    context["chronicle"].query.return_value = [{"source": "x", "action": "y", "payload": {}}]
    await module.handle("my patterns", context)
    context["engram"].semantic.store.assert_called()


@pytest.mark.asyncio
async def test_handle_with_no_history(module, context):
    context["chronicle"].query.return_value = []
    result = await module.handle("show patterns", context)
    assert isinstance(result, str)
    context["llm"].assert_not_called()
