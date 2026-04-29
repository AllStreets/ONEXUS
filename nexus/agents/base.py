"""
AgentModule -- base class for NEXUS agents with graduated sovereignty.

Agents are specialized NexusModules that start as passive skills and earn
autonomy through demonstrated reliability. Trust is tracked by Aegis and
can be revoked at any time.

Trust Tiers:
    SKILL (0-24)       User invokes explicitly. No initiative.
    ADVISOR (25-49)    Suggests actions when relevant context detected.
    MONITOR (50-74)    Proactively watches events and reports findings.
    AUTONOMOUS (75-99) Acts within defined boundaries without asking.
    SOVEREIGN (100)    Coordinates with other agents independently.

Every agent implements four methods:
    analyze()     -- Core logic. Runs at every trust level.
    suggest()     -- Proactive suggestions. ADVISOR and above.
    monitor()     -- Background event monitoring. MONITOR and above.
    coordinate()  -- Cross-agent routing. SOVEREIGN only.
"""
from __future__ import annotations

from typing import Any

from nexus.modules.base import NexusModule


class TrustTier:
    """Trust level thresholds for graduated sovereignty."""
    SKILL = 0
    ADVISOR = 25
    MONITOR = 50
    AUTONOMOUS = 75
    SOVEREIGN = 100

    @staticmethod
    def label(level: int) -> str:
        if level >= TrustTier.SOVEREIGN:
            return "sovereign"
        if level >= TrustTier.AUTONOMOUS:
            return "autonomous"
        if level >= TrustTier.MONITOR:
            return "monitor"
        if level >= TrustTier.ADVISOR:
            return "advisor"
        return "skill"


class AgentModule(NexusModule):
    """Base class for all NEXUS agents.

    Subclasses must implement ``analyze()``. The other tier methods
    (``suggest``, ``monitor``, ``coordinate``) default to no-ops and
    should be overridden when the agent has meaningful behavior at
    those trust levels.

    Class attributes set by each agent:

    * ``watch_events``  -- Pulse topics to subscribe to at MONITOR+.
    * ``coordination_targets`` -- Agent names to coordinate with at SOVEREIGN.
    """

    watch_events: list[str] = []
    coordination_targets: list[str] = []

    # ------------------------------------------------------------------
    # Trust helpers
    # ------------------------------------------------------------------

    async def get_trust_level(self, context: dict[str, Any]) -> int:
        """Return the current Aegis trust score for this agent (0-100)."""
        aegis = context.get("aegis")
        if aegis and hasattr(aegis, "get_trust"):
            try:
                return await aegis.get_trust(self.name)
            except Exception:
                return 0
        return 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def on_load(self, context: dict[str, Any] | None = None) -> None:
        """Subscribe to watch events when trust is high enough."""
        if context is None:
            return
        trust = await self.get_trust_level(context)
        if trust >= TrustTier.MONITOR and self.watch_events:
            pulse = context.get("pulse")
            if pulse:
                for event in self.watch_events:
                    await pulse.subscribe(event, self._on_watch_event)

    async def on_unload(self, context: dict[str, Any] | None = None) -> None:
        """Unsubscribe from watch events."""
        if context is None:
            return
        pulse = context.get("pulse")
        if pulse and self.watch_events:
            for event in self.watch_events:
                try:
                    await pulse.unsubscribe(event, self._on_watch_event)
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Main dispatch -- routes through trust tiers
    # ------------------------------------------------------------------

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        """Route through graduated sovereignty tiers."""
        trust = await self.get_trust_level(context)
        tier = TrustTier.label(trust)

        # Core analysis -- always runs
        result = await self.analyze(message, context)

        # ADVISOR+: append proactive suggestions
        if trust >= TrustTier.ADVISOR:
            suggestion = await self.suggest(message, context)
            if suggestion:
                result += f"\n\n[{self.name}:advisor] {suggestion}"

        # AUTONOMOUS+: record that we acted with autonomy
        if trust >= TrustTier.AUTONOMOUS:
            chronicle = context.get("chronicle")
            if chronicle:
                chronicle.log(self.name, "autonomous_action", {
                    "tier": tier, "trust": trust,
                    "message_preview": message[:100],
                })

        # SOVEREIGN: coordinate with other agents
        if trust >= TrustTier.SOVEREIGN and self.coordination_targets:
            coordination = await self.coordinate(result, context)
            if coordination:
                result += f"\n\n[{self.name}:coordinated]\n{coordination}"

        return result

    # ------------------------------------------------------------------
    # Tier methods -- subclasses override these
    # ------------------------------------------------------------------

    async def analyze(self, message: str, context: dict[str, Any]) -> str:
        """Core analysis logic. Runs at every trust level.

        This is the equivalent of the old ``handle()`` -- the primary
        functionality of the agent.
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement analyze()")

    async def suggest(self, message: str, context: dict[str, Any]) -> str:
        """Proactive suggestions at ADVISOR+ trust.

        Return a suggestion string, or empty string for no suggestion.
        Called after analyze() completes.
        """
        return ""

    async def monitor(self, event: dict[str, Any], context: dict[str, Any]) -> str | None:
        """Background event monitoring at MONITOR+ trust.

        Called when a subscribed Pulse event fires. Return a finding
        string to publish via Pulse, or None to stay silent.
        """
        return None

    async def coordinate(self, analysis_result: str, context: dict[str, Any]) -> str:
        """Cross-agent coordination at SOVEREIGN trust.

        Receives the result of analyze() and can route to other agents
        via Cortex for combined analysis. Return the coordination result
        or empty string.
        """
        return ""

    # ------------------------------------------------------------------
    # Internal event handler
    # ------------------------------------------------------------------

    async def _on_watch_event(self, event: dict[str, Any]) -> None:
        """Pulse callback for monitored events."""
        context = event.get("context", {})
        if not context:
            return
        trust = await self.get_trust_level(context)
        if trust < TrustTier.MONITOR:
            return
        finding = await self.monitor(event, context)
        if finding:
            pulse = context.get("pulse")
            if pulse:
                from nexus.kernel.pulse import Message
                await pulse.publish(Message(
                    topic=f"{self.name}.finding",
                    source=self.name,
                    payload={
                        "finding": finding,
                        "tier": TrustTier.label(trust),
                        "trust": trust,
                    },
                ))
