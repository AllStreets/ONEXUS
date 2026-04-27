# nexus/modules/dreamweaver.py
"""
Dreamweaver — overnight synthesis engine.
Ingests the day's events, finds patterns and connections during idle time,
and produces a morning brief of insights the user might have missed.
"""
import re
from dataclasses import dataclass
from typing import Any
from nexus.modules.base import NexusModule


@dataclass
class Insight:
    pattern: str
    supporting_events: list[str]
    significance: str


@dataclass
class SynthesisReport:
    insights: list[Insight]
    event_count: int
    themes: list[str]


def _extract_keywords(text: str) -> set[str]:
    stop = {"the", "a", "an", "is", "was", "are", "were", "in", "on", "at", "to", "for",
            "of", "with", "and", "or", "but", "not", "this", "that", "had", "has", "have",
            "about", "from", "by", "be", "been", "being", "they", "them", "their", "it"}
    words = re.findall(r'\b[a-z]{3,}\b', text.lower())
    return {w for w in words if w not in stop}


class DreamweaverModule(NexusModule):
    name = "dreamweaver"
    description = "Overnight synthesis — deep pattern analysis and morning briefs"
    version = "0.1.0"

    def __init__(self):
        self._events: list[str] = []

    def ingest(self, event: str) -> None:
        self._events.append(event)

    def event_count(self) -> int:
        return len(self._events)

    def clear(self) -> None:
        self._events.clear()

    def synthesize(self) -> SynthesisReport:
        if not self._events:
            return SynthesisReport(insights=[], event_count=0, themes=[])

        # Build keyword frequency across events
        keyword_events: dict[str, list[int]] = {}
        for i, event in enumerate(self._events):
            for kw in _extract_keywords(event):
                keyword_events.setdefault(kw, []).append(i)

        # Find themes: keywords appearing in 2+ events
        themes = sorted(
            [(kw, indices) for kw, indices in keyword_events.items() if len(indices) >= 2],
            key=lambda x: len(x[1]),
            reverse=True,
        )

        insights = []
        seen_event_groups: set[frozenset[int]] = set()
        for kw, indices in themes[:5]:
            group = frozenset(indices)
            if group in seen_event_groups:
                continue
            seen_event_groups.add(group)
            supporting = [self._events[i] for i in indices]
            insights.append(Insight(
                pattern=f"Recurring theme '{kw}' across {len(indices)} events",
                supporting_events=supporting,
                significance=f"Multiple signals around '{kw}' suggest this deserves attention.",
            ))

        theme_names = [kw for kw, _ in themes[:10]]
        return SynthesisReport(
            insights=insights,
            event_count=len(self._events),
            themes=theme_names,
        )

    def morning_brief(self) -> str:
        report = self.synthesize()
        if not report.insights:
            return "[Dreamweaver] No patterns detected. Quiet day."
        lines = [f"[Dreamweaver] Morning Brief ({report.event_count} events processed)"]
        if report.themes:
            lines.append(f"  Top themes: {', '.join(report.themes[:5])}")
        lines.append("")
        for i, insight in enumerate(report.insights, 1):
            lines.append(f"  {i}. {insight.pattern}")
            lines.append(f"     {insight.significance}")
            for ev in insight.supporting_events[:3]:
                lines.append(f"       - {ev[:100]}")
        return "\n".join(lines)

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        if not self._events:
            return "[Dreamweaver] No events ingested. Nothing to synthesize."
        report = self.synthesize()
        if not report.insights:
            # Events exist but no cross-event patterns — return a raw event brief
            lines = [f"[Dreamweaver] Morning Brief ({report.event_count} event(s) processed)"]
            lines.append("  No recurring patterns detected. Raw events:")
            for ev in self._events[:5]:
                lines.append(f"    - {ev[:100]}")
            return "\n".join(lines)
        return self.morning_brief()
