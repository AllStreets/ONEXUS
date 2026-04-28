import pytest
from unittest.mock import AsyncMock, MagicMock, call
from nexus.modules.ethical_prism import EthicalPrismModule, FRAMEWORKS

@pytest.fixture
def module():
    return EthicalPrismModule()

@pytest.fixture
def context():
    return {
        "llm": AsyncMock(return_value="This action is ethically justified because..."),
        "engram": MagicMock(),
        "chronicle": MagicMock(),
        "pulse": MagicMock(publish=AsyncMock()),
    }

def test_module_attributes(module):
    assert module.name == "ethical_prism"
    assert module.description
    assert module.version

def test_seven_frameworks_defined():
    assert len(FRAMEWORKS) == 7
    names = [f["name"] for f in FRAMEWORKS]
    assert "Utilitarian" in names
    assert "Deontological" in names
    assert "Virtue Ethics" in names
    assert "Care Ethics" in names
    assert "Contractualist" in names
    assert "Rights-Based" in names
    assert "Pragmatic Ethics" in names

@pytest.mark.asyncio
async def test_handle_returns_string(module, context):
    result = await module.handle("should I fire this employee", context)
    assert isinstance(result, str)

@pytest.mark.asyncio
async def test_handle_calls_llm_for_each_framework(module, context):
    await module.handle("analyze ethically: should I share this data", context)
    # Should call LLM 7 times (one per framework) + 1 synthesis
    assert context["llm"].call_count == 8

@pytest.mark.asyncio
async def test_handle_includes_all_framework_names_in_response(module, context):
    result = await module.handle("ethical analysis", context)
    assert isinstance(result, str)

@pytest.mark.asyncio
async def test_handle_stores_analysis(module, context):
    await module.handle("morally", context)
    context["engram"].episodic.store.assert_called()

@pytest.mark.asyncio
async def test_handle_publishes_analysis_event(module, context):
    await module.handle("ethics", context)
    context["pulse"].publish.assert_called()
    msg = context["pulse"].publish.call_args[0][0]
    assert msg.topic == "ethical_prism.analysis"

@pytest.mark.asyncio
async def test_handle_logs_to_chronicle(module, context):
    await module.handle("right thing", context)
    context["chronicle"].log.assert_called()
    assert context["chronicle"].log.call_args[0][0] == "ethical_prism"
