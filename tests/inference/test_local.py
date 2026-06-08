import json
import pytest
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
async def test_local_provider_infer_calls_endpoint(respx_mock):
    """Phase 6: LocalProvider uses httpx (via KernelHttpClient or direct).
    This test mocks httpx and verifies the prompt format passed in the request body.
    """
    import httpx as _httpx
    captured_request = {}
    def _capture(request):
        captured_request["body"] = json.loads(request.content)
        return _httpx.Response(200, json={"content": "response text"})
    respx_mock.post("http://localhost:8384/completion").mock(side_effect=_capture)

    provider = LocalProvider(base_url="http://localhost:8384")
    messages = [{"role": "user", "content": "test"}]
    result = await provider.infer(messages)
    assert result == "response text"
    assert "<|im_start|>user" in captured_request["body"]["prompt"]


@pytest.mark.asyncio
async def test_local_provider_infer_error_raises(respx_mock):
    """Phase 6: connection errors propagate as httpx exceptions (the old behaviour
    swallowed them into a string return; we changed to raise so callers can decide
    what to do with the failure mode)."""
    import httpx as _httpx
    respx_mock.post("http://localhost:99999/completion").mock(
        side_effect=_httpx.ConnectError("refused")
    )
    provider = LocalProvider(base_url="http://localhost:99999")
    with pytest.raises(_httpx.ConnectError):
        await provider.infer([{"role": "user", "content": "test"}])


@pytest.mark.asyncio
async def test_local_provider_health_returns_false_on_failure(respx_mock):
    """health() returns False when the /health endpoint is unreachable."""
    import httpx as _httpx
    respx_mock.get("http://localhost:99999/health").mock(
        side_effect=_httpx.ConnectError("refused")
    )
    provider = LocalProvider(base_url="http://localhost:99999")
    result = await provider.health()
    assert result is False


@pytest.mark.asyncio
async def test_local_provider_health_returns_true_on_success(respx_mock):
    """health() returns True when the /health endpoint returns 200."""
    import httpx as _httpx
    respx_mock.get("http://localhost:8384/health").mock(
        return_value=_httpx.Response(200)
    )
    provider = LocalProvider(base_url="http://localhost:8384")
    result = await provider.health()
    assert result is True
