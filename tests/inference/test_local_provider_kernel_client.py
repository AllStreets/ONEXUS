"""Tests that LocalProvider routes through KernelHttpClient when supplied."""
from __future__ import annotations

import httpx
import pytest
import respx

from nexus.agents.manifest import Manifest
from nexus.context import as_agent
from nexus.inference.kernel_http_client import KernelHttpClient
from nexus.inference.local import LocalProvider
from nexus.kernel.aegis import Aegis, PermissionDenied


@pytest.fixture
def aegis_with_localhost_grant(tmp_path):
    a = Aegis(str(tmp_path / "a.db"))
    a.init_db()
    a.register_manifest(Manifest.model_validate({
        "manifest_version": 1, "slug": "echo", "name": "echo",
        "version": "1.0.0", "system": True,
        "publisher": {"type": "org", "handle": "t"}, "category": "test",
        "identity": {"mark": {"kind": "builtin:echo", "gradient": ["#fff", "#000"]}},
        "intents": [],
        "capabilities": {"tools": [], "declared": {
            "Routine": [], "Notable": ["network.outbound.localhost"],
            "Sensitive": [], "Privileged": [],
        }},
        "runtime": {"transport": "in_process"},
    }))
    a.grant("echo", "network.outbound.localhost")
    return a


@pytest.mark.asyncio
async def test_local_provider_routes_through_kernel_client(
    aegis_with_localhost_grant, respx_mock,
):
    respx_mock.post("http://localhost:8384/completion").mock(
        return_value=httpx.Response(200, json={"content": "hi there<|im_end|>"})
    )
    http = KernelHttpClient(aegis=aegis_with_localhost_grant)
    provider = LocalProvider(base_url="http://localhost:8384", http_client=http)
    async with as_agent("echo"):
        out = await provider.infer([{"role": "user", "content": "hello"}], max_tokens=5)
    assert "hi there" in out
    await http.aclose()


@pytest.mark.asyncio
async def test_local_provider_denied_when_undeclared(aegis_with_localhost_grant):
    """A host the agent has not declared must be denied by aegis.network()."""
    http = KernelHttpClient(aegis=aegis_with_localhost_grant)
    provider = LocalProvider(
        base_url="http://other-host.invalid:8384", http_client=http,
    )
    async with as_agent("echo"):
        with pytest.raises(PermissionDenied):
            await provider.infer(
                [{"role": "user", "content": "x"}], max_tokens=5,
            )
    await http.aclose()


@pytest.mark.asyncio
async def test_local_provider_passthrough_without_aegis(respx_mock):
    """Without a KernelHttpClient, LocalProvider falls back to direct httpx."""
    respx_mock.post("http://localhost:8384/completion").mock(
        return_value=httpx.Response(200, json={"content": "ok<|im_end|>"})
    )
    provider = LocalProvider(base_url="http://localhost:8384")  # no http_client
    out = await provider.infer([{"role": "user", "content": "hi"}], max_tokens=5)
    assert "ok" in out
