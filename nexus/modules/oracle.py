# nexus/modules/oracle.py
"""
Oracle -- anticipatory pattern detection engine.

Absorbs: sigil.

Combines trigger-rule-based pattern scanning with severity-prioritized
threat tracking. The unified scan() method runs both trigger evaluation
AND threat assessment in a single pass.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import IntEnum
from typing import Any

from nexus.modules.base import NexusModule


# ---------------------------------------------------------------------------
# Trigger rule engine (original Oracle)
# ---------------------------------------------------------------------------

@dataclass
class TriggerRule:
    name: str
    keywords: list[str]
    threshold: float
    description: str
    weight: float = 1.0


# ---------------------------------------------------------------------------
# Threat tracking (absorbed from sigil)
# ---------------------------------------------------------------------------

class ThreatSeverity(IntEnum):
    CRITICAL = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3
    INFO = 4


@dataclass
class Threat:
    id: str
    category: str
    description: str
    severity: ThreatSeverity
    source: str
    timestamp: str
    acknowledged: bool = False


# ---------------------------------------------------------------------------
# Scan result combining both systems
# ---------------------------------------------------------------------------

@dataclass
class ScanResult:
    fired_triggers: list[dict[str, Any]]
    active_threats: list[Threat]
    threat_count: int
    trigger_count: int
    summary: str


# ===========================================================================
# Oracle Module
# ===========================================================================

class OracleModule(NexusModule):
    name = "oracle"
    description = (
        "Anticipatory pattern detection -- trigger rules, keyword scoring, "
        "and severity-prioritized threat tracking"
    )
    version = "1.0.0"

    def __init__(self):
        self._rules: list[TriggerRule] = []
        self._threats: dict[str, Threat] = {}

    # -------------------------------------------------------------------
    # Trigger rule management (original)
    # -------------------------------------------------------------------

    def add_rule(self, rule: TriggerRule) -> None:
        self._rules.append(rule)

    def remove_rule(self, name: str) -> None:
        self._rules = [r for r in self._rules if r.name != name]

    def list_rules(self) -> list[TriggerRule]:
        return list(self._rules)

    def evaluate(self, text: str) -> list[dict[str, Any]]:
        """Score text against all rules. Return fired triggers (score > threshold)."""
        text_lower = text.lower()
        fired = []
        for rule in self._rules:
            if not rule.keywords:
                continue
            hits = sum(1 for kw in rule.keywords if kw.lower() in text_lower)
            score = (hits / len(rule.keywords)) * rule.weight
            if score >= rule.threshold:
                fired.append({
                    "rule": rule.name,
                    "score": round(score, 3),
                    "description": rule.description,
                    "matched_keywords": [kw for kw in rule.keywords if kw.lower() in text_lower],
                })
        return fired

    # -------------------------------------------------------------------
    # Threat tracking (absorbed from sigil)
    # -------------------------------------------------------------------

    def register_threat(
        self,
        category: str,
        description: str,
        severity: ThreatSeverity,
        source: str,
    ) -> Threat:
        threat_id = uuid.uuid4().hex[:8]
        ts = datetime.now(timezone.utc).isoformat()
        threat = Threat(
            id=threat_id,
            category=category,
            description=description,
            severity=severity,
            source=source,
            timestamp=ts,
        )
        self._threats[threat_id] = threat
        return threat

    def get_threat(self, threat_id: str) -> Threat | None:
        return self._threats.get(threat_id)

    def acknowledge(self, threat_id: str) -> None:
        threat = self._threats.get(threat_id)
        if threat:
            threat.acknowledged = True

    def list_threats(
        self,
        min_severity: ThreatSeverity | None = None,
        unacknowledged_only: bool = False,
    ) -> list[Threat]:
        threats = list(self._threats.values())
        if min_severity is not None:
            threats = [t for t in threats if t.severity <= min_severity]
        if unacknowledged_only:
            threats = [t for t in threats if not t.acknowledged]
        threats.sort(key=lambda t: t.severity)
        return threats

    # -------------------------------------------------------------------
    # Unified scan (runs both trigger evaluation AND threat assessment)
    # -------------------------------------------------------------------

    def scan(self, text: str) -> ScanResult:
        """
        Run both trigger evaluation and threat assessment in one pass.
        Returns a combined result with fired triggers and active threats.
        """
        fired = self.evaluate(text)
        active_threats = self.list_threats(unacknowledged_only=True)

        # Auto-register threats from high-scoring triggers
        for trigger in fired:
            if trigger["score"] >= 0.7:
                severity = ThreatSeverity.HIGH
            elif trigger["score"] >= 0.5:
                severity = ThreatSeverity.MEDIUM
            else:
                severity = ThreatSeverity.LOW

            # Only auto-register if we don't already have a similar threat
            existing_descriptions = {t.description for t in self._threats.values()}
            threat_desc = f"Trigger '{trigger['rule']}' fired: {trigger['description']}"
            if threat_desc not in existing_descriptions:
                self.register_threat(
                    category=trigger["rule"],
                    description=threat_desc,
                    severity=severity,
                    source="oracle/trigger",
                )

        # Re-fetch after potential new registrations
        active_threats = self.list_threats(unacknowledged_only=True)

        summary_parts = []
        if fired:
            summary_parts.append(f"{len(fired)} trigger(s) fired")
        if active_threats:
            summary_parts.append(f"{len(active_threats)} active threat(s)")
        if not summary_parts:
            summary_parts.append("All clear -- no triggers fired, no active threats")

        return ScanResult(
            fired_triggers=fired,
            active_threats=active_threats,
            threat_count=len(active_threats),
            trigger_count=len(fired),
            summary=". ".join(summary_parts) + ".",
        )

    # -------------------------------------------------------------------
    # handle()
    # -------------------------------------------------------------------

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        result = self.scan(message)

        lines = [f"[Oracle] {result.summary}"]

        if result.fired_triggers:
            lines.append("")
            lines.append("Triggered alerts:")
            for t in result.fired_triggers:
                lines.append(f"  - {t['rule']} (score: {t['score']}) -- {t['description']}")
                lines.append(f"    Matched: {', '.join(t['matched_keywords'])}")

        if result.active_threats:
            lines.append("")
            lines.append("Active threats:")
            for threat in result.active_threats:
                sev_name = threat.severity.name
                lines.append(f"  [{sev_name}] {threat.category}: {threat.description}")
                lines.append(f"    Source: {threat.source} | {threat.timestamp}")

        return "\n".join(lines)
