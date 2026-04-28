import pytest
from unittest.mock import AsyncMock, MagicMock
from nexus.modules.adversarial import AdversarialModule


@pytest.fixture
def module():
    return AdversarialModule()


@pytest.fixture
def context():
    pulse = MagicMock()
    pulse.publish = AsyncMock()
    return {
        "llm": AsyncMock(return_value="Vulnerability found: module X fails on empty input."),
        "engram": MagicMock(),
        "chronicle": MagicMock(),
        "pulse": pulse,
        "aegis": MagicMock(),
    }


def test_module_attributes(module):
    assert module.name == "adversarial"
    assert module.description
    assert module.version


@pytest.mark.asyncio
async def test_handle_returns_string(module, context):
    context["chronicle"].query.return_value = [
        {"source": "cortex", "action": "response", "payload": {"module": "general", "response_preview": "ok"}},
    ]
    result = await module.handle("red team the system", context)
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_handle_analyzes_chronicle(module, context):
    context["chronicle"].query.return_value = [
        {"source": "cortex", "action": "response", "payload": {"module": "atlas", "response_preview": "error"}},
        {"source": "cortex", "action": "response", "payload": {"module": "cipher", "response_preview": "ok"}},
    ]
    await module.handle("stress test", context)
    context["chronicle"].query.assert_called()


@pytest.mark.asyncio
async def test_handle_calls_llm_with_logs(module, context):
    entries = [
        {"source": "cortex", "action": "response", "payload": {"module": "general", "response_preview": "test"}},
    ]
    context["chronicle"].query.return_value = entries
    await module.handle("red team", context)
    context["llm"].assert_called_once()
    prompt = context["llm"].call_args[0][0]
    assert "general" in prompt


@pytest.mark.asyncio
async def test_handle_publishes_report(module, context):
    context["chronicle"].query.return_value = [{"source": "x", "action": "y", "payload": {}}]
    await module.handle("attack", context)
    context["pulse"].publish.assert_called()
    msg = context["pulse"].publish.call_args[0][0]
    assert msg.topic == "adversarial.report"


@pytest.mark.asyncio
async def test_handle_logs_to_chronicle(module, context):
    context["chronicle"].query.return_value = [{"source": "x", "action": "y", "payload": {}}]
    await module.handle("harden", context)
    context["chronicle"].log.assert_called()
    call_args = context["chronicle"].log.call_args
    assert call_args[0][0] == "adversarial"


@pytest.mark.asyncio
async def test_handle_with_no_history(module, context):
    context["chronicle"].query.return_value = []
    result = await module.handle("red team", context)
    assert isinstance(result, str)
    assert "no recent" in result.lower() or "insufficient" in result.lower()
