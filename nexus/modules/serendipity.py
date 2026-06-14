# nexus/modules/serendipity.py
"""Serendipity — anti-optimization discovery (N3.3).

Reads Atlas facts (workspace-scoped, Aegis-gated), scores each by relevance
(keyword overlap to the query) and novelty (inverse effective-confidence
rank), then deliberately surfaces high-novelty / low-relevance items on a
budget — the things optimization would have hidden. Every item cites its
source_ref; every discovery is logged to Chronicle.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from nexus.modules.base import NexusModule
from nexus.society.serendipity import Candidate, SerendipityEngine


class SerendipityModule(NexusModule):
    name = "serendipity"
    description = (
        "Anti-optimization discovery -- surfaces low-relevance / high-novelty "
        "facts from Engram/Atlas on a budget (Aegis-gated, cited, Chronicle-"
        "logged) so the system shows what optimization would have hidden"
    )
    version = "1.0.0"

    DEFAULT_BUDGET = 5

    @classmethod
    def manifest(cls):
        from nexus.agents.manifest import Manifest
        return Manifest.model_validate({
            "manifest_version": 1, "slug": "serendipity", "name": "serendipity",
            "tagline": "Anti-optimization discovery: the signal optimization hides.",
            "version": cls.version, "system": True,
            "publisher": {"type": "org", "handle": "nexus"},
            "category": "reasoning", "license": "Apache-2.0",
            "identity": {"mark": {"kind": "builtin:serendipity",
                                  "gradient": ["#ffc4f0", "#7a2a6a"]}},
            "intents": [{
                "name": "SERENDIPITY",
                "patterns": [r"\bserendipit\w*\b", r"\bsurprise\s+me\b",
                             r"\bunexpected\b", r"\bnovel\b", r"\boff-?the-?beaten\b",
                             r"\banti-?optimi[sz]ation\b"],
                "semantic_signals": ["serendipity", "surprise me", "show me something",
                                     "unexpected", "novelty", "discover", "off the path",
                                     "what am I missing"],
                "weight": 1.0,
            }],
            "capabilities": {
                "tools": [{"name": "handle", "class": "Routine"}],
                "declared": {"Routine": ["engram.read.workspace"], "Notable": [],
                             "Sensitive": [], "Privileged": []},
            },
            "runtime": {"transport": "in_process"},
            "trust": {"floor": 0.30, "default_tier": "ADVISOR"},
        })

    def __init__(self):
        self._engine = SerendipityEngine(relevance_ceiling=0.5)

    # ── candidate construction ──────────────────────────────────────────────

    @staticmethod
    def _keyword_overlap(query: str, text: str) -> float:
        q = {w for w in query.lower().split() if w}
        if not q:
            return 0.0
        t = {w for w in text.lower().split() if w}
        if not t:
            return 0.0
        return len(q & t) / len(q)

    def _build_candidates(self, eng, query: str) -> list[Candidate]:
        conn = eng.atlas._conn()
        try:
            rows = conn.execute(
                "SELECT id, subject, relation, object, fact_class, confidence, "
                "last_confirmed_at, source_ref FROM atlas_facts").fetchall()
        except Exception:
            rows = []
        finally:
            conn.close()
        if not rows:
            return []
        now = datetime.now(timezone.utc)
        effective = []
        for r in rows:
            eff = eng.atlas.effective_confidence(
                float(r["confidence"]), r["last_confirmed_at"],
                r["fact_class"], now)
            effective.append((r, eff))
        # novelty = 1 - confidence-rank fraction; least-confident = most novel
        ranked = sorted(effective, key=lambda x: x[1])  # ascending confidence
        n = len(ranked)
        candidates: list[Candidate] = []
        for idx, (r, eff) in enumerate(ranked):
            novelty = 1.0 if n == 1 else (n - 1 - idx) / (n - 1)
            text = f"{r['subject']} {r['relation']} {r['object']}"
            relevance = self._keyword_overlap(query, text)
            candidates.append(Candidate(
                id=r["id"], text=text, relevance=relevance, novelty=novelty,
                source=r["source_ref"] or f"atlas:{r['id']}"))
        return candidates

    def discover(self, ctx, query: str, budget: int = DEFAULT_BUDGET) -> dict[str, Any]:
        aegis = ctx.get("aegis")
        chronicle = ctx.get("chronicle")
        workspace_id = ctx.get("workspace_id")
        eng = ctx.get("engram")
        if eng is None:
            return {"gated": False, "query": query, "budget": budget, "items": []}
        granted = True
        if aegis is not None:
            decision = aegis.check_capability(
                "serendipity", "engram.read.workspace", workspace_id)
            granted = decision.verdict.value == "ALLOW"
        if not granted:
            if chronicle is not None:
                chronicle.log("serendipity", "discovery",
                              {"query": query, "gated": True, "items": 0})
            return {"gated": True, "query": query, "budget": budget, "items": []}
        candidates = self._build_candidates(eng, query)
        items = self._engine.discover(candidates, budget=budget)
        if chronicle is not None:
            chronicle.log("serendipity", "discovery",
                          {"query": query, "budget": budget, "items": len(items),
                           "sources": [i["source"] for i in items]})
        return {"gated": False, "query": query, "budget": budget, "items": items}

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        result = self.discover(context, message, self.DEFAULT_BUDGET)
        if result["gated"]:
            return ("[Serendipity] Workspace read needs approval — "
                    "`engram.read.workspace` was denied. Nothing was read.")
        items = result["items"]
        if not items:
            return "[Serendipity] No off-axis discoveries surfaced for this query."
        lines = [f"[Serendipity] {len(items)} discoveries optimization would hide:"]
        for it in items:
            lines.append(f"  - {it['text']} (novelty {it['novelty']:.2f}, "
                         f"relevance {it['relevance']:.2f}, source {it['source']})")
        return "\n".join(lines)
