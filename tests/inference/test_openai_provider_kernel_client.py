"""Tests that OpenAIProvider routes through AegisTransport when aegis is supplied."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

from nexus.agents.manifest import Manifest
from nexus.context import as_agent
from nexus.inference.openai_provider import OpenAIProvider
from nexus.kernel.aegis import Aegis, PermissionDenied


def _openai_chat_response(content: str) -> dict:
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 1234567890,
        "model": "gpt-4o-mini",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }


@pytest.fixture
def aegis_with_openai_grant(tmp_path):
    a = Aegis(str(tmp_path / "a.db"))
    a.init_db()
    a.register_manifest(Manifest.model_validate({
        "manifest_version": 1, "slug": "oai-agent", "name": "oai-agent",
        "version": "1.0.0", "system": True,
        "publisher": {"type": "org", "handle": "t"}, "category": "test",
        "identity": {"mark": {"kind": "builtin:echo", "gradient": ["#fff", "#000"]}},
        "intents": [],
        "capabilities": {"tools": [], "declared": {
            "Routine": [], "Notable": ["network.outbound.api.openai.com"],
            "Sensitive": [], "Privileged": [],
        }},
        "runtime": {"transport": "in_process"},
    }))
    a.grant("oai-agent", "network.outbound.api.openai.com")
    return a


@pytest.fixture
def aegis_no_openai_grant(tmp_path):
    """Aegis with agent registered but NO grant for api.openai.com."""
    a = Aegis(str(tmp_path / "b.db"))
    a.init_db()
    a.register_manifest(Manifest.model_validate({
        "manifest_version": 1, "slug": "oai-agent", "name": "oai-agent",
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
async def test_openai_provider_uses_aegis_transport_when_aegis_supplied(
    aegis_with_openai_grant, respx_mock,
):
    """When aegis is supplied and the domain is granted, infer() succeeds via AegisTransport."""
    respx_mock.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json=_openai_chat_response("Hello from aegis-routed OpenAI!"),
        )
    )
    provider = OpenAIProvider(
        api_key="test-key", model="gpt-4o-mini", aegis=aegis_with_openai_grant,
    )
    async with as_agent("oai-agent"):
        result = await provider.infer(
            [{"role": "user", "content": "hi"}], max_tokens=5,
        )
    assert "Hello from aegis-routed OpenAI!" in result


@pytest.mark.asyncio
async def test_openai_provider_denies_when_domain_undeclared(
    aegis_no_openai_grant,
):
    """When the agent has not declared api.openai.com, AegisTransport raises PermissionDenied."""
    provider = OpenAIProvider(
        api_key="test-key", model="gpt-4o-mini", aegis=aegis_no_openai_grant,
    )
    # Spy on aegis.network to confirm PermissionDenied is the cause of the failure.
    original_network = aegis_no_openai_grant.network
    network_raised = []

    async def spy_network(*args, **kwargs):
        try:
            return await original_network(*args, **kwargs)
        except PermissionDenied as exc:
            network_raised.append(exc)
            raise

    with patch.object(aegis_no_openai_grant, "network", side_effect=spy_network):
        async with as_agent("oai-agent"):
            result = await provider.infer(
                [{"role": "user", "content": "hi"}], max_tokens=5,
            )
    # PermissionDenied was raised inside AegisTransport, confirmed by spy.
    assert len(network_raised) >= 1, "Expected PermissionDenied from aegis.network()"
    # infer() catches all exceptions and returns an error string.
    assert "[Inference error:" in result
