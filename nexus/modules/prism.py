"""
Prism — cross-domain synthesis engine.
Collects observations from multiple domains, finds non-obvious connections
through shared tags and context overlap, and surfaces synthesized insights.
"""
from dataclasses import dataclass, field
from typing import Any
from nexus.modules.base import NexusModule


@dataclass
class Observation:
    domain: str
    content: str
    tags: list[str]


@dataclass
class Insight:
    summary: str
    domains: list[str]
    tags: list[str]
    observations: list[Observation]
    connection_strength: float


class PrismModule(NexusModule):
    name = "prism"
    description = "Cross-domain synthesis — finds non-obvious connections across information sources"
    version = "0.1.0"

    def __init__(self):
        self._observations: list[Observation] = []

    def add_observation(self, domain: str, content: str, tags: list[str]) -> None:
        self._observations.append(Observation(domain=domain, content=content, tags=tags))

    def list_observations(self) -> list[Observation]:
        return list(self._observations)

    def clear_observations(self) -> None:
        self._observations.clear()

    def synthesize(self) -> list[Insight]:
        """Find cross-domain connections through shared tags."""
        if len(self._observations) < 2:
            return []

        # Build tag -> observation index
        tag_index: dict[str, list[int]] = {}
        for i, obs in enumerate(self._observations):
            for tag in obs.tags:
                tag_index.setdefault(tag.lower(), []).append(i)

        # Find groups of observations connected by shared tags
        seen_groups: set[frozenset[int]] = set()
        insights: list[Insight] = []

        for tag, indices in tag_index.items():
            if len(indices) < 2:
                continue
            # Only consider cross-domain connections
            domains = {self._observations[i].domain for i in indices}
            if len(domains) < 2:
                continue

            group_key = frozenset(indices)
            if group_key in seen_groups:
                continue
            seen_groups.add(group_key)

            connected_obs = [self._observations[i] for i in indices]
            shared_tags = set.intersection(
                *(set(o.tags) for o in connected_obs)
            )
            all_tags = set()
            for o in connected_obs:
                all_tags.update(o.tags)

            # Connection strength: ratio of shared tags to total unique tags
            strength = len(shared_tags) / len(all_tags) if all_tags else 0.0

            summary_parts = [f"[{o.domain}] {o.content}" for o in connected_obs]
            summary = "Connection found: " + " + ".join(summary_parts)

            insights.append(Insight(
                summary=summary,
                domains=sorted(domains),
                tags=sorted(shared_tags),
                observations=connected_obs,
                connection_strength=round(strength, 3),
            ))

        insights.sort(key=lambda x: x.connection_strength, reverse=True)
        return insights

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        if not self._observations:
            return "[Prism] No observations collected. Feed data from Oracle, Sentry, or other sources first."

        insights = self.synthesize()
        if not insights:
            return "[Prism] No cross-domain insights found. Observations exist but have no shared context."

        lines = [f"[Prism] {len(insights)} cross-domain insight(s) found:"]
        for i, ins in enumerate(insights, 1):
            lines.append(f"  {i}. Domains: {', '.join(ins.domains)}")
            lines.append(f"     Shared tags: {', '.join(ins.tags)}")
            lines.append(f"     Strength: {ins.connection_strength}")
            for obs in ins.observations:
                lines.append(f"       [{obs.domain}] {obs.content}")
        return "\n".join(lines)
