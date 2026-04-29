from __future__ import annotations

import pytest


@pytest.mark.asyncio
class TestTrustEndpoints:

    async def test_get_all_trust(self, client):
        """GET /api/trust should return trust scores for all modules."""
        resp = await client.get("/api/trust")
        assert resp.status_code == 200
        data = resp.json()
        assert "scores" in data
        assert len(data["scores"]) >= 1
        first = data["scores"][0]
        assert "module" in first
        assert "trust" in first
        assert isinstance(first["trust"], int)

    async def test_get_trust_detail(self, client, kernel):
        """GET /api/trust/{module} should return trust info with history."""
        resp = await client.get("/api/trust/general")
        assert resp.status_code == 200
        data = resp.json()
        assert data["module"] == "general"
        assert "trust" in data
        assert "history" in data
        assert isinstance(data["history"], list)

    async def test_get_trust_nonexistent(self, client):
        """GET /api/trust/nonexistent should return 404."""
        resp = await client.get("/api/trust/nonexistent")
        assert resp.status_code == 404

    async def test_adjust_trust(self, client, kernel):
        """POST /api/trust/{module}/adjust should change the trust score."""
        initial_trust = kernel.aegis.get_trust("general")
        resp = await client.post(
            "/api/trust/general/adjust",
            json={"delta": 10, "reason": "test adjustment"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["module"] == "general"
        assert data["delta"] == 10
        assert data["new_trust"] == min(100, initial_trust + 10)

    async def test_adjust_trust_negative(self, client, kernel):
        """Trust adjustment with negative delta should decrease trust."""
        # First set trust to 50 so we can decrease
        kernel.aegis.adjust_trust("general", 50, "setup")
        resp = await client.post(
            "/api/trust/general/adjust",
            json={"delta": -20, "reason": "penalty"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["delta"] == -20
        assert data["new_trust"] >= 0

    async def test_adjust_trust_nonexistent(self, client):
        """Adjusting trust for nonexistent module should return 404."""
        resp = await client.post(
            "/api/trust/nonexistent/adjust",
            json={"delta": 5, "reason": "test"},
        )
        assert resp.status_code == 404

    async def test_adjust_trust_invalid_body(self, client):
        """Missing required fields should return 422."""
        resp = await client.post(
            "/api/trust/general/adjust",
            json={"delta": 5},  # missing reason
        )
        assert resp.status_code == 422

    async def test_trust_history_populated(self, client, kernel):
        """After adjustments, trust history should contain entries."""
        kernel.aegis.adjust_trust("general", 5, "history test 1")
        kernel.aegis.adjust_trust("general", 3, "history test 2")

        resp = await client.get("/api/trust/general")
        data = resp.json()
        assert len(data["history"]) >= 2
        reasons = [h["reason"] for h in data["history"]]
        assert "history test 1" in reasons
        assert "history test 2" in reasons
