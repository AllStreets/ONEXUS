# nexus/modules/herald.py
"""Herald — agent-to-agent negotiation (N3.1).

Proposals, counters, and commitments are typed Pulse messages. Each commit
is gated by aegis.check_capability() against the INITIATOR's manifest, and
the full transcript is recorded in Chronicle.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from nexus.modules.base import NexusModule
from nexus.society.herald import Forge, NegotiationState, NegotiationStatus


def herald_autoaccept_enabled(config) -> bool:
    """Kill switch for Herald's only automated behavior: auto-accepting a
    counter that strictly dominates the prior offer.

    Default OFF (spec deviation 3). Enabled only by env
    NEXUS_HERALD_AUTOACCEPT in (1/true/yes) AND no
    <data_dir>/herald-autoaccept.kill file. Mirrors the Dreamweaver
    convention so the kill switch is observable and uniform.
    """
    if os.environ.get("NEXUS_HERALD_AUTOACCEPT", "0").lower() not in ("1", "true", "yes"):
        return False
    return not (Path(config.data_dir) / "herald-autoaccept.kill").exists()


class HeraldModule(NexusModule):
    name = "herald"
    description = (
        "Agent-to-agent negotiation -- offer/counter/accept/reject/commit as "
        "typed Pulse messages; each commit is Aegis-gated by capability class "
        "and the full transcript is recorded in Chronicle"
    )
    version = "1.0.0"

    @classmethod
    def manifest(cls):
        from nexus.agents.manifest import Manifest
        return Manifest.model_validate({
            "manifest_version": 1, "slug": "herald", "name": "herald",
            "tagline": "Structured negotiation between agents inside Aegis boundaries.",
            "version": cls.version, "system": True,
            "publisher": {"type": "org", "handle": "nexus"},
            "category": "coordination", "license": "Apache-2.0",
            "identity": {"mark": {"kind": "builtin:herald",
                                  "gradient": ["#ffd9a8", "#9c6a2a"]}},
            "intents": [{
                "name": "NEGOTIATE",
                "patterns": [r"\bherald\b", r"\bnegotiat\w*\b", r"\bpropos\w*\b",
                             r"\bcounter-?offer\b", r"\bcommit\s+to\b", r"\bagreement\b"],
                "semantic_signals": ["negotiate", "propose", "counter-offer",
                                     "reach agreement", "commit to terms",
                                     "agent negotiation"],
                "weight": 1.0,
            }],
            "capabilities": {
                "tools": [{"name": "handle", "class": "Routine"}],
                "declared": {"Routine": ["chronicle.read.workspace", "pulse.subscribe"],
                             "Notable": [], "Sensitive": [], "Privileged": []},
            },
            "runtime": {"transport": "in_process"},
            "trust": {"floor": 0.30, "default_tier": "ADVISOR"},
        })

    def __init__(self):
        self._negotiations: dict[str, NegotiationState] = {}

    async def _emit(self, ctx, topic: str, payload: dict[str, Any]) -> None:
        pulse = ctx.get("pulse")
        if pulse is None:
            return
        from nexus.kernel.pulse import Message
        await pulse.publish(Message(topic=topic, source="herald", payload=payload))

    def _log(self, ctx, action: str, payload: dict[str, Any]) -> None:
        ch = ctx.get("chronicle")
        if ch is not None:
            ch.log("herald", action, payload)

    async def open_negotiation(self, ctx, *, initiator, responder, capability,
                               workspace_id, terms, value) -> dict[str, Any]:
        offer = Forge.offer(initiator=initiator, responder=responder,
                            capability=capability, workspace_id=workspace_id,
                            terms=terms, value=value)
        neg = NegotiationState.start(offer)
        self._negotiations[neg.negotiation_id] = neg
        await self._emit(ctx, "herald.offer", {"negotiation_id": neg.negotiation_id, **offer})
        self._log(ctx, "negotiation_event", {"negotiation_id": neg.negotiation_id,
                                             "kind": "offer", "capability": capability})
        return neg.to_dict()

    async def counter(self, ctx, negotiation_id, *, by, terms, value) -> dict[str, Any]:
        neg = self._get(negotiation_id)
        neg.counter(Forge.counter(by=by, terms=terms, value=value))
        await self._emit(ctx, "herald.counter", {"negotiation_id": negotiation_id,
                                                 "by": by, "terms": terms, "value": value})
        self._log(ctx, "negotiation_event", {"negotiation_id": negotiation_id, "kind": "counter"})
        return neg.to_dict()

    async def respond(self, ctx, negotiation_id, *, action, by, reason="") -> dict[str, Any]:
        neg = self._get(negotiation_id)
        if action == "accept":
            neg.accept(by=by)
            await self._emit(ctx, "herald.accept", {"negotiation_id": negotiation_id, "by": by})
        elif action == "reject":
            neg.reject(by=by, reason=reason)
            await self._emit(ctx, "herald.reject", {"negotiation_id": negotiation_id,
                                                    "by": by, "reason": reason})
            self._log(ctx, "transcript", {"negotiation_id": negotiation_id,
                                         "status": neg.status.value, "transcript": neg.transcript})
        else:
            raise ValueError(f"unknown action {action!r}")
        self._log(ctx, "negotiation_event", {"negotiation_id": negotiation_id, "kind": action})
        return neg.to_dict()

    async def commit(self, ctx, negotiation_id, *, by) -> dict[str, Any]:
        neg = self._get(negotiation_id)
        aegis = ctx.get("aegis")
        verdict, reason = "ALLOW", "no aegis in context"
        if aegis is not None:
            decision = aegis.check_capability(neg.initiator, neg.capability, neg.workspace_id)
            verdict, reason = decision.verdict.value, decision.reason
        if verdict != "ALLOW":
            self._log(ctx, "commit_denied", {"negotiation_id": negotiation_id,
                                            "capability": neg.capability, "reason": reason})
            return {"committed": False, "verdict": verdict, "reason": reason,
                    "negotiation_id": negotiation_id}
        token = neg.commit(by=by)
        await self._emit(ctx, "herald.commit", {"negotiation_id": negotiation_id,
                                                "capability": token.capability,
                                                "workspace_id": token.workspace_id})
        self._log(ctx, "negotiation_event", {"negotiation_id": negotiation_id, "kind": "commit"})
        self._log(ctx, "transcript", {"negotiation_id": negotiation_id,
                                     "status": neg.status.value, "transcript": neg.transcript})
        return {"committed": True, "verdict": verdict, "negotiation_id": negotiation_id,
                "capability": token.capability, "workspace_id": token.workspace_id,
                "terms": token.terms}

    async def maybe_auto_accept(self, ctx, negotiation_id, *, by) -> dict[str, Any]:
        """Policy-driven auto-accept of a strictly-dominating counter.

        This is Herald's only automated behavior. It is OFF by default and
        gated by herald_autoaccept_enabled() (env + kill file). When disabled
        it no-ops and logs the skip; manual negotiation is unaffected.
        """
        config = ctx.get("config")
        if config is None or not herald_autoaccept_enabled(config):
            self._log(ctx, "autoaccept_skipped",
                      {"negotiation_id": negotiation_id, "reason": "kill_switch"})
            return {"auto_accepted": False, "reason": "kill_switch"}
        neg = self._get(negotiation_id)
        if not neg.counter_dominates():
            return {"auto_accepted": False, "reason": "counter_not_dominating"}
        return await self.respond(ctx, negotiation_id, action="accept", by=by)

    def get(self, negotiation_id) -> dict[str, Any] | None:
        neg = self._negotiations.get(negotiation_id)
        return neg.to_dict() if neg else None

    def list_open(self) -> list[dict[str, Any]]:
        return [n.to_dict() for n in self._negotiations.values()
                if n.status not in (NegotiationStatus.REJECTED, NegotiationStatus.COMMITTED)]

    def _get(self, negotiation_id) -> NegotiationState:
        neg = self._negotiations.get(negotiation_id)
        if neg is None:
            raise KeyError(f"unknown negotiation {negotiation_id!r}")
        return neg

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        opens = self.list_open()
        if not opens:
            return ("[Herald] No open negotiations. Start one via the Herald API "
                    "(offer -> counter -> accept/reject -> commit). Every commit is "
                    "Aegis-gated and the transcript is recorded in Chronicle.")
        lines = [f"[Herald] {len(opens)} open negotiation(s):"]
        for n in opens:
            lines.append(f"  - {n['negotiation_id']} {n['initiator']}->{n['responder']} "
                         f"[{n['status']}] cap={n['capability']} value={n['current_value']}")
        return "\n".join(lines)
