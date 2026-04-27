"""
Oracle — anticipatory trigger engine.
Scans input against configurable trigger rules with keyword-weighted scoring.
Fires events when pattern density exceeds thresholds.
Observe-only: Oracle never takes actions, only surfaces information.
"""
from dataclasses import dataclass, field
from typing import Any
from nexus.modules.base import NexusModule


@dataclass
class TriggerRule:
    name: str
    keywords: list[str]
    threshold: float
    description: str
    weight: float = 1.0


class OracleModule(NexusModule):
    name = "oracle"
    description = "Anticipatory trigger engine — scans for patterns and fires events"
    version = "0.1.0"

    def __init__(self):
        self._rules: list[TriggerRule] = []

    def add_rule(self, rule: TriggerRule) -> None:
        self._rules.append(rule)

    def remove_rule(self, name: str) -> None:
        self._rules = [r for r in self._rules if r.name != name]

    def list_rules(self) -> list[TriggerRule]:
        return list(self._rules)

    def evaluate(self, text: str) -> list[dict[str, Any]]:
        """Score text against all rules. Return fired triggers (score > threshold)."""
        text_lower = text.lower()
        words = set(text_lower.split())
        fired = []
        for rule in self._rules:
            hits = sum(1 for kw in rule.keywords if kw.lower() in text_lower)
            if not rule.keywords:
                continue
            score = (hits / len(rule.keywords)) * rule.weight
            if score >= rule.threshold:
                fired.append({
                    "rule": rule.name,
                    "score": round(score, 3),
                    "description": rule.description,
                    "matched_keywords": [kw for kw in rule.keywords if kw.lower() in text_lower],
                })
        return fired

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        fired = self.evaluate(message)
        if not fired:
            return "[Oracle] No triggers fired. No active patterns match this input."
        lines = ["[Oracle] Triggered alerts:"]
        for t in fired:
            lines.append(f"  - {t['rule']} (score: {t['score']}) — {t['description']}")
            lines.append(f"    Matched: {', '.join(t['matched_keywords'])}")
        return "\n".join(lines)
