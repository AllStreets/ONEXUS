# tests/inference/test_llm.py
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from nexus.inference.llm import LLMClient
from nexus.inference.provider import InferenceProvider
from nexus.inference.router import ProviderRouter


@pytest.fixture
def mock_router():
    router = MagicMock(spec=ProviderRouter)
    router.infer = AsyncMock(return_value="routed response")
    router.health = AsyncMock(return_value={"local": True})
    router.list_providers = MagicMock(return_value=["local"])
    return router


@pytest.fixture
def llm(mock_router):
    return LLMClient(router=mock_router)


@pytest.mark.asyncio
async def test_llm_infer_delegates_to_router(llm, mock_router):
    """infer() with a raw prompt string should wrap it in messages and route."""
    result = await llm.infer("What is 2+2?")
    assert result == "routed response"
    mock_router.infer.assert_called_once()
    call_args = mock_router.infer.call_args
    messages = call_args[0][0]
    assert any("2+2" in m["content"] for m in messages)


@pytest.mark.asyncio
async def test_llm_chat_delegates_to_router(llm, mock_router):
    """chat() should convert system/user/history to messages and route."""
    result = await llm.chat(
        system="Be helpful.",
        user="Hello",
        history=[{"role": "user", "content": "Q"}, {"role": "assistant", "content": "A"}],
    )
    assert result == "routed response"
    mock_router.infer.assert_called_once()
    call_args = mock_router.infer.call_args
    messages = call_args[0][0]
    roles = [m["role"] for m in messages]
    assert "system" in roles
    assert roles.count("user") == 2


@pytest.mark.asyncio
async def test_llm_chat_no_history(llm, mock_router):
    """chat() without history sends system + user messages."""
    await llm.chat(system="System.", user="Question")
    messages = mock_router.infer.call_args[0][0]
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"


@pytest.mark.asyncio
async def test_llm_infer_with_provider(llm, mock_router):
    """infer() can specify a provider name."""
    await llm.infer("test", provider="openai")
    assert mock_router.infer.call_args[1].get("provider") == "openai"


@pytest.mark.asyncio
async def test_llm_chat_with_provider(llm, mock_router):
    """chat() can specify a provider name."""
    await llm.chat(system="S", user="U", provider="anthropic")
    assert mock_router.infer.call_args[1].get("provider") == "anthropic"


@pytest.mark.asyncio
async def test_llm_infer_passes_max_tokens_and_temperature(llm, mock_router):
    """infer() forwards max_tokens and temperature to the router."""
    await llm.infer("test", max_tokens=256, temperature=0.3)
    kwargs = mock_router.infer.call_args[1]
    assert kwargs["max_tokens"] == 256
    assert kwargs["temperature"] == 0.3


def test_llm_health(llm, mock_router):
    """health() delegates to the router."""
    mock_router.health = MagicMock(return_value={"local": True})
    assert llm.health() is not None


def test_llm_backward_compat_base_url():
    """LLMClient still accepts base_url for backward compatibility."""
    client = LLMClient(base_url="http://localhost:8384")
    assert client._router is not None


def test_llm_accepts_router():
    """LLMClient accepts a pre-built router."""
    router = MagicMock(spec=ProviderRouter)
    client = LLMClient(router=router)
    assert client._router is router
