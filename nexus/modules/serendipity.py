# nexus/modules/serendipity.py
"""
Serendipity — anti-optimization engine.
Monitors what the user focuses on, identifies adjacent fields they are NOT
looking at, and surfaces surprising cross-domain connections with deep
structural similarity. Uses an inverted relevance function — penalizes
obvious connections, rewards surprising ones.

Data pipeline: subscribes to cortex.response events via Pulse, automatically
recording user messages as focus areas and module responses as knowledge entries.
"""
import re
from dataclasses import dataclass, field
from typing import Any
from nexus.modules.base import NexusModule


@dataclass
class KnowledgeEntry:
    domain: str
    content: str
    tags: list[str]


@dataclass
class SurprisingConnection:
    source_domain: str
    content: str
    shared_concepts: list[str]
    surprise_score: float
    explanation: str


def _extract_terms(text: str) -> set[str]:
    return set(re.findall(r'\b[a-z]{3,}\b', text.lower()))


class SerendipityModule(NexusModule):
    name = "serendipity"
    description = "Anti-optimization — surfaces surprising cross-domain connections"
    version = "0.1.0"

    def __init__(self):
        self._focus_areas: list[str] = []
        self._knowledge: list[KnowledgeEntry] = []
        self._sub_id: str | None = None

    async def on_load(self, context: dict[str, Any] | None = None) -> None:
        if context and "pulse" in context:
            self._sub_id = context["pulse"].subscribe(
                "cortex.response", self._on_response
            )

    async def on_unload(self, context: dict[str, Any] | None = None) -> None:
        if self._sub_id and context and "pulse" in context:
            context["pulse"].unsubscribe(self._sub_id)
            self._sub_id = None

    async def _on_response(self, msg) -> None:
        payload = msg.payload
        module = payload.get("module", "unknown")
        if module == self.name:
            return
        message = payload.get("message", "")
        response = payload.get("response", "")
        self.record_focus(message)
        tags = list(_extract_terms(response))[:10]
        self.add_knowledge(domain=module, content=response[:200], tags=tags)

    def record_focus(self, area: str) -> None:
        self._focus_areas.append(area)

    def list_focus_areas(self) -> list[str]:
        return list(self._focus_areas)

    def add_knowledge(self, domain: str, content: str, tags: list[str]) -> None:
        self._knowledge.append(KnowledgeEntry(domain=domain, content=content, tags=tags))

    def list_knowledge(self) -> list[KnowledgeEntry]:
        return list(self._knowledge)

    def find_connections(self) -> list[SurprisingConnection]:
        if not self._focus_areas or not self._knowledge:
            return []

        focus_terms = set()
        for area in self._focus_areas:
            focus_terms.update(_extract_terms(area))

        connections = []
        for entry in self._knowledge:
            entry_terms = set(t.lower() for t in entry.tags) | _extract_terms(entry.content)
            shared = focus_terms & entry_terms
            if not shared:
                continue

            # Domain distance: same domain = 0 surprise, distant domain = high surprise
            focus_domains = [_extract_terms(a) for a in self._focus_areas]
            domain_terms = _extract_terms(entry.domain)
            domain_overlap = sum(1 for fd in focus_domains for t in domain_terms if t in fd)

            # Surprise = concept overlap * domain distance
            concept_overlap = len(shared) / max(len(focus_terms | entry_terms), 1)
            domain_distance = 1.0 / (1.0 + domain_overlap)
            surprise = round(concept_overlap * domain_distance, 3)

            if surprise > 0:
                connections.append(SurprisingConnection(
                    source_domain=entry.domain,
                    content=entry.content,
                    shared_concepts=sorted(shared),
                    surprise_score=surprise,
                    explanation=f"Connects {entry.domain} to your focus via: {', '.join(sorted(shared))}",
                ))

        connections.sort(key=lambda c: c.surprise_score, reverse=True)
        return connections

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        if not self._focus_areas:
            return "[Serendipity] No focus areas recorded. Tell me what you're working on first."
        if not self._knowledge:
            return "[Serendipity] No knowledge base entries. Feed me content from other domains."

        connections = self.find_connections()
        if not connections:
            return "[Serendipity] No surprising connections found yet. Keep feeding diverse knowledge."
        lines = [f"[Serendipity] {len(connections)} surprising connection(s):"]
        for c in connections[:5]:
            lines.append(f"  [{c.source_domain}] (surprise: {c.surprise_score})")
            lines.append(f"    {c.content}")
            lines.append(f"    {c.explanation}")
        return "\n".join(lines)
