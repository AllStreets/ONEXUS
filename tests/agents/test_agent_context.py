"""Tests that agent adapters set the current_agent contextvar during dispatch."""
from __future__ import annotations

import pytest

from nexus.agents.in_process_agent import InProcessAgent
from nexus.agents.manifest import Manifest
from nexus.context import current_agent_slug
from nexus.kernel.aegis import Aegis
from nexus.modules.base import NexusModule


class _Probe(NexusModule):
    name = "probe"
    description = "records the current_agent during dispatch"
    version = "0.1.0"

    @classmethod
    def manifest(cls):
        return Manifest.model_validate({
            "manifest_version": 1, "slug": "probe", "name": "probe",
            "version": "0.1.0", "system": True,
            "publisher": {"type": "org", "handle": "t"}, "category": "test",
            "identity": {"mark": {"kind": "builtin:probe", "gradient": ["#fff", "#000"]}},
            "intents": [],
            "capabilities": {"tools": [{"name": "handle", "class": "Routine"}],
                             "declared": {"Routine": [], "Notable": [], "Sensitive": [], "Privileged": []}},
            "runtime": {"transport": "in_process"},
        })

    async def handle(self, message, context):
        return current_agent_slug() or "<none>"


@pytest.fixture
def aegis(tmp_path):
    a = Aegis(str(tmp_path / "a.db"))
    a.init_db()
    a.register_manifest(_Probe.manifest())
    return a


@pytest.mark.asyncio
async def test_in_process_call_sets_agent_context(aegis):
    """The module sees current_agent_slug() == its slug during dispatch."""
    agent = InProcessAgent(_Probe(), aegis=aegis)
    result = await agent.call_tool("handle", {"message": "x", "context": {}})
    assert result == "probe"


@pytest.mark.asyncio
async def test_in_process_call_restores_context_after(aegis):
    """After the call returns, current_agent_slug() is back to None."""
    agent = InProcessAgent(_Probe(), aegis=aegis)
    await agent.call_tool("handle", {"message": "x", "context": {}})
    assert current_agent_slug() is None
