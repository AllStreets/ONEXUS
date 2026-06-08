"""Tests for PermissionRequest + PermissionInbox."""
from __future__ import annotations

import asyncio
import pytest

from nexus.kernel.aegis import (
    PermissionRequest,
    PermissionDecision,
    PermissionInbox,
    PermissionScope,
)


def test_permission_request_is_frozen():
    req = PermissionRequest(
        agent_slug="aider",
        capability="fs.write.workspace",
        permission_class="Notable",
        workspace_id="ws-1",
        preview="diff …",
    )
    with pytest.raises(Exception):
        req.agent_slug = "evil"


@pytest.mark.asyncio
async def test_inbox_round_trip():
    inbox = PermissionInbox()

    async def actor():
        req = PermissionRequest(
            agent_slug="aider", capability="fs.write.workspace",
            permission_class="Notable", workspace_id="ws-1", preview="diff",
        )
        return await inbox.ask(req)

    actor_task = asyncio.create_task(actor())
    await asyncio.sleep(0)

    pending = inbox.pending()
    assert len(pending) == 1
    ticket_id = pending[0].id

    inbox.answer(ticket_id, PermissionDecision.ALLOW_ONCE)
    result = await actor_task
    assert result is PermissionDecision.ALLOW_ONCE


@pytest.mark.asyncio
async def test_inbox_deny_decision_propagates():
    inbox = PermissionInbox()

    async def actor():
        req = PermissionRequest(
            agent_slug="aider", capability="fs.write.workspace",
            permission_class="Notable", workspace_id="ws-1", preview="…",
        )
        return await inbox.ask(req)

    task = asyncio.create_task(actor())
    await asyncio.sleep(0)
    ticket = inbox.pending()[0]
    inbox.answer(ticket.id, PermissionDecision.DENY)
    assert await task is PermissionDecision.DENY


@pytest.mark.asyncio
async def test_inbox_pending_excludes_answered():
    inbox = PermissionInbox()
    req = PermissionRequest(
        agent_slug="a", capability="x", permission_class="Notable",
        workspace_id=None, preview="",
    )
    task = asyncio.create_task(inbox.ask(req))
    await asyncio.sleep(0)
    assert len(inbox.pending()) == 1
    ticket_id = inbox.pending()[0].id
    inbox.answer(ticket_id, PermissionDecision.ALLOW_ONCE)
    await task
    assert inbox.pending() == []


@pytest.mark.asyncio
async def test_inbox_unknown_ticket_raises():
    inbox = PermissionInbox()
    with pytest.raises(KeyError):
        inbox.answer("nonexistent-id", PermissionDecision.ALLOW_ONCE)


def test_permission_scope_values():
    assert PermissionScope.ONCE.value == "once"
    assert PermissionScope.ALWAYS_IN_WORKSPACE.value == "always_in_workspace"
    assert PermissionScope.ALWAYS_EVERYWHERE.value == "always_everywhere"
    assert PermissionScope.NEVER.value == "never"
