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
    # Informational, NOT high-stakes — a swarm fanning out to many agents in a
    # short window. Surfaces real activity on the radar (e.g. a cortex launch)
    # at HIGH priority, so it never trips the emergency veil.
    "swarm_burst": DetectionRule(
        name="swarm_burst",
        description="Many agents routed in a short window — a swarm is active",
        severity="high", high_stakes=False, window_s=20.0, threshold=4,
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
            return self._check_runaway_loop(event) + self._check_swarm_burst(event)
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

    def _check_swarm_burst(self, event: dict) -> list[Detection]:
        """Informational: many distinct routes in a short window (a swarm is
        active, e.g. a cortex launch). Fires once per window bucket so it pulses
        the radar during bursts rather than spamming it."""
        rule = self._rules.get("swarm_burst")
        if rule is None:
            return []
        ts = float(event["ts"])
        recent = [e for e in self._route_events if 0 <= ts - float(e["ts"]) <= rule.window_s]
        if len(recent) < rule.threshold:
            return []
        modules = sorted({str(e.get("module")) for e in recent if e.get("module")})
        return self._fire(rule, str(event.get("module") or "cortex"),
                          ("swarm_burst", int(ts // rule.window_s)),
                          [{"routes": len(recent), "modules": modules[:8]}], ts)

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


class SigilModule(NexusModule):
    name = "sigil"
    description = (
        "Threat radar -- deterministic detection of trust collapse, denied-call "
        "bursts, runaway loops, anomalous egress cadence, and permission escalation"
    )
    version = "1.0.0"

    @classmethod
    def manifest(cls):
        from nexus.agents.manifest import Manifest
        return Manifest.model_validate({
            "manifest_version": 1,
            "slug": "sigil",
            "name": "sigil",
            "tagline": "Threat radar: trust collapse, denied bursts, runaway loops, egress anomalies.",
            "version": cls.version,
            "system": True,
            "publisher": {"type": "org", "handle": "nexus"},
            "category": "monitoring",
            "license": "Apache-2.0",
            "identity": {"mark": {"kind": "builtin:sigil",
                                  "gradient": ["#ffb4a8", "#a82a1c"]}},
            "intents": [{
                "name": "THREAT_RADAR",
                "patterns": [
                    r"\bsigil\b", r"\bthreat\s+radar\b", r"\btrust\s+collapse\b",
                    r"\bdenied\s+calls?\b", r"\bsecurity\s+sweep\b",
                    r"\bdetections?\s+log\b", r"\banomalous\s+egress\b",
                ],
                "semantic_signals": [
                    "threat radar", "trust collapse", "denied calls", "radar",
                    "security sweep", "detections", "what threats", "egress anomaly",
                ],
                "weight": 1.0,
            }],
            "capabilities": {
                "tools": [{"name": "handle", "class": "Routine"}],
                "declared": {"Routine": ["pulse.subscribe",
                                         "chronicle.read.workspace",
                                         "pulse.broadcast.emergency"],
                             "Notable": [], "Sensitive": [], "Privileged": []},
            },
            "runtime": {"transport": "in_process"},
            "trust": {"floor": 0.30, "default_tier": "ADVISOR"},
        })

    def __init__(self, engine: SigilRuleEngine | None = None):
        self._engine = engine or SigilRuleEngine()
        self._context: dict[str, Any] | None = None
        self._sub_ids: list[str] = []

    # -- lifecycle ----------------------------------------------------------

    async def on_load(self, context: dict[str, Any] | None = None) -> None:
        if not context or "pulse" not in context:
            return
        self._context = context
        aegis = context.get("aegis")
        if aegis is not None:
            decision = aegis.check_capability("sigil", "pulse.subscribe")
            if decision.verdict.value != "ALLOW":
                return
        pulse = context["pulse"]
        for topic in ("aegis.trust_change", "kernel.gate", "kernel.route"):
            self._sub_ids.append(pulse.subscribe(topic, self._on_pulse))

    async def on_unload(self, context: dict[str, Any] | None = None) -> None:
        ctx = context or self._context
        if ctx and "pulse" in ctx:
            for sid in self._sub_ids:
                ctx["pulse"].unsubscribe(sid)
        self._sub_ids = []

    # -- event ingestion ------------------------------------------------------

    def _normalize(self, msg: Message) -> dict[str, Any] | None:
        p = msg.payload or {}
        now = time.time()
        if msg.topic == "aegis.trust_change":
            return {"kind": "trust_change", "module": p.get("module"),
                    "old_score": p.get("old_score", 0.0),
                    "new_score": p.get("new_score", 0.0), "ts": now}
        if msg.topic == "kernel.gate":
            return {"kind": "gate", "module": p.get("agent"),
                    "capability": p.get("capability"), "verdict": p.get("verdict"),
                    "permission_class": p.get("permission_class"), "ts": now}
        if msg.topic == "kernel.route":
            return {"kind": "route", "module": p.get("target"),
                    "preview": p.get("message_preview", ""), "ts": now}
        return None

    async def _on_pulse(self, msg: Message) -> None:
        if msg.source == "sigil":
            return
        ev = self._normalize(msg)
        if ev is None:
            return
        detections = self._engine.observe(ev)
        if ev["kind"] == "gate" and str(ev.get("capability") or "").startswith("network.outbound"):
            detections += self._scan_egress()
        for det in detections:
            await self._broadcast(det)

    def _scan_egress(self) -> list[Detection]:
        chronicle = (self._context or {}).get("chronicle")
        if chronicle is None:
            return []
        rows = chronicle.query(source="aegis", action="network_request", limit=1000)
        stamps: list[float] = []
        for r in rows:
            try:
                stamps.append(datetime.fromisoformat(r["timestamp"]).timestamp())
            except (TypeError, ValueError):
                continue
        return self._engine.check_egress(stamps, now=time.time())

    # -- broadcast ------------------------------------------------------------

    async def _broadcast(self, det: Detection) -> None:
        ctx = self._context or {}
        chronicle, pulse, cortex = ctx.get("chronicle"), ctx.get("pulse"), ctx.get("cortex")
        rule = DETECTION_RULES.get(det.rule)
        payload: dict[str, Any] = {
            "rule": det.rule,
            "severity": det.severity,
            "module": det.module,
            "description": rule.description if rule else "",
            "evidence": det.evidence[:10],
            "detected_at": datetime.now(timezone.utc).isoformat(),
        }
        sentry = cortex.get_module("sentry") if cortex is not None and hasattr(cortex, "get_module") else None
        if sentry is not None and hasattr(sentry, "get_state"):
            payload["sentry_state"] = sentry.get_state().to_dict()
        payload["provenance"] = hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode()
        ).hexdigest()
        payload["activate_specter"] = bool(det.high_stakes)
        if chronicle is not None:
            chronicle.log("sigil", "detection", payload)
        if pulse is not None:
            # Only high-stakes detections go out at EMERGENCY priority (which the
            # shell renders as a full-surface alert veil + alert mood). Routine
            # detections broadcast at HIGH so they light up the Sigil radar
            # without nuking the whole app red.
            prio = Priority.EMERGENCY if det.high_stakes else Priority.HIGH
            await pulse.publish(Message(
                topic="sigil.detection", source="sigil",
                payload=payload, priority=prio,
            ))

    # -- handle ----------------------------------------------------------------

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        aegis = context.get("aegis")
        if aegis is not None:
            decision = aegis.check_capability("sigil", "chronicle.read.workspace")
            if decision.verdict.value != "ALLOW":
                return "[Sigil] Read blocked by Aegis: " + decision.reason
        chronicle = context.get("chronicle")
        rows = chronicle.query(source="sigil", action="detection", limit=10) if chronicle else []
        if not rows:
            return "[Sigil] Radar clear -- no detections recorded."
        lines = ["[Sigil] Recent detections:"]
        for r in rows:
            p = r["payload"]
            lines.append(
                f"  [{str(p.get('severity', '?')).upper()}] {p.get('rule', '?')} "
                f"on {p.get('module', '?')} at {r['timestamp']} "
                f"(provenance {str(p.get('provenance', ''))[:12]})"
            )
        return "\n".join(lines)
