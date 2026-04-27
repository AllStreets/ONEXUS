# nexus/modules/specter.py
"""
Specter — adversarial red-team agent.
Runs structured adversarial analysis on high-stakes decisions:
counter-arguments, failure modes, hidden assumptions, worst-case scenarios.
Auto-activates based on detected stake level.
"""
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any
from nexus.modules.base import NexusModule

_HIGH_STAKE_MARKERS = [
    "contract", "invest", "hire", "fire", "quit", "resign", "acquire",
    "merge", "lawsuit", "deploy", "production", "publish", "announce",
    "commit", "sign", "negotiate", "$", "salary", "equity", "fund",
    "non-compete", "partnership", "acquisition",
]
_MEDIUM_STAKE_MARKERS = [
    "switch", "migrate", "change", "restructure", "reorganize", "pivot",
    "launch", "release", "proposal", "strategy", "plan", "decision",
    "choose", "select", "evaluate",
]


class StakeLevel(IntEnum):
    CRITICAL = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3


@dataclass
class RedTeamReport:
    decision: str
    stake_level: StakeLevel
    counter_arguments: list[str]
    failure_modes: list[str]
    hidden_assumptions: list[str]
    worst_case: str
    recommendation: str


class SpecterModule(NexusModule):
    name = "specter"
    description = "Adversarial red-team — counter-arguments, failure modes, hidden assumptions"
    version = "0.1.0"

    def assess_stakes(self, text: str) -> StakeLevel:
        text_lower = text.lower()
        high_hits = sum(1 for m in _HIGH_STAKE_MARKERS if m in text_lower)
        med_hits = sum(1 for m in _MEDIUM_STAKE_MARKERS if m in text_lower)
        if high_hits >= 2:
            return StakeLevel.CRITICAL
        if high_hits >= 1:
            return StakeLevel.HIGH
        if med_hits >= 1:
            return StakeLevel.MEDIUM
        return StakeLevel.LOW

    def analyze(
        self,
        decision: str,
        context: str = "",
        adversarial_angles: list[str] | None = None,
    ) -> RedTeamReport:
        stake = self.assess_stakes(decision + " " + context)

        if adversarial_angles:
            counters = [f"From the angle of {a}: this decision may fail because it ignores {a}." for a in adversarial_angles]
        else:
            counters = [
                "The opposite position has merit: the status quo may outperform the change.",
                "This decision optimizes for short-term gain at potential long-term cost.",
                "Selection bias: you may be overweighting evidence that supports this choice.",
            ]

        failures = [
            "The timeline is more aggressive than historical precedent suggests.",
            "Key dependencies are outside your control and may not materialize.",
            "The decision assumes stable conditions that could change rapidly.",
        ]

        assumptions = [
            "You assume the other party's incentives align with yours.",
            "You assume current conditions will persist through execution.",
            "You assume you have complete information — but information gaps are likely.",
        ]

        worst = "Complete failure: the decision backfires, the fallback position is worse than the starting point, and recovery requires more resources than the original investment."

        rec = f"Given {stake.name} stakes: pause and verify your top assumption before committing. What would have to be true for this to fail?"

        return RedTeamReport(
            decision=decision,
            stake_level=stake,
            counter_arguments=counters,
            failure_modes=failures,
            hidden_assumptions=assumptions,
            worst_case=worst,
            recommendation=rec,
        )

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        stake = self.assess_stakes(message)
        if stake == StakeLevel.LOW:
            return "[Specter] Low-stakes decision detected. Red-team analysis not warranted."

        report = self.analyze(decision=message)
        lines = [
            f"[Specter] Red Team Analysis (stakes: {report.stake_level.name})",
            "",
            "Counter-arguments:",
        ]
        for i, c in enumerate(report.counter_arguments, 1):
            lines.append(f"  {i}. {c}")
        lines.append("")
        lines.append("Failure modes:")
        for i, f in enumerate(report.failure_modes, 1):
            lines.append(f"  {i}. {f}")
        lines.append("")
        lines.append("Hidden assumptions:")
        for i, a in enumerate(report.hidden_assumptions, 1):
            lines.append(f"  {i}. {a}")
        lines.append("")
        lines.append(f"Worst case: {report.worst_case}")
        lines.append("")
        lines.append(f"Recommendation: {report.recommendation}")
        return "\n".join(lines)
