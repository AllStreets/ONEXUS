"""End-to-end Phase 6 smoke — provider call → KernelHttpClient → aegis.network → chronicle log."""
from __future__ import annotations

import httpx
import pytest
import respx

from nexus.agents.in_process_agent import InProcessAgent
from nexus.agents.manifest import Manifest
from nexus.context import as_agent, current_agent_slug
from nexus.inference.kernel_http_client import KernelHttpClient
from nexus.inference.local import LocalProvider
from nexus.kernel.aegis import Aegis, PermissionDenied
from nexus.kernel.chronicle import Chronicle
from nexus.modules.base import NexusModule


def _inferring_module_manifest():
    return Manifest.model_validate({
        "manifest_version": 1, "slug": "inferring-mod", "name": "inferring-mod",
        "version": "0.1.0", "system": True,
        "publisher": {"type": "org", "handle": "test"}, "category": "test",
        "identity": {"mark": {"kind": "builtin:inferring-mod", "gradient": ["#fff", "#000"]}},
        "intents": [],
        "capabilities": {
            "tools": [{"name": "handle", "class": "Routine"}],
            "declared": {
                "Routine": [], "Notable": ["network.outbound.localhost"],
                "Sensitive": [], "Privileged": [],
            },
        },
        "runtime": {"transport": "in_process"},
    })


@pytest.mark.asyncio
async def test_end_to_end_provider_call_through_aegis(tmp_path, respx_mock):
    """An agent calls a provider; the request flows through aegis.network()
    and lands in Chronicle as `network_request`."""
    chronicle = Chronicle(str(tmp_path / "c.db"))
    chronicle.init_db()
    aegis = Aegis(str(tmp_path / "a.db"), chronicle=chronicle)
    aegis.init_db()
    aegis.register_manifest(_inferring_module_manifest())
    aegis.grant("inferring-mod", "network.outbound.localhost")

    respx_mock.post("http://localhost:8384/completion").mock(
        return_value=httpx.Response(200, json={"content": "hi<|im_end|>"})
    )

    http = KernelHttpClient(aegis=aegis)
    provider = LocalProvider(base_url="http://localhost:8384", http_client=http)

    class _Module(NexusModule):
        name = "inferring-mod"
        description = "uses LocalProvider"
        version = "0.1.0"

        @classmethod
        def manifest(cls):
            return _inferring_module_manifest()

        async def handle(self, message, context):
            return await provider.infer([{"role": "user", "content": message}], max_tokens=5)

    agent = InProcessAgent(_Module(), aegis=aegis)
    result = await agent.call_tool("handle", {"message": "hi", "context": {}})
    assert "hi" in result
    await http.aclose()

    # Chronicle must contain a network_request entry
    events = chronicle.query(source="aegis", action="network_request", limit=10)
    assert any(
        e["payload"].get("agent") == "inferring-mod"
        and "localhost" in e["payload"].get("url", "")
        for e in events
    ), f"no network_request logged for inferring-mod; got: {events}"


@pytest.mark.asyncio
async def test_kernel_never_directly_imports_httpx_in_kernel_modules():
    """The kernel/ modules (cortex, engram, pulse, chronicle, aegis) must NOT
    issue direct outbound HTTP themselves. Aegis is allowed to import httpx
    (it IS the gateway). Everything else must not. This is a guard-rail test —
    a static check that the kernel's local-first promise still holds."""
    from pathlib import Path
    kernel_dir = Path("nexus/kernel")
    for f in kernel_dir.glob("*.py"):
        if f.name in ("__init__.py", "aegis.py"):
            # __init__ is allowed; aegis.py is the gateway itself
            continue
        text = f.read_text()
        # Reject obvious outbound HTTP libraries
        assert "import httpx" not in text and "from httpx" not in text, (
            f"{f}: kernel module must not import httpx directly"
        )
        assert "urlopen" not in text, (
            f"{f}: kernel module must not use urllib.urlopen directly"
        )
        assert "requests.get" not in text and "requests.post" not in text, (
            f"{f}: kernel module must not use requests directly"
        )
