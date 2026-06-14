# nexus/modules/prism.py
"""Prism -- cross-domain synthesis (N2.1). Aegis-gated cross-partition reads."""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from nexus.modules.base import NexusModule


class CrossDomainSynthesizer:
    def recurring_entities(self, partitions, min_workspaces=2):
        by_subject = defaultdict(set)
        cites = defaultdict(list)
        for ws_id, facts in partitions:
            for f in facts:
                by_subject[f["subject"]].add(ws_id)
                cites[f["subject"]].append(f"{ws_id}:{f.get('source_ref') or f.get('id', '')}")
        out = []
        for subject, workspaces in by_subject.items():
            if len(workspaces) >= min_workspaces:
                out.append({"subject": subject, "workspaces": sorted(workspaces),
                            "citations": cites[subject]})
        out.sort(key=lambda e: (-len(e["workspaces"]), e["subject"]))
        return out

    def contradictions(self, partitions):
        index = defaultdict(lambda: defaultdict(list))
        for ws_id, facts in partitions:
            for f in facts:
                index[(f["subject"], f["relation"])][f["object"]].append(
                    (ws_id, f.get("confidence", 0.0), f.get("source_ref") or ""))
        out = []
        for (subject, relation), objects in index.items():
            if len(objects) < 2:
                continue
            claims = []
            for obj, refs in objects.items():
                for ws_id, conf, cite in refs:
                    claims.append({"object": obj, "workspace": ws_id,
                                   "confidence": round(float(conf), 3),
                                   "citation": f"{ws_id}:{cite}"})
            claims.sort(key=lambda c: -c["confidence"])
            out.append({"subject": subject, "relation": relation, "claims": claims})
        out.sort(key=lambda c: c["subject"])
        return out


class PrismModule(NexusModule):
    name = "prism"
    description = (
        "Cross-domain synthesis -- reads across Engram partitions (Aegis-gated, "
        "always prompted) to surface recurring entities, contradictions, and "
        "patterns the per-workspace view can't see, with source citations"
    )
    version = "1.0.0"

    @classmethod
    def manifest(cls):
        from nexus.agents.manifest import Manifest
        return Manifest.model_validate({
            "manifest_version": 1,
            "slug": "prism", "name": "prism",
            "tagline": "Cross-domain synthesis: recurring entities, contradictions, patterns.",
            "version": cls.version, "system": True,
            "publisher": {"type": "org", "handle": "nexus"},
            "category": "reasoning", "license": "Apache-2.0",
            "identity": {"mark": {"kind": "builtin:prism", "gradient": ["#d8b4ff", "#5a2a9c"]}},
            "intents": [{
                "name": "CROSS_DOMAIN_SYNTHESIS",
                "patterns": [
                    r"\bprism\b", r"\bcross-?domain\b", r"\bcross-?workspace\b",
                    r"\bsynthesi[sz]e?\b", r"\bconnections?\s+across\b",
                    r"\brecurring\s+entit\w+\b", r"\bcontradictions?\s+across\b",
                ],
                "semantic_signals": [
                    "prism", "cross-domain synthesis", "across workspaces",
                    "recurring entities", "contradictions between workspaces",
                    "connections across", "synthesize across", "patterns across",
                ],
                "weight": 1.0,
            }],
            "capabilities": {
                "tools": [{"name": "handle", "class": "Routine"}],
                "declared": {"Routine": ["engram.read.workspace"], "Notable": [],
                             "Sensitive": ["engram.read.global"], "Privileged": []},
            },
            "runtime": {"transport": "in_process"},
            "trust": {"floor": 0.30, "default_tier": "ADVISOR"},
        })

    def __init__(self):
        self._synth = CrossDomainSynthesizer()

    def _load_partitions(self, mgr):
        from nexus.kernel.engram import Engram
        partitions = []
        for ws in mgr.list():
            db = mgr.workspace_dir(ws.workspace_id) / "engram" / "episodic.sqlite"
            if not db.exists():
                continue
            eng = Engram(db)
            conn = eng.atlas._conn()
            try:
                rows = conn.execute(
                    "SELECT id, subject, relation, object, confidence, source_ref "
                    "FROM atlas_facts").fetchall()
            except Exception:
                rows = []
            finally:
                conn.close()
            partitions.append((ws.workspace_id, [
                {"id": r["id"], "subject": r["subject"], "relation": r["relation"],
                 "object": r["object"], "confidence": float(r["confidence"]),
                 "source_ref": r["source_ref"]} for r in rows]))
        return partitions

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        aegis = context.get("aegis")
        chronicle = context.get("chronicle")
        mgr = context.get("workspace_manager")
        if mgr is None:
            return "[Prism] Workspace manager unavailable."
        granted = True
        if aegis is not None:
            decision = aegis.check_capability("prism", "engram.read.global")
            granted = decision.verdict.value == "ALLOW"
        if not granted:
            return ("[Prism] Cross-workspace synthesis needs approval — "
                    "`engram.read.global` is a Sensitive capability and is always "
                    "prompted. Grant it (Settings -> Security) to let Prism read "
                    "across partitions. No partitions were read.")
        partitions = self._load_partitions(mgr)
        want_contradictions = "contradiction" in message.lower()
        findings = (self._synth.contradictions(partitions) if want_contradictions
                    else self._synth.recurring_entities(partitions))
        mode = "contradictions" if want_contradictions else "recurring_entities"
        if chronicle is not None:
            chronicle.log("prism", "synthesis",
                          {"mode": mode, "partitions": [w for w, _ in partitions],
                           "findings": len(findings)})
        if not findings:
            return f"[Prism] No cross-workspace {mode.replace('_', ' ')} found."
        lines = [f"[Prism] Cross-workspace {mode.replace('_', ' ')} "
                 f"(read {len(partitions)} partitions):"]
        if mode == "recurring_entities":
            for e in findings[:10]:
                lines.append(f"  - '{e['subject']}' appears in {', '.join(e['workspaces'])} "
                             f"(sources: {', '.join(e['citations'][:4])})")
        else:
            for c in findings[:10]:
                lines.append(f"  - CONTRADICTION on {c['subject']} · {c['relation']}:")
                for claim in c["claims"][:4]:
                    lines.append(f"      {claim['object']} (conf {claim['confidence']:.2f}, "
                                 f"from {claim['workspace']}, cite {claim['citation']})")
        return "\n".join(lines)
