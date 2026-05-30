# nexus/modules/autonomic.py
"""
Autonomic -- earned autonomous action engine.
Observes patterns, learns routines, and gradually takes autonomous action
as trust is earned through successful outcomes. Every action is auditable,
every decision is adversarially checked, and trust retreats on failure.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from enum import IntEnum
from typing import Any

from nexus.modules.base import NexusModule


class TrustTier(IntEnum):
    OBSERVER = 0    # 0-20: watch only
    SUGGESTER = 1   # 21-50: suggest
    DRAFTER = 2     # 51-75: prepare actions for approval
    ACTOR = 3       # 76-90: act + confirm
    STEWARD = 4     # 91-100: full autonomy in earned domains

    @classmethod
    def from_score(cls, score: int) -> "TrustTier":
        if score <= 20:
            return cls.OBSERVER
        if score <= 50:
            return cls.SUGGESTER
        if score <= 75:
            return cls.DRAFTER
        if score <= 90:
            return cls.ACTOR
        return cls.STEWARD


class ProposalVerdict(IntEnum):
    APPROVED = 0
    REJECTED = 1
    NEEDS_REVIEW = 2


@dataclass
class Pattern:
    id: str
    category: str
    description: str
    trigger_conditions: dict[str, Any]
    action_template: str
    confidence: float
    times_observed: int
    times_approved: int
    times_rejected: int
    last_seen: str


@dataclass
class DomainTrust:
    domain: str
    trust_score: int
    successes: int
    failures: int
    last_failure: str
    cooldown_until: str


@dataclass
class ActionProposal:
    id: str
    domain: str
    description: str
    pattern_id: str | None
    stakes: str  # "low", "medium", "high"
    reasoning: str
    verdict: ProposalVerdict = ProposalVerdict.NEEDS_REVIEW


_DEFAULT_CONFIG = {
    "trust_drop_on_failure": 20,
    "cooldown_hours": 48,
    "audit_probability": 0.10,
    "high_stakes_domains": ["financial", "communication", "legal"],
}


class AutonomicModule(NexusModule):
    name = "autonomic"
    description = "Earned autonomous action -- observes patterns, learns routines, acts within trust boundaries"
    version = "0.1.0"

    def __init__(self, config: dict[str, Any] | None = None):
        self._config = {**_DEFAULT_CONFIG, **(config or {})}
        self._patterns: dict[str, Pattern] = {}
        self._domains: dict[str, DomainTrust] = {}
        self._proposals: dict[str, ActionProposal] = {}
        self._event_log: list[dict[str, Any]] = []

    # -- Domain trust management --

    def get_domain_trust(self, domain: str) -> DomainTrust:
        if domain not in self._domains:
            self._domains[domain] = DomainTrust(
                domain=domain, trust_score=0, successes=0,
                failures=0, last_failure="", cooldown_until="",
            )
        return self._domains[domain]

    def get_tier(self, domain: str) -> TrustTier:
        dt = self.get_domain_trust(domain)
        return TrustTier.from_score(dt.trust_score)

    def record_success(self, domain: str) -> DomainTrust:
        dt = self.get_domain_trust(domain)
        now = datetime.now(timezone.utc).isoformat()
        if dt.cooldown_until and now < dt.cooldown_until:
            return dt
        dt.successes += 1
        dt.trust_score = min(100, dt.trust_score + 2)
        return dt

    def record_failure(self, domain: str) -> DomainTrust:
        dt = self.get_domain_trust(domain)
        now = datetime.now(timezone.utc).isoformat()
        drop = self._config["trust_drop_on_failure"]
        dt.failures += 1
        dt.trust_score = max(0, dt.trust_score - drop)
        dt.last_failure = now
        cooldown_end = datetime.now(timezone.utc) + timedelta(
            hours=self._config["cooldown_hours"]
        )
        dt.cooldown_until = cooldown_end.isoformat()
        return dt

    def is_in_cooldown(self, domain: str) -> bool:
        dt = self.get_domain_trust(domain)
        if not dt.cooldown_until:
            return False
        now = datetime.now(timezone.utc).isoformat()
        return now < dt.cooldown_until

    # -- Pattern management --

    def observe_event(self, category: str, description: str, conditions: dict[str, Any]) -> Pattern:
        for p in self._patterns.values():
            if p.category == category and p.trigger_conditions == conditions:
                p.times_observed += 1
                p.confidence = min(1.0, p.times_observed / 20.0)
                p.last_seen = datetime.now(timezone.utc).isoformat()
                return p

        pattern = Pattern(
            id=uuid.uuid4().hex[:12],
            category=category,
            description=description,
            trigger_conditions=conditions,
            action_template="",
            confidence=0.05,
            times_observed=1,
            times_approved=0,
            times_rejected=0,
            last_seen=datetime.now(timezone.utc).isoformat(),
        )
        self._patterns[pattern.id] = pattern
        return pattern

    def get_patterns(self, category: str | None = None) -> list[Pattern]:
        if category is None:
            return list(self._patterns.values())
        return [p for p in self._patterns.values() if p.category == category]

    def approve_pattern(self, pattern_id: str) -> Pattern | None:
        p = self._patterns.get(pattern_id)
        if p:
            p.times_approved += 1
            p.confidence = min(1.0, p.confidence + 0.05)
        return p

    def reject_pattern(self, pattern_id: str) -> Pattern | None:
        p = self._patterns.get(pattern_id)
        if p:
            p.times_rejected += 1
            p.confidence = max(0.0, p.confidence - 0.1)
        return p

    # -- Action proposals --

    def assess_stakes(self, domain: str, description: str) -> str:
        if domain in self._config["high_stakes_domains"]:
            return "high"
        desc_lower = description.lower()
        high_words = ["delete", "send", "publish", "pay", "transfer", "commit"]
        if any(w in desc_lower for w in high_words):
            return "high"
        medium_words = ["update", "modify", "change", "schedule", "move"]
        if any(w in desc_lower for w in medium_words):
            return "medium"
        return "low"

    def propose_action(
        self,
        domain: str,
        description: str,
        pattern_id: str | None = None,
        reasoning: str = "",
    ) -> ActionProposal:
        stakes = self.assess_stakes(domain, description)
        tier = self.get_tier(domain)

        if tier == TrustTier.STEWARD and stakes == "low":
            verdict = ProposalVerdict.APPROVED
        elif tier >= TrustTier.ACTOR and stakes == "low":
            verdict = ProposalVerdict.APPROVED
        elif tier >= TrustTier.DRAFTER:
            verdict = ProposalVerdict.NEEDS_REVIEW
        else:
            verdict = ProposalVerdict.REJECTED

        if stakes == "high" and verdict != ProposalVerdict.REJECTED:
            verdict = ProposalVerdict.NEEDS_REVIEW

        if self.is_in_cooldown(domain):
            verdict = ProposalVerdict.REJECTED

        proposal = ActionProposal(
            id=uuid.uuid4().hex[:12],
            domain=domain,
            description=description,
            pattern_id=pattern_id,
            stakes=stakes,
            reasoning=reasoning,
            verdict=verdict,
        )
        self._proposals[proposal.id] = proposal
        return proposal

    # -- Kill switch --

    def kill_switch(self) -> None:
        for dt in self._domains.values():
            dt.trust_score = 0
            dt.successes = 0
        self._proposals.clear()

    # -- Lifecycle --

    async def on_load(self, context: dict[str, Any]) -> None:
        self._pulse = context.get("pulse")
        if self._pulse:
            self._pulse.subscribe("cortex.response", self.on_pulse_event)

    async def on_unload(self, context: dict[str, Any]) -> None:
        pulse = context.get("pulse")
        if pulse:
            pulse.unsubscribe("cortex.response", self.on_pulse_event)

    # -- Pulse event handler --

    async def on_pulse_event(self, msg: Any) -> None:
        self._event_log.append({
            "topic": getattr(msg, "topic", "unknown"),
            "source": getattr(msg, "source", "unknown"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    # -- NexusModule interface --

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        msg_lower = message.lower()

        if "kill" in msg_lower or "revoke" in msg_lower or "deny autonomic" in msg_lower:
            self.kill_switch()
            chronicle = context.get("chronicle")
            if chronicle:
                chronicle.log("autonomic", "kill_switch", {"reason": message[:200]})
            return "[Autonomic] All autonomous permissions revoked. All domain trust reset to 0. Observer mode only."

        if "status" in msg_lower or "trust" in msg_lower:
            lines = ["[Autonomic] Domain Trust Status:"]
            if not self._domains:
                lines.append("  No domains tracked yet. Operating in Observer mode.")
            for domain, dt in sorted(self._domains.items()):
                tier = TrustTier.from_score(dt.trust_score)
                cooldown = " (COOLDOWN)" if self.is_in_cooldown(domain) else ""
                lines.append(
                    f"  {domain}: trust={dt.trust_score} tier={tier.name} "
                    f"successes={dt.successes} failures={dt.failures}{cooldown}"
                )
            patterns = self.get_patterns()
            if patterns:
                lines.append(f"\nPatterns observed: {len(patterns)}")
                for p in patterns[:5]:
                    lines.append(f"  [{p.category}] {p.description} (confidence={p.confidence:.2f}, observed={p.times_observed})")
            return "\n".join(lines)

        if "pattern" in msg_lower or "routine" in msg_lower or "automate" in msg_lower:
            patterns = self.get_patterns()
            if not patterns:
                return "[Autonomic] No patterns detected yet. Still observing. Patterns emerge from repeated actions tracked through Pulse events."
            lines = ["[Autonomic] Detected Patterns:"]
            for p in patterns:
                lines.append(
                    f"  [{p.category}] {p.description}\n"
                    f"    confidence={p.confidence:.2f} observed={p.times_observed} "
                    f"approved={p.times_approved} rejected={p.times_rejected}"
                )
            return "\n".join(lines)

        return (
            "[Autonomic] Observing and learning. "
            f"Tracking {len(self._domains)} domains, {len(self._patterns)} patterns, "
            f"{len(self._event_log)} events logged. "
            "Use 'autonomic status' for details or 'autonomic patterns' to see detected routines."
        )
