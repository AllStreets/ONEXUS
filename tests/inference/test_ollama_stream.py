"""OllamaProvider.infer_stream — native NDJSON token streaming."""
import httpx
import pytest

from nexus.inference.ollama import OllamaProvider


@pytest.mark.asyncio
async def test_ollama_stream_yields_ndjson_tokens(respx_mock):
    """stream=True NDJSON lines become individual yielded tokens; blank and
    malformed lines are skipped; empty-content keepalives produce nothing."""
    body = "\n".join([
        '{"message": {"content": "Hel"}, "done": false}',
        "",
        "not json at all",
        '{"message": {"content": ""}, "done": false}',
        '{"message": {"content": "lo"}, "done": false}',
        '{"message": {"content": ""}, "done": true}',
    ]) + "\n"
    respx_mock.post("http://localhost:11434/api/chat").mock(
        return_value=httpx.Response(200, text=body)
    )

    provider = OllamaProvider()
    chunks = [c async for c in provider.infer_stream([{"role": "user", "content": "hi"}])]
    assert chunks == ["Hel", "lo"]


@pytest.mark.asyncio
async def test_ollama_stream_stops_at_done(respx_mock):
    """Lines after the done:true frame are never yielded."""
    body = "\n".join([
        '{"message": {"content": "only"}, "done": true}',
        '{"message": {"content": "never"}, "done": false}',
    ]) + "\n"
    respx_mock.post("http://localhost:11434/api/chat").mock(
        return_value=httpx.Response(200, text=body)
    )

    provider = OllamaProvider()
    chunks = [c async for c in provider.infer_stream([{"role": "user", "content": "hi"}])]
    assert chunks == ["only"]


@pytest.mark.asyncio
async def test_ollama_stream_with_kernel_client_falls_back_to_single_chunk():
    """When an Aegis-gated KernelHttpClient is attached, streaming routes
    through the base-class fallback (one complete infer() response) so every
    outbound byte still passes the kernel network gate."""

    class _Resp:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content": "gated answer"}}

    class _FakeKernelClient:
        def __init__(self):
            self.posts = []

        async def post(self, url, json=None):
            self.posts.append((url, json))
            return _Resp()

    http = _FakeKernelClient()
    provider = OllamaProvider(http_client=http)
    chunks = [c async for c in provider.infer_stream([{"role": "user", "content": "hi"}])]
    assert chunks == ["gated answer"]
    # The gated request went out non-streaming through the kernel client.
    assert len(http.posts) == 1
    assert http.posts[0][1]["stream"] is False
