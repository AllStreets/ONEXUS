"""End-to-end smoke for the Phase 4 safety UX backend."""
from __future__ import annotations

import asyncio

import pytest

from nexus.agents.installer import (
    plan_from_manifest_dict, install_from_plan, load_installed_manifest,
)
from nexus.agents.in_process_agent import InProcessAgent
from nexus.agents.manifest import Manifest
from nexus.kernel.aegis import (
    Aegis, PermissionInbox, PermissionDecision, PermissionDenied,
)
from nexus.modules.base import NexusModule


def _writer_manifest_dict() -> dict:
    return {
        "manifest_version": 1, "slug": "writer", "name": "writer",
        "version": "0.1.0", "system": False,
        "publisher": {"type": "org", "handle": "test"}, "category": "test",
        "identity": {"mark": {"kind": "svg", "gradient": ["#fff", "#000"]}},
        "intents": [],
        "capabilities": {
            "tools": [{"name": "handle", "class": "Notable",
                       "scope": "fs.write.workspace"}],
            "declared": {"Routine": [], "Notable": ["fs.write.workspace"],
                         "Sensitive": [], "Privileged": []},
        },
        "runtime": {"transport": "stdio", "command": "x"},
    }


class _StubWriter(NexusModule):
    name = "writer"
    description = "writes"
    version = "0.1.0"

    @classmethod
    def manifest(cls):
        return Manifest.model_validate(_writer_manifest_dict())

    async def handle(self, message, context):
        return f"wrote: {message}"


@pytest.mark.asyncio
async def test_full_install_prompt_grant_call_cycle(tmp_path):
    # 1. Validate manifest → install plan
    plan = plan_from_manifest_dict(_writer_manifest_dict())
    assert plan.slug == "writer"
    assert any("fs.write.workspace" in g.capabilities for g in plan.groups)

    # 2. Persist + register
    aegis = Aegis(str(tmp_path / "aegis.db"))
    aegis.init_db()
    install_from_plan(plan, tmp_path, aegis=aegis)
    assert (tmp_path / "agents" / "writer" / "manifest.json").exists()
    assert load_installed_manifest("writer", tmp_path) is not None

    # 3. Build a gated InProcessAgent
    inbox = PermissionInbox()
    agent = InProcessAgent(_StubWriter(), aegis=aegis, inbox=inbox)

    # 4. First tool call → suspended in inbox
    async def caller():
        return await agent.call_tool(
            "handle", {"message": "hello", "context": {}, "workspace_id": "ws-1"},
        )

    task = asyncio.create_task(caller())
    await asyncio.sleep(0.05)
    pending = inbox.pending()
    assert len(pending) == 1
    ticket = pending[0]
    assert ticket.request.agent_slug == "writer"
    assert ticket.request.capability == "fs.write.workspace"
    assert ticket.request.permission_class == "Notable"

    # 5. User grants always-in-workspace
    inbox.answer(ticket.id, PermissionDecision.ALLOW_ALWAYS_IN_WORKSPACE)
    result = await task
    assert result == "wrote: hello"

    # 6. Second call same workspace: silent (grant persisted)
    result2 = await agent.call_tool(
        "handle", {"message": "again", "context": {}, "workspace_id": "ws-1"},
    )
    assert result2 == "wrote: again"
    assert inbox.pending() == []

    # 7. Different workspace: still prompts
    async def caller2():
        return await agent.call_tool(
            "handle", {"message": "elsewhere", "context": {}, "workspace_id": "ws-2"},
        )
    task2 = asyncio.create_task(caller2())
    await asyncio.sleep(0.05)
    assert len(inbox.pending()) == 1
    inbox.answer(inbox.pending()[0].id, PermissionDecision.DENY)
    with pytest.raises(PermissionDenied):
        await task2
