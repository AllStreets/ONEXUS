"""Tests for KernelHttpClient: aegis-gated when context is set, passthrough otherwise."""
from __future__ import annotations

import pytest
import httpx
import respx

from nexus.agents.manifest import Manifest
from nexus.context import as_agent
from nexus.inference.kernel_http_client import KernelHttpClient
from nexus.kernel.aegis import Aegis, PermissionDenied


def _agent_with_domain(slug, domain):
    return Manifest.model_validate({
        "manifest_version": 1, "slug": slug, "name": slug,
        "version": "1.0.0", "system": False,
        "publisher": {"type": "org", "handle": "t"}, "category": "test",
        "identity": {"mark": {"kind": "svg", "gradient": ["#fff", "#000"]}},
        "intents": [],
        "capabilities": {"tools": [], "declared": {
            "Routine": [], "Notable": [f"network.outbound.{domain}"],
            "Sensitive": [], "Privileged": [],
        }},
        "runtime": {"transport": "stdio", "command": "x"},
    })


@pytest.fixture
def aegis(tmp_path):
    a = Aegis(str(tmp_path / "a.db"))
    a.init_db()
    a.register_manifest(_agent_with_domain("aider", "api.openai.com"))
    a.grant("aider", "network.outbound.api.openai.com")  # global
    return a


@pytest.mark.asyncio
async def test_passthrough_without_aegis_or_context(respx_mock):
    """Without aegis or context, behaves like a normal httpx.AsyncClient."""
    respx_mock.get("https://example.com/").mock(return_value=httpx.Response(200, json={"ok": True}))
    client = KernelHttpClient()
    r = await client.request("GET", "https://example.com/")
    assert r.status_code == 200
    await client.aclose()


@pytest.mark.asyncio
async def test_routes_through_aegis_when_attached(aegis, respx_mock):
    """When aegis + agent context are set, the call must be gated by aegis."""
    respx_mock.get("https://api.openai.com/v1/models").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    client = KernelHttpClient(aegis=aegis)
    async with as_agent("aider"):
        r = await client.request("GET", "https://api.openai.com/v1/models")
    assert r.status_code == 200
    await client.aclose()


@pytest.mark.asyncio
async def test_denies_undeclared_domain(aegis):
    """Aegis blocks an undeclared domain."""
    client = KernelHttpClient(aegis=aegis)
    async with as_agent("aider"):
        with pytest.raises(PermissionDenied):
            await client.request("GET", "https://evil.example.com/")
    await client.aclose()


@pytest.mark.asyncio
async def test_no_context_falls_back_to_passthrough(aegis, respx_mock):
    """If aegis is attached but no agent is in context, passes through (kernel paths)."""
    respx_mock.get("https://anywhere.com/").mock(return_value=httpx.Response(204))
    client = KernelHttpClient(aegis=aegis)
    r = await client.request("GET", "https://anywhere.com/")
    assert r.status_code == 204
    await client.aclose()
