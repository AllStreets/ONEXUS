"""Serendipity — anti-optimization discovery (N3.3, pure).

Deliberately surfaces low-relevance / high-novelty items on a budget, so the
system shows you what optimization would have hidden. Deterministic.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Candidate:
    id: str
    text: str
    relevance: float   # [0,1] match to the query
    novelty: float     # [0,1] inverse familiarity
    source: str        # citation (atlas:<id> / engram:<id>)


class SerendipityEngine:
    def __init__(self, *, relevance_ceiling: float = 0.5):
        self._ceiling = relevance_ceiling

    def discover(self, candidates: list[Candidate], *, budget: int) -> list[dict[str, Any]]:
        eligible = [c for c in candidates if c.relevance <= self._ceiling]
        eligible.sort(key=lambda c: (-c.novelty, c.id))
        chosen = eligible[: max(0, budget)]
        return [{"id": c.id, "text": c.text, "relevance": round(c.relevance, 4),
                 "novelty": round(c.novelty, 4), "source": c.source} for c in chosen]
