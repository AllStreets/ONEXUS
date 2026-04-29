from __future__ import annotations

import pytest


@pytest.mark.asyncio
class TestChronicleEndpoints:

    async def test_query_empty(self, client):
        """GET /api/chronicle with no events should return empty list."""
        resp = await client.get("/api/chronicle")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["entries"], list)
        assert data["count"] >= 0

    async def test_query_after_logging(self, client, kernel):
        """After logging events, they should appear in query results."""
        kernel.chronicle.log("test_source", "test_action", {"key": "value"})
        kernel.chronicle.log("test_source", "other_action", {"x": 1})

        resp = await client.get("/api/chronicle")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 2

    async def test_query_filter_by_source(self, client, kernel):
        """Filter by source should only return matching entries."""
        kernel.chronicle.log("alpha", "event_a", {})
        kernel.chronicle.log("beta", "event_b", {})

        resp = await client.get("/api/chronicle", params={"source": "alpha"})
        assert resp.status_code == 200
        data = resp.json()
        for entry in data["entries"]:
            assert entry["source"] == "alpha"

    async def test_query_filter_by_event_type(self, client, kernel):
        """Filter by event_type should only return matching actions."""
        kernel.chronicle.log("src", "create", {})
        kernel.chronicle.log("src", "delete", {})

        resp = await client.get("/api/chronicle", params={"event_type": "create"})
        assert resp.status_code == 200
        data = resp.json()
        for entry in data["entries"]:
            assert entry["action"] == "create"

    async def test_query_with_limit(self, client, kernel):
        """Limit parameter should restrict result count."""
        for i in range(10):
            kernel.chronicle.log("bulk", f"event_{i}", {})

        resp = await client.get("/api/chronicle", params={"source": "bulk", "limit": 3})
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] <= 3

    async def test_stats(self, client, kernel):
        """GET /api/chronicle/stats should return aggregate stats."""
        kernel.chronicle.log("mod_a", "route", {})
        kernel.chronicle.log("mod_a", "route", {})
        kernel.chronicle.log("mod_b", "error", {})

        resp = await client.get("/api/chronicle/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_events"] >= 3
        assert "by_action" in data
        assert "by_source" in data
        assert isinstance(data["by_action"], dict)
        assert isinstance(data["by_source"], dict)

    async def test_entry_structure(self, client, kernel):
        """Each chronicle entry should have the expected fields."""
        kernel.chronicle.log("struct_test", "check", {"detail": "yes"})
        resp = await client.get("/api/chronicle", params={"source": "struct_test"})
        data = resp.json()
        assert data["count"] >= 1
        entry = data["entries"][0]
        assert "event_id" in entry
        assert "timestamp" in entry
        assert "source" in entry
        assert "action" in entry
        assert "payload" in entry
        assert entry["payload"]["detail"] == "yes"
