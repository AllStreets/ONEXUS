from __future__ import annotations

import json
import pytest


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
