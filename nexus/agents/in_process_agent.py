"""
InProcessAgent — adapter that wraps a NexusModule and gates every
tool call through Aegis.check_capability() before invocation.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from nexus.modules.base import NexusModule

if TYPE_CHECKING:
    from nexus.kernel.aegis import Aegis, PermissionInbox


class InProcessAgent:
    def __init__(
        self,
        module: NexusModule,
        *,
        aegis: "Aegis | None" = None,
        inbox: "PermissionInbox | None" = None,
    ):
        self._module = module
        self._aegis = aegis
        self._inbox = inbox
        self._paused = False
        self._manifest = type(module).manifest()
        # Build name → ToolDescriptor map from the manifest (authoritative for scope/class)
        self._tools_by_name = {t.name: t for t in self._manifest.capabilities.tools}

    @property
    def slug(self) -> str:
        return self._manifest.slug

    @property
    def is_paused(self) -> bool:
        return self._paused

    def pause(self) -> None:
        self._paused = True

    def wake(self) -> None:
        self._paused = False

    async def call_tool(self, tool_name: str, args: dict[str, Any]) -> Any:
        if self._paused:
            raise RuntimeError(
                f"agent {self.slug!r} is paused; switch to its workspace to wake it"
            )

        if tool_name not in self._tools_by_name:
            raise KeyError(
                f"agent {self.slug!r} has no tool {tool_name!r}; "
                f"declared: {list(self._tools_by_name)}"
            )

        # Gate through Aegis if attached
        if self._aegis is not None:
            await self._gate(tool_name, args)

        # Dispatch
        if tool_name == "handle":
            message = args.get("message", "")
            context = args.get("context", {})
            return await self._module.handle(message, context)

        # Future: dispatch to other declared tools by method name.
        method = getattr(self._module, tool_name, None)
        if method is None:
            raise AttributeError(
                f"agent {self.slug!r} declares tool {tool_name!r} but the "
                f"module has no method by that name"
            )
        # Strip workspace_id from kwargs before forwarding to the module method
        method_args = {k: v for k, v in args.items() if k != "workspace_id"}
        return await method(**method_args)

    # ── gating ───────────────────────────────────────────────────────────

    async def _gate(self, tool_name: str, args: dict[str, Any]) -> None:
        from nexus.kernel.aegis import (
            PermissionDenied,
            PermissionRequest,
            PermissionDecision,
            Verdict,
        )

        tool = self._tools_by_name[tool_name]
        scope = tool.scope if hasattr(tool, "scope") else tool.get("scope")
        if scope is None:
            return  # Routine tool with no declared scope — silent allow

        workspace_id = args.get("workspace_id")
        decision = self._aegis.check_capability(
            self.slug, scope, workspace_id=workspace_id,
        )

        if decision.verdict is Verdict.ALLOW:
            return
        if decision.verdict is Verdict.DENY:
            raise PermissionDenied(self.slug, f"{tool_name}:{scope}")

        # Verdict.PROMPT — if workspace_id was not in args, the module may perform
        # its own internal aegis.fs() gating with a concrete workspace_id. In that
        # case, allow the call through so the module can gate itself.
        if workspace_id is None:
            return

        # Verdict.PROMPT — surface to inbox if attached, else deny
        if self._inbox is None:
            raise PermissionDenied(self.slug, f"{tool_name}:{scope}:no_inbox")

        request = PermissionRequest(
            agent_slug=self.slug,
            capability=scope,
            permission_class=decision.permission_class.value if decision.permission_class else "Notable",
            workspace_id=workspace_id,
            preview=str(args.get("message", ""))[:200],
        )
        user_decision = await self._inbox.ask(request)
        await self._apply_decision(user_decision, scope, workspace_id)

    async def _apply_decision(self, decision, capability, workspace_id) -> None:
        from nexus.kernel.aegis import PermissionDecision, PermissionDenied
        if decision is PermissionDecision.DENY:
            raise PermissionDenied(self.slug, f"{capability}:user_denied")
        if decision is PermissionDecision.ALLOW_ONCE:
            return
        if decision is PermissionDecision.ALLOW_ALWAYS_IN_WORKSPACE:
            self._aegis.grant(self.slug, capability, workspace_id=workspace_id)
            return
        if decision is PermissionDecision.ALLOW_ALWAYS_EVERYWHERE:
            self._aegis.grant(self.slug, capability)  # workspace_id=None → global
            return
        raise RuntimeError(f"unhandled decision: {decision!r}")
