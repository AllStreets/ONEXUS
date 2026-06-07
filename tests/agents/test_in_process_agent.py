"""Tests for InProcessAgent — the adapter that makes a NexusModule speak the agent protocol."""
from __future__ import annotations

import pytest

from nexus.agents.in_process_agent import InProcessAgent
from nexus.agents.manifest import Manifest
from nexus.modules.base import NexusModule
from nexus.kernel.aegis import Aegis


class _GreeterModule(NexusModule):
    name = "greeter"
    description = "says hi"
    version = "1.0.0"

    @classmethod
    def manifest(cls) -> Manifest:
        return Manifest.model_validate({
            "manifest_version": 1,
            "slug": "greeter", "name": "greeter", "version": "1.0.0",
            "system": True,
            "publisher": {"type": "org", "handle": "nexus"},
            "category": "test",
            "identity": {"mark": {"kind": "builtin:greeter", "gradient": ["#fff", "#000"]}},
            "intents": [{"name": "greet", "patterns": ["^hi"], "weight": 1.0}],
            "capabilities": {
                "tools": [{"name": "handle", "class": "Routine"}],
                "declared": {"Routine": []},
            },
            "runtime": {"transport": "in_process"},
        })

    async def handle(self, message: str, context: dict) -> str:
        return f"hello, {message}"


@pytest.fixture
def aegis(tmp_path):
    a = Aegis(str(tmp_path / "a.db"))
    a.init_db()
    a.register_manifest(_GreeterModule.manifest())
    return a


@pytest.mark.asyncio
async def test_call_tool_dispatches_to_module(aegis):
    agent = InProcessAgent(_GreeterModule(), aegis=aegis)
    result = await agent.call_tool("handle", {"message": "world", "context": {}})
    assert result == "hello, world"


@pytest.mark.asyncio
async def test_paused_agent_refuses_calls(aegis):
    agent = InProcessAgent(_GreeterModule(), aegis=aegis)
    agent.pause()
    with pytest.raises(RuntimeError) as exc:
        await agent.call_tool("handle", {"message": "x", "context": {}})
    assert "paused" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_woken_agent_responds_again(aegis):
    agent = InProcessAgent(_GreeterModule(), aegis=aegis)
    agent.pause()
    agent.wake()
    result = await agent.call_tool("handle", {"message": "x", "context": {}})
    assert result == "hello, x"


@pytest.mark.asyncio
async def test_unknown_tool_raises(aegis):
    agent = InProcessAgent(_GreeterModule(), aegis=aegis)
    with pytest.raises(KeyError):
        await agent.call_tool("nonexistent", {})
