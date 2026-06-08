"""Tests that InProcessAgent gates tool calls through Aegis.check_capability."""
from __future__ import annotations

import asyncio
import pytest

from nexus.agents.in_process_agent import InProcessAgent
from nexus.agents.manifest import Manifest
from nexus.kernel.aegis import (
    Aegis,
    PermissionDecision,
    PermissionInbox,
    PermissionDenied,
)
from nexus.modules.base import NexusModule


class _NotableWriter(NexusModule):
    """A module whose `handle` tool is class=Notable, scope=fs.write.workspace."""
    name = "writer"
    description = "writes files"
    version = "0.1.0"

    @classmethod
    def manifest(cls):
        return Manifest.model_validate({
            "manifest_version": 1, "slug": "writer", "name": "writer",
            "version": "0.1.0", "system": True,
            "publisher": {"type": "org", "handle": "t"}, "category": "test",
            "identity": {"mark": {"kind": "builtin:writer", "gradient": ["#fff", "#000"]}},
            "intents": [],
            "capabilities": {
                "tools": [{"name": "handle", "class": "Notable",
                           "scope": "fs.write.workspace"}],
                "declared": {"Routine": [], "Notable": ["fs.write.workspace"],
                             "Sensitive": [], "Privileged": []},
            },
            "runtime": {"transport": "in_process"},
            "trust": {"floor": 0.0, "default_tier": "OBSERVER"},
        })

    async def handle(self, message, context):
        return f"wrote: {message}"


class _RoutineHelper(NexusModule):
    """A module whose `handle` tool is class=Routine — should never prompt."""
    name = "helper"
    description = "routine"
    version = "0.1.0"

    @classmethod
    def manifest(cls):
        return Manifest.model_validate({
            "manifest_version": 1, "slug": "helper", "name": "helper",
            "version": "0.1.0", "system": True,
            "publisher": {"type": "org", "handle": "t"}, "category": "test",
            "identity": {"mark": {"kind": "builtin:helper", "gradient": ["#fff", "#000"]}},
            "intents": [],
            "capabilities": {
                "tools": [{"name": "handle", "class": "Routine"}],
                "declared": {"Routine": ["engram.read.workspace"]},
            },
            "runtime": {"transport": "in_process"},
        })

    async def handle(self, message, context):
        return f"helper: {message}"


@pytest.fixture
def aegis(tmp_path):
    a = Aegis(str(tmp_path / "a.db"))
    a.init_db()
    a.register_manifest(_NotableWriter.manifest())
    a.register_manifest(_RoutineHelper.manifest())
    return a


@pytest.mark.asyncio
async def test_routine_tool_is_allowed_silently(aegis):
    agent = InProcessAgent(_RoutineHelper(), aegis=aegis)
    result = await agent.call_tool("handle", {"message": "ping", "context": {}})
    assert result == "helper: ping"


@pytest.mark.asyncio
async def test_notable_tool_with_grant_allowed(aegis):
    agent = InProcessAgent(_NotableWriter(), aegis=aegis)
    aegis.grant("writer", "fs.write.workspace")  # global
    result = await agent.call_tool(
        "handle", {"message": "ok", "context": {}, "workspace_id": "ws-1"},
    )
    assert result == "wrote: ok"


@pytest.mark.asyncio
async def test_notable_tool_without_grant_or_inbox_denied(aegis):
    """Without a grant AND without an inbox to ask, PROMPT raises PermissionDenied."""
    agent = InProcessAgent(_NotableWriter(), aegis=aegis)
    with pytest.raises(PermissionDenied):
        await agent.call_tool("handle", {"message": "x", "context": {}, "workspace_id": "ws-1"})


@pytest.mark.asyncio
async def test_notable_tool_with_inbox_allow_proceeds(aegis):
    """With an inbox attached, PROMPT pushes a ticket; ALLOW resolves it."""
    inbox = PermissionInbox()
    agent = InProcessAgent(_NotableWriter(), aegis=aegis, inbox=inbox)

    async def caller():
        return await agent.call_tool(
            "handle", {"message": "ok", "context": {}, "workspace_id": "ws-1"},
        )

    task = asyncio.create_task(caller())
    await asyncio.sleep(0.01)  # let caller reach the suspend point
    pending = inbox.pending()
    assert len(pending) == 1
    assert pending[0].request.agent_slug == "writer"
    inbox.answer(pending[0].id, PermissionDecision.ALLOW_ONCE)
    result = await task
    assert result == "wrote: ok"


@pytest.mark.asyncio
async def test_notable_tool_with_inbox_deny_raises(aegis):
    inbox = PermissionInbox()
    agent = InProcessAgent(_NotableWriter(), aegis=aegis, inbox=inbox)

    async def caller():
        return await agent.call_tool(
            "handle", {"message": "x", "context": {}, "workspace_id": "ws-1"},
        )

    task = asyncio.create_task(caller())
    await asyncio.sleep(0.01)
    inbox.answer(inbox.pending()[0].id, PermissionDecision.DENY)
    with pytest.raises(PermissionDenied):
        await task


@pytest.mark.asyncio
async def test_allow_always_in_workspace_persists_grant(aegis):
    inbox = PermissionInbox()
    agent = InProcessAgent(_NotableWriter(), aegis=aegis, inbox=inbox)

    async def caller(workspace_id):
        return await agent.call_tool(
            "handle", {"message": "ok", "context": {}, "workspace_id": workspace_id},
        )

    task = asyncio.create_task(caller("ws-1"))
    await asyncio.sleep(0.01)
    inbox.answer(inbox.pending()[0].id, PermissionDecision.ALLOW_ALWAYS_IN_WORKSPACE)
    assert await task == "wrote: ok"

    # Second call in same workspace must not prompt
    result = await agent.call_tool("handle", {"message": "again", "context": {}, "workspace_id": "ws-1"})
    assert result == "wrote: again"
    assert inbox.pending() == []
