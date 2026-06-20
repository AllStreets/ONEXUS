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
        # Trust is a float in [0.0, 1.0]
        assert isinstance(first["trust"], (int, float))

    async def test_get_trust_detail(self, client, kernel):
        """GET /api/trust/{module} should return trust info with history."""
        resp = await client.get("/api/trust/council")
        assert resp.status_code == 200
        data = resp.json()
        assert data["module"] == "council"
        assert "trust" in data
        assert "history" in data
        assert isinstance(data["history"], list)

    async def test_get_trust_nonexistent(self, client):
        """GET /api/trust/nonexistent should return 404."""
        resp = await client.get("/api/trust/nonexistent")
        assert resp.status_code == 404

    async def test_adjust_trust(self, client, kernel):
        """POST /api/trust/{module}/adjust should change the trust score."""
        initial_trust = kernel.aegis.get_trust("council")
        resp = await client.post(
            "/api/trust/council/adjust",
            json={"delta": 0.1, "reason": "test adjustment"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["module"] == "council"
        assert data["delta"] == pytest.approx(0.1, abs=1e-6)
        assert data["new_trust"] == pytest.approx(min(1.0, initial_trust + 0.1), abs=1e-6)

    async def test_adjust_trust_negative(self, client, kernel):
        """Trust adjustment with negative delta should decrease trust."""
        # First set trust to 0.5 so a penalty doesn't clamp
        kernel.aegis.set_trust("council", 0.5)
        resp = await client.post(
            "/api/trust/council/adjust",
            json={"delta": -0.2, "reason": "penalty"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["delta"] == pytest.approx(-0.2, abs=1e-6)
        assert data["new_trust"] >= 0.0

    async def test_adjust_trust_nonexistent(self, client):
        """Adjusting trust for nonexistent module should return 404."""
        resp = await client.post(
            "/api/trust/nonexistent/adjust",
            json={"delta": 0.05, "reason": "test"},
        )
        assert resp.status_code == 404

    async def test_adjust_trust_invalid_body(self, client):
        """Missing required fields should return 422."""
        resp = await client.post(
            "/api/trust/council/adjust",
            json={"delta": 0.05},  # missing reason
        )
        assert resp.status_code == 422

    async def test_trust_history_populated(self, client, kernel):
        """After adjustments, trust history should contain entries."""
        kernel.aegis.set_trust("council", 0.3)
        kernel.aegis.set_trust("council", 0.4)

        resp = await client.get("/api/trust/council")
        data = resp.json()
        assert len(data["history"]) >= 2

    async def test_revoke_trust_drops_to_zero_and_collapses_grants(self, client, kernel):
        """POST /api/trust/{module}/revoke drops trust to 0.0 and collapses grants."""
        kernel.aegis.set_trust("council", 0.85)
        resp = await client.post("/api/trust/council/revoke")
        assert resp.status_code == 200
        data = resp.json()
        assert data["module"] == "council"
        assert data["revoked"] is True
        assert data["trust"] == 0.0
        # The revoke is durable — a subsequent read confirms 0.0.
        assert kernel.aegis.get_trust("council") == 0.0
