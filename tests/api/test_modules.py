from __future__ import annotations

import pytest
from nexus.kernel.aegis import PermissionDenied


@pytest.mark.asyncio
class TestModuleEndpoints:

    async def test_list_modules(self, client):
        """GET /api/modules should list registered modules."""
        resp = await client.get("/api/modules")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 1
        names = [m["name"] for m in data["modules"]]
        # The test kernel registers CouncilModule as 'council'
        assert "council" in names

    async def test_get_module_detail(self, client):
        """GET /api/modules/council should return module info."""
        resp = await client.get("/api/modules/council")
        assert resp.status_code == 200
        module = resp.json()["module"]
        assert module["name"] == "council"
        assert "description" in module
        assert "version" in module
        assert isinstance(module["allowed"], bool)
        assert isinstance(module["trust"], (int, float))

    async def test_get_nonexistent_module(self, client):
        """GET /api/modules/nonexistent should return 404."""
        resp = await client.get("/api/modules/nonexistent")
        assert resp.status_code == 404

    async def test_deny_module(self, client, kernel):
        """POST /api/modules/council/deny should disable the module."""
        resp = await client.post("/api/modules/council/deny")
        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "deny"
        assert data["success"] is True

        # Verify the policy changed — check() should now raise PermissionDenied
        try:
            kernel.aegis.check("council", "handle")
            denied = False
        except PermissionDenied:
            denied = True
        assert denied

    async def test_allow_module(self, client, kernel):
        """POST /api/modules/council/allow should enable the module."""
        # First deny
        kernel.aegis.set_policy("council", allowed=False)
        try:
            kernel.aegis.check("council", "handle")
            denied = False
        except PermissionDenied:
            denied = True
        assert denied

        # Then allow via API
        resp = await client.post("/api/modules/council/allow")
        assert resp.status_code == 200
        # Should no longer raise
        kernel.aegis.check("council", "handle")  # raises if still denied

    async def test_allow_nonexistent_module(self, client):
        """Allowing a nonexistent module should return 404."""
        resp = await client.post("/api/modules/nonexistent/allow")
        assert resp.status_code == 404

    async def test_deny_nonexistent_module(self, client):
        resp = await client.post("/api/modules/nonexistent/deny")
        assert resp.status_code == 404

    async def test_module_info_fields(self, client):
        """Module info should contain all expected fields."""
        resp = await client.get("/api/modules/council")
        module = resp.json()["module"]
        expected_fields = {"name", "description", "version", "requires_network",
                           "allowed", "trust", "network_allowed"}
        assert expected_fields.issubset(set(module.keys()))
