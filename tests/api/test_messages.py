from __future__ import annotations

import json
import pytest

from nexus.inference.provider import ProviderUnavailable


def _parse_sse(body: str) -> list[dict]:
    return [
        json.loads(line.removeprefix("data: "))
        for line in body.strip().split("\n")
        if line.startswith("data: ")
    ]


class FakeStreamRouter:
    """Stands in for kernel.provider_router with a native token stream."""

    def __init__(self, tokens):
        self._tokens = tokens
        self.calls: list[list[dict]] = []

    def list_providers(self):
        return ["fake"]

    async def infer(self, messages, max_tokens=1024, temperature=0.7, provider=None):
        self.calls.append(messages)
        return "".join(self._tokens)

    async def infer_stream(self, messages, max_tokens=1024, temperature=0.7, provider=None):
        self.calls.append(messages)
        for t in self._tokens:
            yield t


class UnavailableRouter:
    """provider_router whose stream dies before the first token."""

    def list_providers(self):
        return []

    async def infer_stream(self, messages, max_tokens=1024, temperature=0.7, provider=None):
        raise ProviderUnavailable("none")
        yield ""  # pragma: no cover — makes this an async generator


@pytest.mark.asyncio
class TestMessageEndpoints:

    async def test_send_message(self, client, kernel):
        """POST /api/messages should route through Cortex and return a response."""
        resp = await client.post("/api/messages", json={"message": "hello world"})
        assert resp.status_code == 200
        data = resp.json()
        assert "response" in data
        assert len(data["response"]) > 0
        assert data["module"] is not None

    async def test_send_message_empty_rejected(self, client):
        """Empty message should be rejected by validation."""
        resp = await client.post("/api/messages", json={"message": ""})
        assert resp.status_code == 422

    async def test_send_message_with_context(self, client):
        """Context dict should be accepted without error."""
        resp = await client.post(
            "/api/messages",
            json={"message": "test message", "context": {"key": "value"}},
        )
        assert resp.status_code == 200

    async def test_stream_message(self, client):
        """POST /api/messages/stream should return SSE chunks."""
        resp = await client.post(
            "/api/messages/stream",
            json={"message": "hello"},
        )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]

        # Parse SSE events
        body = resp.text
        events = [
            line.removeprefix("data: ")
            for line in body.strip().split("\n")
            if line.startswith("data: ")
        ]
        assert len(events) >= 1

        # Last event should be type=done
        last = json.loads(events[-1])
        assert last["type"] == "done"

    async def test_stream_message_real_tokens(self, client, kernel):
        """With a streaming provider registered, SSE frames carry the raw
        provider tokens and the terminal frame reports streamed=True with
        module + memory_id."""
        kernel.provider_router = FakeStreamRouter(["Hel", "lo ", "world"])
        resp = await client.post("/api/messages/stream", json={"message": "hello"})
        assert resp.status_code == 200

        events = _parse_sse(resp.text)
        chunks = [e["content"] for e in events if e["type"] == "chunk"]
        assert chunks == ["Hel", "lo ", "world"]

        last = events[-1]
        assert last["type"] == "done"
        assert last["streamed"] is True
        assert last["module"]
        assert last["memory_id"]

        # The provider saw a persona system prompt + the user message.
        sent = kernel.provider_router.calls[0]
        assert sent[0]["role"] == "system"
        assert sent[-1] == {"role": "user", "content": "hello"}

    async def test_stream_message_side_effects_match_sync(self, client, kernel):
        """Streamed exchanges leave the same messages-level trace as the
        sync endpoint: Engram exchange record + chronicle 'exchange' log."""
        kernel.provider_router = FakeStreamRouter(["streamed reply"])
        await client.post("/api/messages/stream", json={"message": "trace me please"})

        results = kernel.engram.episodic.recall_recent(limit=5)
        contents = [r["content"] for r in results]
        assert any("USER: trace me please" in c and "streamed reply" in c for c in contents)

        entries = kernel.chronicle.query(source="messages", limit=10)
        assert any(e["action"] == "exchange" for e in entries)

    async def test_stream_message_falls_back_when_provider_unavailable(self, client, kernel):
        """When no provider can stream, the endpoint chunks the full Cortex
        pipeline response — same content as POST /api/messages — and still
        persists the exchange."""
        kernel.provider_router = UnavailableRouter()

        sync = await client.post("/api/messages", json={"message": "hello fallback"})
        expected = sync.json()["response"]

        resp = await client.post("/api/messages/stream", json={"message": "hello fallback"})
        events = _parse_sse(resp.text)
        body = "".join(e["content"] for e in events if e["type"] == "chunk")
        assert body == expected

        last = events[-1]
        assert last["type"] == "done"
        assert last["streamed"] is False
        assert last["memory_id"]

    async def test_message_stores_in_episodic(self, client, kernel):
        """After processing a message, episodic memory should contain it."""
        await client.post("/api/messages", json={"message": "remember this test"})
        results = kernel.engram.episodic.recall_recent(limit=5)
        contents = [r["content"] for r in results]
        assert any("remember this test" in c for c in contents)

    async def test_message_logs_to_chronicle(self, client, kernel):
        """Cortex should log route + response events to Chronicle."""
        await client.post("/api/messages", json={"message": "chronicle test"})
        entries = kernel.chronicle.query(source="cortex", limit=10)
        actions = [e["action"] for e in entries]
        assert "route" in actions
        assert "response" in actions
