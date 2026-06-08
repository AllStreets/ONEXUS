"""
Base class for all Nexus modules.

A NexusModule is the in-process implementation of a built-in agent.
It exposes:
  - identity (name, description, version)
  - a Manifest (so it can be unified with catalog agents)
  - one or more tools (callable surfaces; default = the single `handle` tool)
  - lifecycle hooks (on_load / on_unload)
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from nexus.agents.manifest import Manifest


class NexusModule(ABC):
    name: str
    description: str
    version: str
    requires_network: bool = False

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Skip check for abstract subclasses and intermediate base classes
        if getattr(cls, "__abstractmethods__", None):
            return
        # Skip intermediate base classes that raise NotImplementedError in a
        # method that concrete subclasses must override.
        for method_name in ("analyze", "handle"):
            method = getattr(cls, method_name, None)
            if method is not None:
                import inspect
                try:
                    src = inspect.getsource(method)
                    if "raise NotImplementedError" in src and "must implement" in src:
                        return
                except (OSError, TypeError):
                    pass
        for attr in ("name", "description", "version"):
            if not hasattr(cls, attr) or not getattr(cls, attr):
                raise TypeError(f"Module {cls.__name__} must define '{attr}'")

    @abstractmethod
    async def handle(self, message: str, context: dict[str, Any]) -> str:
        """Process a user message and return a response string."""

    # ── unified-agent surface ────────────────────────────────────────────

    @classmethod
    def manifest(cls) -> "Manifest":
        """Return the agent manifest for this module.

        Concrete modules MUST override this. During Phase 2 (migration)
        each of the 9 built-ins ships its own override. Until then,
        this raises so subclasses can't accidentally forget.
        """
        raise NotImplementedError(
            f"{cls.__name__} must implement manifest() — see Phase 2 migration."
        )

    def tools(self) -> list[dict[str, Any]]:
        """Return MCP-shaped tool descriptors for the runtime to expose.

        Default: a single `handle` tool of class Routine. Modules with
        multiple distinct tool surfaces override this.
        """
        return [{
            "name": "handle",
            "class": "Routine",
            "description": getattr(self, "description", ""),
        }]

    # ── legacy chronicle helper (preserved) ──────────────────────────────

    def _log_outbound(self, context: dict[str, Any], destination: str, summary: str) -> None:
        """Log an outbound data event to Chronicle. Required for network modules."""
        chronicle = context.get("chronicle")
        if chronicle:
            chronicle.log(self.name, "outbound_data", {
                "destination": destination,
                "summary": summary[:500],
            })

    async def on_load(self, context: dict[str, Any] | None = None) -> None:
        """Called when the module is loaded into the kernel."""
        pass

    async def on_unload(self, context: dict[str, Any] | None = None) -> None:
        """Called when the module is unloaded from the kernel."""
        pass

    def __repr__(self) -> str:
        return f"<Module:{self.name} v{self.version}>"
