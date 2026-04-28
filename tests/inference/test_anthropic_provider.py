import pytest
from unittest.mock import patch, MagicMock
from nexus.inference.anthropic_provider import AnthropicProvider
from nexus.inference.provider import InferenceProvider


def test_anthropic_provider_is_inference_provider():
    provider = AnthropicProvider(api_key="test-key")
    assert isinstance(provider, InferenceProvider)


def test_anthropic_provider_name():
    provider = AnthropicProvider(api_key="test-key")
    assert provider.name == "anthropic"


def test_anthropic_provider_default_model():
    provider = AnthropicProvider(api_key="test-key")
    assert provider._model == "claude-sonnet-4-20250514"


def test_anthropic_provider_custom_model():
    provider = AnthropicProvider(api_key="test-key", model="claude-opus-4-20250514")
    assert provider._model == "claude-opus-4-20250514"


@pytest.mark.asyncio
async def test_anthropic_provider_infer_calls_sdk():
    provider = AnthropicProvider(api_key="test-key")
    messages = [
        {"role": "system", "content": "Be helpful."},
        {"role": "user", "content": "Hello"},
    ]

    mock_content_block = MagicMock()
    mock_content_block.text = "Hi from Claude!"
    mock_response = MagicMock()
    mock_response.content = [mock_content_block]

    with patch.object(provider._client.messages, "create", return_value=mock_response) as mock_create:
        result = await provider.infer(messages, max_tokens=512, temperature=0.5)
        assert result == "Hi from Claude!"
        mock_create.assert_called_once_with(
            model="claude-sonnet-4-20250514",
            system="Be helpful.",
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=512,
            temperature=0.5,
        )


@pytest.mark.asyncio
async def test_anthropic_provider_infer_no_system_message():
    provider = AnthropicProvider(api_key="test-key")
    messages = [{"role": "user", "content": "Hello"}]

    mock_content_block = MagicMock()
    mock_content_block.text = "Hi!"
    mock_response = MagicMock()
    mock_response.content = [mock_content_block]

    with patch.object(provider._client.messages, "create", return_value=mock_response) as mock_create:
        result = await provider.infer(messages)
        assert result == "Hi!"
        call_kwargs = mock_create.call_args[1]
        assert "system" not in call_kwargs or call_kwargs["system"] is None


@pytest.mark.asyncio
async def test_anthropic_provider_infer_error():
    provider = AnthropicProvider(api_key="test-key")
    messages = [{"role": "user", "content": "test"}]

    with patch.object(provider._client.messages, "create", side_effect=Exception("API error")):
        result = await provider.infer(messages)
        assert "[Inference error:" in result


@pytest.mark.asyncio
async def test_anthropic_provider_health_success():
    provider = AnthropicProvider(api_key="test-key")

    mock_content_block = MagicMock()
    mock_content_block.text = "ok"
    mock_response = MagicMock()
    mock_response.content = [mock_content_block]

    with patch.object(provider._client.messages, "create", return_value=mock_response):
        result = await provider.health()
        assert result is True


@pytest.mark.asyncio
async def test_anthropic_provider_health_failure():
    provider = AnthropicProvider(api_key="test-key")

    with patch.object(provider._client.messages, "create", side_effect=Exception("bad key")):
        result = await provider.health()
        assert result is False
