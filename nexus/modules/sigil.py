# nexus/modules/sigil.py
"""
Sigil -- threat radar (N1.1).

Watches the kernel's own behavior: Aegis trust deltas, gate verdicts,
Cortex routing traffic, and the Aegis network log (Chronicle). Detection
rules are deterministic and table-driven (DETECTION_RULES). On detection,
Sigil broadcasts a Pulse message at EMERGENCY priority carrying a
provenance hash, records it in Chronicle, and flags high-stakes detections
for Specter auto-activation via the Cortex emergency bypass.
"""
from __future__ import annotations

import hashlib
import json
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from nexus.modules.base import NexusModule
from nexus.kernel.pulse import Message, Priority


TIER_ORDER = ["OBSERVER", "ADVISOR", "MONITOR", "EXECUTOR", "AUTONOMOUS"]


@dataclass(frozen=True)
class DetectionRule:
    name: str
    description: str
    severity: str          # "high" | "critical"
    high_stakes: bool      # auto-activates Specter via Cortex bypass
    window_s: float = 300.0
    threshold: int = 5


DETECTION_RULES: dict[str, DetectionRule] = {
    "trust_collapse": DetectionRule(
        name="trust_collapse",
        description="Module trust fell a full tier within this session",
        severity="critical", high_stakes=True,
    ),
    "denied_burst": DetectionRule(
        name="denied_burst",
        description="Burst of denied calls from one module",
        severity="high", high_stakes=False, window_s=300.0, threshold=5,
    ),
    "runaway_loop": DetectionRule(
        name="runaway_loop",
        description="Same module re-routed with identical input at loop cadence",
        severity="high", high_stakes=True, window_s=120.0, threshold=8,
    ),
    "egress_anomaly": DetectionRule(
        name="egress_anomaly",
        description="Outbound network cadence spiked vs workspace baseline",
        severity="high", high_stakes=False, window_s=60.0, threshold=4,
    ),
    "permission_escalation": DetectionRule(
        name="permission_escalation",
        description="Repeated privileged capability requests after denial",
        severity="critical", high_stakes=True, window_s=600.0, threshold=3,
    ),
}


@dataclass
class Detection:
    rule: str
    severity: str
    high_stakes: bool
    module: str
    detected_at: float
    evidence: list[dict[str, Any]] = field(default_factory=list)


class SigilRuleEngine:
    """Deterministic, table-driven detection over normalized kernel events.

    Events are dicts with a "kind" and a float "ts" (unix seconds):
      {"kind": "trust_change", "module", "old_score", "new_score", "ts"}
      {"kind": "gate", "module", "capability", "verdict", "permission_class", "ts"}
      {"kind": "route", "module", "preview", "ts"}
    Network egress timestamps come from Aegis's Chronicle network log and
    are passed to check_egress() separately.
    """

    def __init__(self, rules: dict[str, DetectionRule] | None = None):
        self._rules = dict(rules if rules is not None else DETECTION_RULES)
        self._gate_events: deque[dict] = deque(maxlen=1024)
        self._route_events: deque[dict] = deque(maxlen=1024)
        self._fired: set[tuple] = set()

    @staticmethod
    def _tier_index(score: float) -> int:
        from nexus.kernel.aegis import TrustTier
        return TIER_ORDER.index(TrustTier.from_score(float(score)))

    def observe(self, event: dict[str, Any]) -> list[Detection]:
        kind = event.get("kind")
        if kind == "trust_change":
            return self._check_trust_collapse(event)
        if kind == "gate":
            self._gate_events.append(event)
            return self._check_denied_burst(event) + self._check_permission_escalation(event)
        if kind == "route":
            self._route_events.append(event)
            return self._check_runaway_loop(event)
        return []

    def _fire(self, rule: DetectionRule, module: str, key: tuple,
              evidence: list[dict], ts: float) -> list[Detection]:
        if key in self._fired:
            return []
        self._fired.add(key)
        return [Detection(rule=rule.name, severity=rule.severity,
                          high_stakes=rule.high_stakes, module=module,
                          detected_at=ts, evidence=evidence)]

    def _check_trust_collapse(self, event: dict) -> list[Detection]:
        rule = self._rules.get("trust_collapse")
        if rule is None:
            return []
        old_i = self._tier_index(event.get("old_score", 0.0))
        new_i = self._tier_index(event.get("new_score", 0.0))
        if old_i - new_i < 1:
            return []
        module = str(event.get("module"))
        return self._fire(rule, module, ("trust_collapse", module, old_i, new_i),
                          [event], float(event["ts"]))

    def _check_denied_burst(self, event: dict) -> list[Detection]:
        rule = self._rules.get("denied_burst")
        if rule is None or event.get("verdict") != "DENY":
            return []
        module, ts = event.get("module"), float(event["ts"])
        recent = [e for e in self._gate_events
                  if e.get("module") == module and e.get("verdict") == "DENY"
                  and 0 <= ts - float(e["ts"]) <= rule.window_s]
        if len(recent) < rule.threshold:
            return []
        return self._fire(rule, str(module),
                          ("denied_burst", module, int(ts // rule.window_s)),
                          recent[-rule.threshold:], ts)

    def _check_permission_escalation(self, event: dict) -> list[Detection]:
        rule = self._rules.get("permission_escalation")
        if rule is None or event.get("permission_class") != "Privileged":
            return []
        if event.get("verdict") not in ("PROMPT", "DENY"):
            return []
        module, cap, ts = event.get("module"), event.get("capability"), float(event["ts"])
        recent = [e for e in self._gate_events
                  if e.get("module") == module and e.get("capability") == cap
                  and e.get("verdict") in ("PROMPT", "DENY")
                  and 0 <= ts - float(e["ts"]) <= rule.window_s]
        if len(recent) < rule.threshold:
            return []
        return self._fire(rule, str(module),
                          ("permission_escalation", module, cap, int(ts // rule.window_s)),
                          recent[-rule.threshold:], ts)

    def _check_runaway_loop(self, event: dict) -> list[Detection]:
        rule = self._rules.get("runaway_loop")
        if rule is None:
            return []
        module, preview, ts = event.get("module"), event.get("preview"), float(event["ts"])
        recent = [e for e in self._route_events
                  if e.get("module") == module and e.get("preview") == preview
                  and 0 <= ts - float(e["ts"]) <= rule.window_s]
        if len(recent) < rule.threshold:
            return []
        return self._fire(rule, str(module),
                          ("runaway_loop", module, int(ts // rule.window_s)),
                          recent[-3:], ts)

    def check_egress(self, network_ts: list[float], *, now: float) -> list[Detection]:
        """Anomalous egress cadence vs the trailing-hour workspace baseline."""
        rule = self._rules.get("egress_anomaly")
        if rule is None:
            return []
        recent = [t for t in network_ts if 0 <= now - t <= rule.window_s]
        history = [t for t in network_ts if rule.window_s < now - t <= 3600.0]
        baseline_per_min = len(history) / 59.0 if history else 0.0
        if len(recent) < 10:
            return []
        if baseline_per_min > 0 and len(recent) <= baseline_per_min * rule.threshold:
            return []
        return self._fire(rule, "aegis", ("egress_anomaly", int(now // rule.window_s)),
                          [{"recent_per_min": len(recent),
                            "baseline_per_min": round(baseline_per_min, 3)}], now)
