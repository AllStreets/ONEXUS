"""Tests that AnthropicProvider routes through AegisTransport when aegis is supplied."""
from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest
import respx

from nexus.agents.manifest import Manifest
from nexus.context import as_agent
from nexus.inference.anthropic_provider import AnthropicProvider
from nexus.kernel.aegis import Aegis, PermissionDenied


def _anthropic_messages_response(text: str) -> dict:
    return {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": text}],
        "model": "claude-sonnet-4-20250514",
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }


@pytest.fixture
def aegis_with_anthropic_grant(tmp_path):
    a = Aegis(str(tmp_path / "a.db"))
    a.init_db()
    a.register_manifest(Manifest.model_validate({
        "manifest_version": 1, "slug": "ant-agent", "name": "ant-agent",
        "version": "1.0.0", "system": True,
        "publisher": {"type": "org", "handle": "t"}, "category": "test",
        "identity": {"mark": {"kind": "builtin:echo", "gradient": ["#fff", "#000"]}},
        "intents": [],
        "capabilities": {"tools": [], "declared": {
            "Routine": [], "Notable": ["network.outbound.api.anthropic.com"],
            "Sensitive": [], "Privileged": [],
        }},
        "runtime": {"transport": "in_process"},
    }))
    a.grant("ant-agent", "network.outbound.api.anthropic.com")
    return a


@pytest.fixture
def aegis_no_anthropic_grant(tmp_path):
    """Aegis with agent registered but NO grant for api.anthropic.com."""
    a = Aegis(str(tmp_path / "b.db"))
    a.init_db()
    a.register_manifest(Manifest.model_validate({
        "manifest_version": 1, "slug": "ant-agent", "name": "ant-agent",
        "version": "1.0.0", "system": True,
        "publisher": {"type": "org", "handle": "t"}, "category": "test",
        "identity": {"mark": {"kind": "builtin:echo", "gradient": ["#fff", "#000"]}},
        "intents": [],
        "capabilities": {"tools": [], "declared": {
            "Routine": [], "Notable": [],
            "Sensitive": [], "Privileged": [],
        }},
        "runtime": {"transport": "in_process"},
    }))
    return a


@pytest.mark.asyncio
async def test_anthropic_provider_uses_aegis_transport_when_aegis_supplied(
    aegis_with_anthropic_grant, respx_mock,
):
    """When aegis is supplied and the domain is granted, infer() succeeds via AegisTransport."""
    respx_mock.post("https://api.anthropic.com/v1/messages").mock(
        return_value=httpx.Response(
            200,
            json=_anthropic_messages_response("Hello from aegis-routed Anthropic!"),
        )
    )
    provider = AnthropicProvider(
        api_key="test-key",
        model="claude-sonnet-4-20250514",
        aegis=aegis_with_anthropic_grant,
    )
    async with as_agent("ant-agent"):
        result = await provider.infer(
            [{"role": "user", "content": "hi"}], max_tokens=5,
        )
    assert "Hello from aegis-routed Anthropic!" in result


@pytest.mark.asyncio
async def test_anthropic_provider_denies_when_domain_undeclared(
    aegis_no_anthropic_grant,
):
    """When the agent has not declared api.anthropic.com, AegisTransport raises PermissionDenied."""
    provider = AnthropicProvider(
        api_key="test-key",
        model="claude-sonnet-4-20250514",
        aegis=aegis_no_anthropic_grant,
    )
    # Spy on aegis.network to confirm PermissionDenied is the cause of the failure.
    original_network = aegis_no_anthropic_grant.network
    network_raised = []

    async def spy_network(*args, **kwargs):
        try:
            return await original_network(*args, **kwargs)
        except PermissionDenied as exc:
            network_raised.append(exc)
            raise

    with patch.object(aegis_no_anthropic_grant, "network", side_effect=spy_network):
        async with as_agent("ant-agent"):
            result = await provider.infer(
                [{"role": "user", "content": "hi"}], max_tokens=5,
            )
    # PermissionDenied was raised inside AegisTransport, confirmed by spy.
    assert len(network_raised) >= 1, "Expected PermissionDenied from aegis.network()"
    # infer() catches all exceptions and returns an error string.
    assert "[Inference error:" in result
