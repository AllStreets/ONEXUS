"""Tests for Aegis.network — the outbound HTTP gateway."""
from __future__ import annotations

import pytest
import httpx

from nexus.kernel.aegis import Aegis, PermissionDenied
from nexus.agents.manifest import Manifest


def _agent_with_domains(slug: str, domains: list[str]) -> Manifest:
    declared_notable = [f"network.outbound.{d}" for d in domains]
    return Manifest.model_validate({
        "manifest_version": 1,
        "slug": slug, "name": slug, "version": "1.0.0", "system": False,
        "publisher": {"type": "org", "handle": "test"},
        "category": "test",
        "identity": {"mark": {"kind": "svg", "gradient": ["#fff", "#000"]}},
        "intents": [],
        "capabilities": {
            "tools": [],
            "declared": {
                "Routine": [], "Sensitive": [], "Privileged": [],
                "Notable": declared_notable,
            },
        },
        "runtime": {"transport": "stdio", "command": "x"},
    })


@pytest.fixture
def aegis(tmp_path):
    a = Aegis(str(tmp_path / "aegis.db"))
    a.init_db()
    a.register_manifest(_agent_with_domains("a", ["example.com"]))
    a.grant("a", "network.outbound.example.com")  # global grant
    return a


@pytest.mark.asyncio
async def test_allowed_domain_passes(aegis, respx_mock):
    """A declared + granted domain returns the response."""
    respx_mock.get("https://example.com/").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    resp = await aegis.network("a", "https://example.com/", method="GET")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


@pytest.mark.asyncio
async def test_undeclared_domain_denied(aegis):
    with pytest.raises(PermissionDenied):
        await aegis.network("a", "https://evil.com/", method="GET")


@pytest.mark.asyncio
async def test_declared_but_not_granted_prompts(aegis):
    aegis.register_manifest(_agent_with_domains("b", ["example.com"]))
    # No grant; default trust is OBSERVER; Notable requires grant or Executor
    with pytest.raises(PermissionDenied):
        await aegis.network("b", "https://example.com/", method="GET")


@pytest.mark.asyncio
async def test_rate_limit_blocks_after_threshold(aegis, respx_mock):
    """Per-agent rate limit (default 60 rpm) blocks burst."""
    respx_mock.get("https://example.com/").mock(
        return_value=httpx.Response(200, json={})
    )
    aegis.set_rate_limit("a", per_minute=2)
    await aegis.network("a", "https://example.com/", method="GET")
    await aegis.network("a", "https://example.com/", method="GET")
    with pytest.raises(PermissionDenied):
        await aegis.network("a", "https://example.com/", method="GET")
