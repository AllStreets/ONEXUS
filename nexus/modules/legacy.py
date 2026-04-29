# nexus/modules/legacy.py
"""
Legacy -- knowledge crystallization engine.
Distills months of decisions, outcomes, and behavioral patterns into
structured, exportable knowledge artifacts. Extracts frameworks, playbooks,
and heuristics from actual behavior -- not self-reported preferences.

Data pipeline: subscribes to cortex.response events via Pulse, automatically
recording decisions from deliberation modules (council, ethical_prism).
"""
import re
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

    _POSITIVE_SIGNALS = frozenset({
        "agreed", "approved", "yes", "good", "accepted", "confirmed",
        "correct", "right", "great", "perfect", "done", "success", "ok",
    })
    _NEGATIVE_SIGNALS = frozenset({
        "rejected", "denied", "no", "failed", "bad", "incorrect", "wrong",
        "error", "refused", "blocked", "declined", "invalid", "unable",
    })

    # POS-tag approximation: stop words to exclude from factor extraction
    _FACTOR_STOP = frozenset({
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
        "being", "have", "has", "had", "do", "does", "did", "will", "would",
        "could", "should", "may", "might", "shall", "can", "need", "this",
        "that", "these", "those", "it", "its", "i", "you", "we", "they",
        "what", "which", "who", "how", "when", "where", "why", "just", "also",
    })

    @staticmethod
    def _determine_outcome(response: str) -> str:
        """Return 'positive', 'negative', or 'recorded' based on response text."""
        lower = response.lower()
        tokens = set(re.findall(r"[a-z]+", lower))
        pos_hits = len(tokens & LegacyModule._POSITIVE_SIGNALS)
        neg_hits = len(tokens & LegacyModule._NEGATIVE_SIGNALS)
        if pos_hits > neg_hits:
            return "positive"
        if neg_hits > pos_hits:
            return "negative"
        return "recorded"

    @staticmethod
    def _extract_factors(message: str) -> list[str]:
        """Extract decision-relevant key terms from a message.

        Strategy: prefer noun-like tokens (longer, mixed-case or title-case
        words), de-duplicate, and fall back to any word >4 chars if nothing
        useful is found.
        """
        # Pull out capitalised phrases (likely named entities / proper nouns)
        named = re.findall(r'\b[A-Z][a-zA-Z]{2,}\b', message)
        # Pull out lowercase terms >4 chars that aren't stop words
        lower_terms = [
            w.strip("?.,!;:\"'()[]")
            for w in message.split()
            if len(w.strip("?.,!;:\"'()[]")) > 4
            and w.strip("?.,!;:\"'()[]").lower() not in LegacyModule._FACTOR_STOP
            and w[0].islower()
        ]
        combined: list[str] = []
        seen: set[str] = set()
        for term in named + lower_terms:
            key = term.lower()
            if key not in seen:
                seen.add(key)
                combined.append(term)
        factors = combined[:8] if combined else ["unspecified"]
        return factors

    async def _on_response(self, msg) -> None:
        payload = msg.payload
        module = payload.get("module", "unknown")
        if module not in self._DECISION_MODULES:
            return
        message = payload.get("message", "")
        response = payload.get("response", "")
        outcome = self._determine_outcome(response)
        factors = self._extract_factors(message)
        self.record_decision(
            domain=module,
            decision=message[:200],
            outcome=outcome,
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

    @staticmethod
    def _select_artifact_type(
        patterns: list[DecisionPattern],
        decisions: list[DecisionRecord],
    ) -> ArtifactType:
        """Choose the most appropriate artifact type for the crystallized data.

        Rules:
        - HEURISTIC  — one or more factors with a strong outcome correlation
                       (positive_rate >= 0.75 or <= 0.25, freq >= 2).
        - PLAYBOOK   — sequential/conditional patterns: decisions share similar
                       factor sets and similar outcomes, implying a repeatable
                       decision procedure.
        - FRAMEWORK  — cross-cutting factors that appear in many different
                       outcomes (no single strong correlation), or when neither
                       of the above applies.
        """
        if not patterns:
            return ArtifactType.FRAMEWORK

        # Check for strong factor→outcome correlations → HEURISTIC
        strong = [
            p for p in patterns
            if p.frequency >= 2 and (p.positive_rate >= 0.75 or p.positive_rate <= 0.25)
        ]
        if strong:
            return ArtifactType.HEURISTIC

        # Check for sequential / playbook signal: multiple decisions share
        # overlapping factor sets and converge on the same outcome.
        outcome_groups: dict[str, list[DecisionRecord]] = {}
        for d in decisions:
            outcome_groups.setdefault(d.outcome, []).append(d)
        for outcome, group in outcome_groups.items():
            if len(group) >= 3:
                # Check factor overlap across the group
                factor_sets = [set(d.factors) for d in group]
                common = factor_sets[0]
                for fs in factor_sets[1:]:
                    common &= fs
                if common:
                    return ArtifactType.PLAYBOOK

        return ArtifactType.FRAMEWORK

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
        artifact_type = self._select_artifact_type(patterns, domain_decisions)

        type_label = artifact_type.value.title()
        lines = [f"Decision {type_label}: {domain.title()}"]
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
            artifact_type=artifact_type,
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
