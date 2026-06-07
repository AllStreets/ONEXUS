"""
InProcessAgent — adapter that wraps a NexusModule and exposes the
same `call_tool()` interface as an external MCP-served agent.

Built-in modules run as InProcessAgents; the runtime treats them
identically to subprocess agents but pays no IPC cost.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from nexus.modules.base import NexusModule

if TYPE_CHECKING:
    from nexus.kernel.aegis import Aegis


class InProcessAgent:
    def __init__(self, module: NexusModule, *, aegis: "Aegis | None" = None):
        self._module = module
        self._aegis = aegis
        self._paused = False
        self._manifest = type(module).manifest()
        # Build a name → tool descriptor map
        self._tools_by_name = {t["name"]: t for t in module.tools()}

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

        # Tools map onto module methods. For now the only tool is `handle`.
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
        return await method(**args)
