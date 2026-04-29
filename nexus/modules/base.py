"""
Base class for all Nexus modules.
Every module must declare name, description, version, and implement handle().
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


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
        # Skip intermediate base classes that define their own abstract-like
        # methods (e.g. AgentModule) -- they raise NotImplementedError in a
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
        ...

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
