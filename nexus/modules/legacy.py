# nexus/modules/legacy.py
"""
Legacy -- knowledge crystallization engine.
Distills months of decisions, outcomes, and behavioral patterns into
structured, exportable knowledge artifacts. Extracts frameworks, playbooks,
and heuristics from actual behavior -- not self-reported preferences.

Data pipeline: subscribes to cortex.response events via Pulse, automatically
recording decisions from deliberation modules (council, ethical_prism).
"""
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from nexus.modules.base import NexusModule


class ArtifactType(Enum):
    FRAMEWORK = "framework"
    PLAYBOOK = "playbook"
    HEURISTIC = "heuristic"


@dataclass
class DecisionRecord:
    domain: str
    decision: str
    outcome: str
    factors: list[str]


@dataclass
class DecisionPattern:
    factor: str
    frequency: int
    positive_rate: float
    domains: list[str]


@dataclass
class KnowledgeArtifact:
    domain: str
    artifact_type: ArtifactType
    patterns: list[DecisionPattern]
    content: str
    decision_count: int


class LegacyModule(NexusModule):
    name = "legacy"
    description = "Knowledge crystallization -- distills decisions into transferable wisdom"
    version = "0.1.0"

    _DECISION_MODULES = frozenset({"council", "ethical_prism", "autonomic"})

    def __init__(self):
        self._decisions: list[DecisionRecord] = []
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
        if module not in self._DECISION_MODULES:
            return
        message = payload.get("message", "")
        response = payload.get("response", "")
        # Extract decision factors from the user's question
        words = [w.strip("?.,!") for w in message.lower().split() if len(w) > 3]
        factors = words[:5] if words else ["unspecified"]
        self.record_decision(
            domain=module,
            decision=message[:200],
            outcome="recorded",
            factors=factors,
        )

    def record_decision(
        self,
        domain: str,
        decision: str,
        outcome: str,
        factors: list[str],
    ) -> None:
        self._decisions.append(DecisionRecord(
            domain=domain,
            decision=decision,
            outcome=outcome,
            factors=factors,
        ))

    def decision_count(self) -> int:
        return len(self._decisions)

    def list_domains(self) -> list[str]:
        return sorted(set(d.domain for d in self._decisions))

    def extract_patterns(self, domain: str) -> list[DecisionPattern]:
        domain_decisions = [d for d in self._decisions if d.domain == domain]
        if not domain_decisions:
            return []

        factor_counts: Counter[str] = Counter()
        factor_positive: Counter[str] = Counter()
        factor_domains: dict[str, set[str]] = {}

        for d in domain_decisions:
            for f in d.factors:
                factor_counts[f] += 1
                if d.outcome == "positive":
                    factor_positive[f] += 1
                factor_domains.setdefault(f, set()).add(d.domain)

        patterns = []
        for factor, count in factor_counts.most_common():
            if count >= 2:
                pos_rate = factor_positive[factor] / count if count > 0 else 0.0
                patterns.append(DecisionPattern(
                    factor=factor,
                    frequency=count,
                    positive_rate=round(pos_rate, 2),
                    domains=sorted(factor_domains.get(factor, set())),
                ))

        return patterns

    def crystallize(self, domain: str) -> KnowledgeArtifact:
        domain_decisions = [d for d in self._decisions if d.domain == domain]
        if not domain_decisions:
            return KnowledgeArtifact(
                domain=domain,
                artifact_type=ArtifactType.FRAMEWORK,
                patterns=[],
                content="",
                decision_count=0,
            )

        patterns = self.extract_patterns(domain)

        lines = [f"Decision Framework: {domain.title()}"]
        lines.append(f"Based on {len(domain_decisions)} decisions.\n")
        if patterns:
            lines.append("Key factors (by frequency):")
            for p in patterns:
                lines.append(
                    f"  - {p.factor}: appeared in {p.frequency} decisions "
                    f"({p.positive_rate:.0%} positive outcome rate)"
                )
        lines.append("")
        lines.append("Decisions analyzed:")
        for d in domain_decisions:
            lines.append(f"  [{d.outcome}] {d.decision}")

        return KnowledgeArtifact(
            domain=domain,
            artifact_type=ArtifactType.FRAMEWORK,
            patterns=patterns,
            content="\n".join(lines),
            decision_count=len(domain_decisions),
        )

    def export_markdown(self, artifact: KnowledgeArtifact) -> str:
        lines = [f"# {artifact.domain.title()} Decision Framework"]
        lines.append(f"\n*Crystallized from {artifact.decision_count} decisions.*\n")
        if artifact.patterns:
            lines.append("## Key Patterns\n")
            for p in artifact.patterns:
                lines.append(
                    f"- **{p.factor}**: {p.frequency}x "
                    f"({p.positive_rate:.0%} positive)"
                )
        lines.append(f"\n## Raw Framework\n\n{artifact.content}")
        return "\n".join(lines)

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        if not self._decisions:
            return "[Legacy] No decisions recorded yet. Record decisions to build knowledge artifacts."

        lower = message.lower()
        domains = self.list_domains()

        target_domain = None
        for d in domains:
            if d in lower:
                target_domain = d
                break

        if target_domain:
            artifact = self.crystallize(target_domain)
            return f"[Legacy] {artifact.content}"

        lines = [f"[Legacy] Knowledge base: {self.decision_count()} decisions across {len(domains)} domains"]
        for d in domains:
            count = sum(1 for dec in self._decisions if dec.domain == d)
            patterns = self.extract_patterns(d)
            lines.append(f"  {d}: {count} decisions, {len(patterns)} patterns extracted")
        return "\n".join(lines)
