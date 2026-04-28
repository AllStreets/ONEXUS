# tests/inference/test_openai_provider.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from nexus.inference.openai_provider import OpenAIProvider
from nexus.inference.provider import InferenceProvider


def test_openai_provider_is_inference_provider():
    provider = OpenAIProvider(api_key="test-key")
    assert isinstance(provider, InferenceProvider)


def test_openai_provider_name():
    provider = OpenAIProvider(api_key="test-key")
    assert provider.name == "openai"


def test_openai_provider_default_model():
    provider = OpenAIProvider(api_key="test-key")
    assert provider._model == "gpt-4o-mini"


def test_openai_provider_custom_model():
    provider = OpenAIProvider(api_key="test-key", model="gpt-4o")
    assert provider._model == "gpt-4o"


@pytest.mark.asyncio
async def test_openai_provider_infer_calls_sdk():
    provider = OpenAIProvider(api_key="test-key", model="gpt-4o-mini")
    messages = [
        {"role": "system", "content": "Be helpful."},
        {"role": "user", "content": "Hello"},
    ]

    mock_choice = MagicMock()
    mock_choice.message.content = "Hi there!"
    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]

    with patch.object(provider._client.chat.completions, "create", return_value=mock_completion) as mock_create:
        result = await provider.infer(messages, max_tokens=512, temperature=0.5)
        assert result == "Hi there!"
        mock_create.assert_called_once_with(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=512,
            temperature=0.5,
        )


@pytest.mark.asyncio
async def test_openai_provider_infer_error():
    provider = OpenAIProvider(api_key="test-key")
    messages = [{"role": "user", "content": "test"}]

    with patch.object(provider._client.chat.completions, "create", side_effect=Exception("API error")):
        result = await provider.infer(messages)
        assert "[Inference error:" in result


@pytest.mark.asyncio
async def test_openai_provider_health_success():
    provider = OpenAIProvider(api_key="test-key")

    mock_choice = MagicMock()
    mock_choice.message.content = "ok"
    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]

    with patch.object(provider._client.chat.completions, "create", return_value=mock_completion):
        result = await provider.health()
        assert result is True


@pytest.mark.asyncio
async def test_openai_provider_health_failure():
    provider = OpenAIProvider(api_key="test-key")

    with patch.object(provider._client.chat.completions, "create", side_effect=Exception("bad key")):
        result = await provider.health()
        assert result is False
