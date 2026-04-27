# nexus/modules/chronos.py
"""
Chronos — temporal branching and counter-factual modeling.
Models probabilistic future timelines across multiple life domains.
Also handles counter-factuals: 'what if I had done X instead?'
"""
import uuid
from dataclasses import dataclass, field
from typing import Any
from nexus.modules.base import NexusModule

_DEFAULT_DOMAINS = ["career", "finance", "wellbeing"]


@dataclass
class Branch:
    label: str
    probability: float
    outcomes: dict[str, str]
    risk_level: str


@dataclass
class Timeline:
    id: str
    decision: str
    context: str
    branches: list[Branch]
    domains: list[str]


class ChronosModule(NexusModule):
    name = "chronos"
    description = "Temporal branching — probabilistic future modeling and counter-factuals"
    version = "0.1.0"

    def create_timeline(
        self,
        decision: str,
        context: str = "",
        domains: list[str] | None = None,
    ) -> Timeline:
        domains = domains or _DEFAULT_DOMAINS
        timeline_id = uuid.uuid4().hex[:8]

        branch_a = Branch(
            label=f"Proceed: {decision[:60]}",
            probability=0.55,
            outcomes={d: f"Positive trajectory in {d} — change creates new opportunities" for d in domains},
            risk_level="medium",
        )
        branch_b = Branch(
            label=f"Status quo: don't act",
            probability=0.30,
            outcomes={d: f"Stable trajectory in {d} — predictable but constrained growth" for d in domains},
            risk_level="low",
        )
        branch_c = Branch(
            label=f"Proceed but conditions worsen",
            probability=0.15,
            outcomes={d: f"Negative trajectory in {d} — external factors undermine the decision" for d in domains},
            risk_level="high",
        )

        return Timeline(
            id=timeline_id,
            decision=decision,
            context=context,
            branches=[branch_a, branch_b, branch_c],
            domains=domains,
        )

    def counterfactual(
        self,
        actual_decision: str,
        alternative: str,
        outcome_actual: str,
    ) -> str:
        return (
            f"Counterfactual analysis:\n"
            f"  Actual: {actual_decision} -> {outcome_actual}\n"
            f"  Alternative: {alternative}\n"
            f"  Assessment: The alternative path likely would have produced different "
            f"trade-offs rather than a strictly better outcome. The key variable is "
            f"whether the risks you avoided were real or perceived. Given the actual "
            f"outcome ({outcome_actual}), the counterfactual suggests the alternative "
            f"had both higher upside and higher variance."
        )

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        lower = message.lower()
        if "what if" in lower or "counterfactual" in lower or "instead" in lower:
            result = self.counterfactual(
                actual_decision="the path taken",
                alternative=message,
                outcome_actual="current state",
            )
            return f"[Chronos] {result}"

        tl = self.create_timeline(decision=message)
        lines = [f"[Chronos] Timeline for: {tl.decision[:80]}"]
        for b in tl.branches:
            lines.append(f"  Branch: {b.label} (p={b.probability}, risk={b.risk_level})")
            for domain, outcome in b.outcomes.items():
                lines.append(f"    {domain}: {outcome}")
        return "\n".join(lines)
