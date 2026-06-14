# nexus/modules/chronos.py
"""Chronos -- temporal counterfactual reasoning (N2.2). Wraps synthesis.chronos."""
from __future__ import annotations

import re
from typing import Any

from nexus.modules.base import NexusModule
from nexus.synthesis.chronos import Chronos


_CF_RE = re.compile(
    r"(?:what\s+if|counterfactual[:,]?)\s+(?P<module>[\w-]+)\s+(?P<action>[\w.]+)?",
    re.IGNORECASE,
)


class ChronosModule(NexusModule):
    name = "chronos"
    description = (
        "Temporal counterfactual reasoning -- replay the decision history with "
        "one node flipped and report which downstream actions depended on it"
    )
    version = "1.0.0"

    @classmethod
    def manifest(cls):
        from nexus.agents.manifest import Manifest
        return Manifest.model_validate({
            "manifest_version": 1,
            "slug": "chronos",
            "name": "chronos",
            "tagline": "Counterfactuals: replay the decision DAG with one node flipped.",
            "version": cls.version,
            "system": True,
            "publisher": {"type": "org", "handle": "nexus"},
            "category": "reasoning",
            "license": "Apache-2.0",
            "identity": {"mark": {"kind": "builtin:chronos",
                                  "gradient": ["#b8c4ff", "#3a4a9c"]}},
            "intents": [{
                "name": "COUNTERFACTUAL",
                "patterns": [
                    r"\bchronos\b", r"\bcounterfactual\b", r"\bwhat\s+if\b",
                    r"\bwould\s+have\s+happened\b", r"\bdecision\s+history\b",
                    r"\bdecision\s+timeline\b", r"\bif\s+.*\s+had\s+been\s+denied\b",
                ],
                "semantic_signals": [
                    "chronos", "counterfactual", "what would have happened",
                    "what if", "decision history", "decision timeline",
                    "if that grant had been denied", "replay decisions",
                ],
                "weight": 1.0,
            }],
            "capabilities": {
                "tools": [{"name": "handle", "class": "Routine"}],
                "declared": {"Routine": ["chronicle.read.workspace"],
                             "Notable": [], "Sensitive": [], "Privileged": []},
            },
            "runtime": {"transport": "in_process"},
            "trust": {"floor": 0.30, "default_tier": "ADVISOR"},
        })

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        aegis = context.get("aegis")
        chronicle = context.get("chronicle")
        if aegis is not None:
            decision = aegis.check_capability("chronos", "chronicle.read.workspace")
            if decision.verdict.value != "ALLOW":
                return "[Chronos] Read blocked by Aegis: " + decision.reason
        if chronicle is None:
            return "[Chronos] Chronicle unavailable."
        chronos = Chronos(chronicle)

        m = _CF_RE.search(message)
        if m and ("what if" in message.lower() or "counterfactual" in message.lower()):
            module = m.group("module").lower()
            action = (m.group("action") or "permission_granted").lower()
            result = chronos.counterfactual_by(module=module, action=action)
            chronicle.log("chronos", "query",
                          {"mode": "counterfactual", "module": module, "action": action})
            if result["flipped"] is None:
                return f"[Chronos] No recorded '{action}' decision for '{module}' to flip."
            lines = [
                f"[Chronos] Counterfactual: if {module}'s {action} had been denied —",
                f"  flipped: {result['flipped']['action']} @ {result['flipped']['timestamp'][:19]} "
                f"(event {result['flipped']['id']})",
                "  Would NOT have happened:",
            ]
            for a in result["would_not_have_happened"]:
                lines.append(f"    - {a['module']} · {a['action']} · {a['preview'][:48]}")
            if not result["would_not_have_happened"]:
                lines.append("    (nothing downstream depended on it)")
            return "\n".join(lines)

        timeline = chronos.timeline(limit=40)
        chronicle.log("chronos", "query", {"mode": "timeline", "results": len(timeline)})
        if not timeline:
            return "[Chronos] No decisions recorded yet."
        lines = ["[Chronos] Decision timeline (branch points marked *):"]
        for d in timeline[-15:]:
            mark = "*" if d["branch_point"] else " "
            lines.append(f"  {mark} {d['timestamp'][:19]} {d['kind']:<8} "
                         f"{(d['module'] or '-'):<10} {d['preview'][:40]}")
        return "\n".join(lines)
