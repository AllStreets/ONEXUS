import json
import pytest
from unittest.mock import patch, MagicMock
from nexus.inference.local import LocalProvider
from nexus.inference.provider import InferenceProvider


def test_local_provider_is_inference_provider():
    provider = LocalProvider(base_url="http://localhost:8384")
    assert isinstance(provider, InferenceProvider)


def test_local_provider_name():
    provider = LocalProvider(base_url="http://localhost:8384")
    assert provider.name == "local"


def test_local_provider_converts_messages_to_chatml():
    provider = LocalProvider(base_url="http://localhost:8384")
    messages = [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Hello"},
    ]
    prompt = provider._messages_to_chatml(messages)
    assert "<|im_start|>system" in prompt
    assert "You are helpful." in prompt
    assert "<|im_start|>user" in prompt
    assert "Hello" in prompt
    assert prompt.endswith("<|im_start|>assistant\n")


def test_local_provider_chatml_with_history():
    provider = LocalProvider(base_url="http://localhost:8384")
    messages = [
        {"role": "system", "content": "System."},
        {"role": "user", "content": "Q1"},
        {"role": "assistant", "content": "A1"},
        {"role": "user", "content": "Q2"},
    ]
    prompt = provider._messages_to_chatml(messages)
    assert "Q1" in prompt
    assert "A1" in prompt
    assert "Q2" in prompt


@pytest.mark.asyncio
async def test_local_provider_infer_calls_endpoint():
    provider = LocalProvider(base_url="http://localhost:8384")
    messages = [{"role": "user", "content": "test"}]

    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({"content": "response text"}).encode()
    mock_response.status = 200
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_response) as mock_urlopen:
        result = await provider.infer(messages)
        assert result == "response text"
        mock_urlopen.assert_called_once()
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        body = json.loads(req.data)
        assert "<|im_start|>user" in body["prompt"]


@pytest.mark.asyncio
async def test_local_provider_infer_error_returns_message():
    provider = LocalProvider(base_url="http://localhost:99999")
    messages = [{"role": "user", "content": "test"}]

    with patch("urllib.request.urlopen", side_effect=Exception("Connection refused")):
        result = await provider.infer(messages)
        assert "[Inference error:" in result


def test_local_provider_health_returns_false_on_failure():
    provider = LocalProvider(base_url="http://localhost:99999")
    with patch("urllib.request.urlopen", side_effect=Exception("refused")):
        assert provider.health() is False


def test_local_provider_health_returns_true_on_success():
    provider = LocalProvider(base_url="http://localhost:8384")
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_response):
        assert provider.health() is True
