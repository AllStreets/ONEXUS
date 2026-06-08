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

        from nexus.context import as_agent
        async with as_agent(self.slug):
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

    # ── gating ───────────────────────────────────────────────────────────────

    async def _gate(self, tool_name: str, args: dict[str, Any]) -> None:
        from nexus.agents._gating import gate_tool_call
        await gate_tool_call(
            self.slug, self._manifest, tool_name, args, self._aegis, self._inbox,
            defer_on_no_workspace=True,
        )
