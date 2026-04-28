import pytest
from unittest.mock import AsyncMock, MagicMock
from nexus.modules.dream_loop import DreamLoopModule


@pytest.fixture
def module():
    return DreamLoopModule()


@pytest.fixture
def context():
    pulse = MagicMock()
    pulse.publish = AsyncMock()
    return {
        "llm": AsyncMock(return_value="Pattern discovered: you tend to ask about productivity on Mondays."),
        "engram": MagicMock(),
        "chronicle": MagicMock(),
        "pulse": pulse,
    }


def test_module_attributes(module):
    assert module.name == "dream_loop"
    assert module.description
    assert module.version


@pytest.mark.asyncio
async def test_handle_returns_string(module, context):
    context["engram"].episodic.recall.return_value = [
        {"content": "User asked about emails", "source": "user_input"},
        {"content": "User asked about schedule", "source": "user_input"},
    ]
    result = await module.handle("show dreams", context)
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_handle_calls_llm_with_memories(module, context):
    context["engram"].episodic.recall.return_value = [
        {"content": "Interaction 1"},
        {"content": "Interaction 2"},
    ]
    await module.handle("dream", context)
    context["llm"].assert_called_once()
    prompt = context["llm"].call_args[0][0]
    assert "Interaction 1" in prompt
    assert "Interaction 2" in prompt


@pytest.mark.asyncio
async def test_handle_stores_insight_in_semantic_memory(module, context):
    context["engram"].episodic.recall.return_value = [{"content": "data"}]
    await module.handle("dream", context)
    context["engram"].semantic.store.assert_called_once()
    call_args = context["engram"].semantic.store.call_args
    assert "dream_insight" in str(call_args)


@pytest.mark.asyncio
async def test_handle_publishes_notify_event(module, context):
    context["engram"].episodic.recall.return_value = [{"content": "data"}]
    await module.handle("dream", context)
    context["pulse"].publish.assert_called()
    msg = context["pulse"].publish.call_args[0][0]
    assert msg.topic == "notify.dream_loop"


@pytest.mark.asyncio
async def test_handle_logs_to_chronicle(module, context):
    context["engram"].episodic.recall.return_value = [{"content": "data"}]
    await module.handle("dream", context)
    context["chronicle"].log.assert_called()
    call_args = context["chronicle"].log.call_args
    assert call_args[0][0] == "dream_loop"
    assert call_args[0][1] == "dream_session"


@pytest.mark.asyncio
async def test_handle_with_no_memories(module, context):
    context["engram"].episodic.recall.return_value = []
    result = await module.handle("dream", context)
    assert isinstance(result, str)
    assert "no recent" in result.lower() or "nothing" in result.lower()
    context["llm"].assert_not_called()
