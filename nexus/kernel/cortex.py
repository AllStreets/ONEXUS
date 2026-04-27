"""
Cortex — the Nexus router and orchestrator.
Receives user input, selects the appropriate module, enforces permissions,
logs to Chronicle, and stores interactions in Engram.
"""
from typing import Any
from nexus.kernel.engram import Engram
from nexus.kernel.chronicle import Chronicle
from nexus.kernel.aegis import Aegis, PermissionDenied
from nexus.kernel.pulse import Pulse, Message
from nexus.modules.base import NexusModule
from nexus.config import NexusConfig


class Cortex:
    def __init__(
        self,
        engram: Engram,
        chronicle: Chronicle,
        aegis: Aegis,
        pulse: Pulse,
        config: NexusConfig,
    ):
        self._engram = engram
        self._chronicle = chronicle
        self._aegis = aegis
        self._pulse = pulse
        self._config = config
        self._modules: dict[str, NexusModule] = {}
        self._llm = None

    def set_llm(self, llm_fn) -> None:
        """Set the LLM inference function used by modules."""
        self._llm = llm_fn

    def register_module(self, module: NexusModule) -> None:
        self._modules[module.name] = module

    def unregister_module(self, name: str) -> None:
        self._modules.pop(name, None)

    def list_modules(self) -> list[str]:
        return list(self._modules.keys())

    def _select_module(self, message: str) -> str:
        """
        Select which module should handle this message.
        Batch 1: always routes to 'general'.
        Batch 2+ upgrades to LLM-based intent classification.
        """
        if "general" in self._modules:
            return "general"
        if self._modules:
            return next(iter(self._modules))
        return ""

    async def process(self, message: str) -> str:
        """Route a user message to the appropriate module and return the response."""
        target = self._select_module(message)

        if not target:
            return "[Nexus] No modules loaded."

        # Check permissions
        try:
            self._aegis.check(target, "handle")
        except PermissionDenied:
            self._chronicle.log("cortex", "permission_denied", {
                "module": target, "message_preview": message[:100],
            })
            return f"[Nexus] Module '{target}' is not allowed to respond. Enable it with: nexus allow {target}"

        # Log the routing decision
        self._chronicle.log("cortex", "route", {
            "target": target, "message_preview": message[:100],
        })

        # Store the user message in episodic memory
        self._engram.episodic.store(f"User: {message}", source="user_input")

        # Build context for the module
        context: dict[str, Any] = {
            "llm": self._llm,
            "engram": self._engram,
            "chronicle": self._chronicle,
            "pulse": self._pulse,
        }

        # Execute
        module = self._modules[target]
        response = await module.handle(message, context)

        # Store the response in episodic memory
        self._engram.episodic.store(f"Nexus ({target}): {response}", source=f"module.{target}")

        # Log completion
        self._chronicle.log("cortex", "response", {
            "module": target, "response_preview": response[:200],
        })

        # Publish to Pulse for any listening modules
        await self._pulse.publish(Message(
            topic="cortex.response",
            source="cortex",
            payload={"module": target, "message": message, "response": response},
        ))

        return response
