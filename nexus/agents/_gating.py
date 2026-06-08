"""Shared capability-check gating used by both InProcessAgent and MCPAgent."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from nexus.kernel.aegis import Aegis, PermissionInbox
    from nexus.agents.manifest import Manifest


async def gate_tool_call(
    agent_slug: str,
    manifest: "Manifest",
    tool_name: str,
    args: dict[str, Any],
    aegis: "Aegis | None",
    inbox: "PermissionInbox | None",
    *,
    defer_on_no_workspace: bool = False,
) -> None:
    """Check ``aegis.check_capability`` for this tool call; surface PROMPT to inbox.

    Returns None on ALLOW; raises PermissionDenied on DENY or user-denial.

    ``defer_on_no_workspace``: when True (InProcessAgent), a PROMPT verdict with no
    workspace_id in args silently passes through so the module itself can perform
    its own deeper aegis gating.  When False (MCPAgent), no workspace_id + no inbox
    raises PermissionDenied immediately.
    """
    if aegis is None:
        return  # no gating when aegis isn't attached

    from nexus.kernel.aegis import (
        PermissionDecision,
        PermissionDenied,
        PermissionRequest,
        Verdict,
    )

    tool = manifest.tool(tool_name)
    if tool is None or tool.scope is None:
        return  # Routine tool with no declared scope — silent allow

    workspace_id = args.get("workspace_id")
    decision = aegis.check_capability(agent_slug, tool.scope, workspace_id=workspace_id)

    if decision.verdict is Verdict.ALLOW:
        return
    if decision.verdict is Verdict.DENY:
        raise PermissionDenied(agent_slug, f"{tool_name}:{tool.scope}")

    # Verdict.PROMPT — if workspace_id was not in args and caller asked us to defer,
    # the module may perform its own internal aegis.fs() gating with a concrete
    # workspace_id. In that case, allow the call through so the module can gate itself.
    if workspace_id is None and defer_on_no_workspace:
        return

    # Verdict.PROMPT — surface to inbox if attached, else deny
    if inbox is None:
        raise PermissionDenied(agent_slug, f"{tool_name}:{tool.scope}:no_inbox")

    request = PermissionRequest(
        agent_slug=agent_slug,
        capability=tool.scope,
        permission_class=tool.permission_class.value,
        workspace_id=workspace_id,
        preview=str(args.get("message", args))[:200],
    )
    user_decision = await inbox.ask(request)
    if user_decision is PermissionDecision.DENY:
        raise PermissionDenied(agent_slug, f"{tool.scope}:user_denied")
    if user_decision is PermissionDecision.ALLOW_ALWAYS_IN_WORKSPACE:
        aegis.grant(agent_slug, tool.scope, workspace_id=workspace_id)
    elif user_decision is PermissionDecision.ALLOW_ALWAYS_EVERYWHERE:
        aegis.grant(agent_slug, tool.scope)  # global
    # ALLOW_ONCE: do nothing extra; proceed
