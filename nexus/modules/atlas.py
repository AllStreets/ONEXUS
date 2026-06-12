# nexus/modules/atlas.py
"""
Atlas -- living world model (N1.2).

The temporal knowledge graph over Engram's semantic tier. Facts are
(subject, relation, object) triples with confidence that decays at read
time; re-confirmation restores it; contradictory facts coexist. Answers
"what do we believe about X, with what confidence, learned when, from
where" -- with citations to Chronicle/Engram sources.
"""
from __future__ import annotations

import re
from typing import Any

from nexus.modules.base import NexusModule


_OBSERVE_RE = re.compile(
    r"^\s*(?:atlas[:,]?\s*)?(?:observe|remember)\s*:\s*"
    r"(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*(?:\|\s*([0-9.]+))?\s*$",
    re.IGNORECASE,
)
_QUERY_PREFIX_RE = re.compile(
    r"^\s*(?:atlas[:,]?\s*)?(?:what\s+do\s+we\s+(?:know|believe)\s+about\s+)?",
    re.IGNORECASE,
)


class AtlasModule(NexusModule):
    name = "atlas"
    description = (
        "Living world model -- temporal knowledge graph with confidence decay, "
        "re-confirmation, contradictions, and source citations"
    )
    version = "1.0.0"

    @classmethod
    def manifest(cls):
        from nexus.agents.manifest import Manifest
        return Manifest.model_validate({
            "manifest_version": 1,
            "slug": "atlas",
            "name": "atlas",
            "tagline": "World model: temporal facts with confidence decay and citations.",
            "version": cls.version,
            "system": True,
            "publisher": {"type": "org", "handle": "nexus"},
            "category": "memory",
            "license": "Apache-2.0",
            "identity": {"mark": {"kind": "builtin:atlas",
                                  "gradient": ["#7ee8b2", "#1c6a4a"]}},
            "intents": [{
                "name": "WORLD_MODEL",
                "patterns": [
                    r"\batlas\b", r"\bknowledge\s+graph\b", r"\bworld\s+model\b",
                    r"\bwhat\s+do\s+we\s+(?:know|believe)\b", r"\bfacts?\s+about\b",
                    r"\bobserve\s*:", r"\bremember\s*:",
                ],
                "semantic_signals": [
                    "atlas", "knowledge graph", "world model", "what do we know about",
                    "what do we believe", "facts about", "remember that", "observe",
                ],
                "weight": 1.0,
            }],
            "capabilities": {
                "tools": [{"name": "handle", "class": "Routine"}],
                "declared": {"Routine": ["engram.read.workspace",
                                         "engram.write.workspace"],
                             "Notable": [], "Sensitive": [], "Privileged": []},
            },
            "runtime": {"transport": "in_process"},
            "trust": {"floor": 0.30, "default_tier": "ADVISOR"},
        })

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        aegis = context.get("aegis")
        engram = context.get("engram")
        chronicle = context.get("chronicle")
        if engram is None or not hasattr(engram, "atlas"):
            return "[Atlas] Engram atlas tier unavailable."

        m = _OBSERVE_RE.match(message)
        if m:
            if aegis is not None:
                decision = aegis.check_capability("atlas", "engram.write.workspace")
                if decision.verdict.value != "ALLOW":
                    return "[Atlas] Write blocked by Aegis: " + decision.reason
            subject = m.group(1).strip().lower()
            relation = m.group(2).strip().lower()
            obj = m.group(3).strip()
            confidence = float(m.group(4)) if m.group(4) else 0.9
            source_ref = ""
            if chronicle is not None:
                event_id = chronicle.log("atlas", "observe", {
                    "subject": subject, "relation": relation,
                    "object": obj, "confidence": confidence,
                })
                source_ref = f"chronicle:{event_id}"
            fact_id = engram.atlas.observe(
                subject, relation, obj,
                confidence=confidence, source_ref=source_ref,
            )
            return (f"[Atlas] Recorded {subject} --{relation}--> {obj} "
                    f"(confidence {confidence:.2f}, fact {fact_id}, "
                    f"source {source_ref or 'unrecorded'})")

        if aegis is not None:
            decision = aegis.check_capability("atlas", "engram.read.workspace")
            if decision.verdict.value != "ALLOW":
                return "[Atlas] Read blocked by Aegis: " + decision.reason
        subject = _QUERY_PREFIX_RE.sub("", message, count=1).strip(" ?.").lower()
        beliefs = engram.atlas.beliefs(subject) if subject else []
        if chronicle is not None:
            chronicle.log("atlas", "query", {"subject": subject, "results": len(beliefs)})
        if not beliefs:
            return f"[Atlas] No beliefs recorded about '{subject}'."
        lines = [f"[Atlas] Beliefs about '{subject}':"]
        for b in beliefs[:10]:
            lines.append(
                f"  - {b['relation']}: {b['object']} "
                f"(confidence {b['confidence']:.2f}, learned {b['observed_at'][:10]}, "
                f"last confirmed {b['last_confirmed_at'][:10]}, "
                f"source {b['source_ref'] or 'unrecorded'})"
            )
        return "\n".join(lines)
