"""Herald — agent-to-agent negotiation state machine (pure, deterministic).

The kernel-free core: an offer/counter/accept/reject/commit machine plus
Forge, which builds and validates the typed payloads. No Pulse, no Aegis,
no I/O here — HeraldModule wires those in.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class NegotiationStatus(str, Enum):
    OPEN = "open"
    COUNTERED = "countered"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    COMMITTED = "committed"


_TERMINAL = {NegotiationStatus.REJECTED, NegotiationStatus.COMMITTED}


class IllegalTransition(Exception):
    """Raised when a negotiation action is invalid for the current state."""


@dataclass(frozen=True)
class CommitToken:
    negotiation_id: str
    capability: str
    workspace_id: str | None
    terms: dict[str, Any]
    committed_by: str


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Forge:
    """Builds and validates typed negotiation payloads."""

    @staticmethod
    def offer(*, initiator: str, responder: str, capability: str,
              workspace_id: str | None, terms: dict[str, Any],
              value: float) -> dict[str, Any]:
        if not initiator or not responder:
            raise ValueError("offer requires initiator and responder")
        if not capability:
            raise ValueError("offer requires a capability")
        if not (0.0 <= value <= 1.0):
            raise ValueError("offer value must be in [0,1]")
        return {
            "kind": "offer", "initiator": initiator, "responder": responder,
            "capability": capability, "workspace_id": workspace_id,
            "terms": dict(terms), "value": float(value), "at": _now(),
        }

    @staticmethod
    def counter(*, by: str, terms: dict[str, Any], value: float) -> dict[str, Any]:
        if not (0.0 <= value <= 1.0):
            raise ValueError("counter value must be in [0,1]")
        return {"kind": "counter", "by": by, "terms": dict(terms),
                "value": float(value), "at": _now()}


@dataclass
class NegotiationState:
    negotiation_id: str
    initiator: str
    responder: str
    capability: str
    workspace_id: str | None
    status: NegotiationStatus
    current_terms: dict[str, Any]
    current_value: float
    offer_value: float
    transcript: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def start(cls, offer: dict[str, Any]) -> "NegotiationState":
        if offer.get("kind") != "offer":
            raise ValueError("start requires an offer payload")
        neg = cls(
            negotiation_id=uuid.uuid4().hex[:12],
            initiator=offer["initiator"], responder=offer["responder"],
            capability=offer["capability"], workspace_id=offer["workspace_id"],
            status=NegotiationStatus.OPEN,
            current_terms=dict(offer["terms"]), current_value=offer["value"],
            offer_value=offer["value"],
        )
        neg.transcript.append(offer)
        return neg

    def _require(self, allowed: set[NegotiationStatus], action: str) -> None:
        if self.status in _TERMINAL:
            raise IllegalTransition(f"{action}: negotiation is terminal ({self.status.value})")
        if self.status not in allowed:
            raise IllegalTransition(f"{action}: not allowed from {self.status.value}")

    def counter(self, counter: dict[str, Any]) -> None:
        self._require({NegotiationStatus.OPEN, NegotiationStatus.COUNTERED}, "counter")
        self.current_terms = dict(counter["terms"])
        self.current_value = float(counter["value"])
        self.status = NegotiationStatus.COUNTERED
        self.transcript.append(counter)

    def accept(self, *, by: str) -> None:
        self._require({NegotiationStatus.OPEN, NegotiationStatus.COUNTERED}, "accept")
        self.status = NegotiationStatus.ACCEPTED
        self.transcript.append({"kind": "accept", "by": by, "at": _now()})

    def reject(self, *, by: str, reason: str = "") -> None:
        self._require({NegotiationStatus.OPEN, NegotiationStatus.COUNTERED}, "reject")
        self.status = NegotiationStatus.REJECTED
        self.transcript.append({"kind": "reject", "by": by, "reason": reason, "at": _now()})

    def commit(self, *, by: str) -> CommitToken:
        if self.status is not NegotiationStatus.ACCEPTED:
            raise IllegalTransition("commit: requires ACCEPTED state")
        self.status = NegotiationStatus.COMMITTED
        self.transcript.append({"kind": "commit", "by": by, "at": _now()})
        return CommitToken(
            negotiation_id=self.negotiation_id, capability=self.capability,
            workspace_id=self.workspace_id, terms=dict(self.current_terms),
            committed_by=by,
        )

    def counter_dominates(self) -> bool:
        return (self.status is NegotiationStatus.COUNTERED
                and self.current_value <= self.offer_value)

    def to_dict(self) -> dict[str, Any]:
        return {
            "negotiation_id": self.negotiation_id, "initiator": self.initiator,
            "responder": self.responder, "capability": self.capability,
            "workspace_id": self.workspace_id, "status": self.status.value,
            "current_terms": self.current_terms, "current_value": self.current_value,
            "transcript": self.transcript,
        }
