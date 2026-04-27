# nexus/modules/council.py
"""
Council -- multi-agent deliberation orchestrator.
Selects relevant modules, runs structured multi-round debate,
synthesizes a recommendation with preserved dissent.

Inspired by Marvin Minsky's Society of Mind -- intelligence emerges
from the interaction of many simpler agents.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from nexus.modules.base import NexusModule


_DELIBERATION_ROLES: dict[str, dict[str, Any]] = {
    "specter": {
        "role": "adversarial",
        "instruction": "Find weaknesses, hidden assumptions, and failure modes.",
        "triggers": ["decision", "should i", "plan", "strategy", "risk"],
    },
    "chronos": {
        "role": "temporal",
        "instruction": "Model future timelines and consequences.",
        "triggers": ["future", "long-term", "timeline", "when", "deadline"],
    },
    "serendipity": {
        "role": "lateral",
        "instruction": "Surface non-obvious connections and overlooked perspectives.",
        "triggers": ["option", "alternative", "creative", "stuck", "blind spot"],
    },
    "forge": {
        "role": "strategic",
        "instruction": "Analyze trade-offs, incentives, and negotiation angles.",
        "triggers": ["deal", "offer", "trade-off", "cost", "benefit", "negotiate"],
    },
    "atlas": {
        "role": "factual",
        "instruction": "Provide relevant facts and knowledge context.",
        "triggers": ["fact", "know", "data", "evidence", "history"],
    },
    "cipher": {
        "role": "verification",
        "instruction": "Assess source reliability and information conflicts.",
        "triggers": ["trust", "source", "verify", "conflict", "credib"],
    },
    "prism": {
        "role": "synthesis",
        "instruction": "Find cross-domain connections and synthesize perspectives.",
        "triggers": ["connect", "relate", "pattern", "synthesize", "insight"],
    },
}

_DEFAULT_CONFIG = {
    "max_rounds": 3,
    "min_modules": 3,
    "max_modules": 5,
    "always_include": ["specter"],
    "timeout_per_round_seconds": 30,
}


@dataclass
class DeliberationResult:
    question: str
    recommendation: str
    confidence: float
    consensus_view: str
    dissenting_views: list[str]
    key_uncertainties: list[str]
    participants: list[str]
    rounds: int
    transcript: list[dict[str, Any]] = field(default_factory=list)


class CouncilModule(NexusModule):
    name = "council"
    description = "Multi-agent deliberation -- structured debate across modules with synthesized recommendations"
    version = "0.1.0"

    def __init__(self, config: dict[str, Any] | None = None):
        self._config = {**_DEFAULT_CONFIG, **(config or {})}
        self._modules: dict[str, NexusModule] = {}

    def set_modules(self, modules: dict[str, NexusModule]) -> None:
        self._modules = modules

    def select_participants(self, question: str) -> list[str]:
        question_lower = question.lower()
        scores: list[tuple[str, int]] = []
        for mod_name, role_info in _DELIBERATION_ROLES.items():
            score = sum(1 for t in role_info["triggers"] if t in question_lower)
            scores.append((mod_name, score))
        scores.sort(key=lambda x: x[1], reverse=True)

        selected: list[str] = []
        for name in self._config["always_include"]:
            if name not in selected:
                selected.append(name)

        for mod_name, score in scores:
            if mod_name in selected:
                continue
            if score > 0 or len(selected) < self._config["min_modules"]:
                selected.append(mod_name)
            if len(selected) >= self._config["max_modules"]:
                break

        while len(selected) < self._config["min_modules"]:
            for mod_name, _ in scores:
                if mod_name not in selected:
                    selected.append(mod_name)
                    break
            else:
                break
            if len(selected) >= self._config["min_modules"]:
                break

        return selected

    async def deliberate(
        self,
        question: str,
        context: dict[str, Any],
        participants: list[str] | None = None,
    ) -> DeliberationResult:
        if participants is None:
            participants = self.select_participants(question)

        available = [p for p in participants if p in self._modules]
        if not available:
            return DeliberationResult(
                question=question,
                recommendation="No modules available for deliberation.",
                confidence=0.0,
                consensus_view="",
                dissenting_views=[],
                key_uncertainties=["No modules participated."],
                participants=[],
                rounds=0,
                transcript=[],
            )

        transcript: list[dict[str, Any]] = []
        prior_responses: dict[str, str] = {}
        max_rounds = self._config["max_rounds"]

        for round_num in range(1, max_rounds + 1):
            round_record: dict[str, Any] = {"round": round_num, "responses": {}}
            for mod_name in available:
                role_info = _DELIBERATION_ROLES.get(mod_name, {})
                delib_context = {
                    **context,
                    "mode": "council_deliberation",
                    "round": round_num,
                    "role": role_info.get("role", "general"),
                    "instruction": role_info.get("instruction", "Provide your perspective."),
                    "question": question,
                    "prior_responses": dict(prior_responses) if round_num > 1 else {},
                }
                try:
                    response = await self._modules[mod_name].handle(question, delib_context)
                except Exception as exc:
                    response = f"[Error from {mod_name}: {exc}]"
                round_record["responses"][mod_name] = response
                prior_responses[mod_name] = response

            transcript.append(round_record)

            pulse = context.get("pulse")
            if pulse:
                from nexus.kernel.pulse import Message
                await pulse.publish(Message(
                    topic="council.round.complete",
                    source="council",
                    payload={"round": round_num, "participants": available},
                ))

        result = self._synthesize(question, available, transcript, context)

        chronicle = context.get("chronicle")
        if chronicle:
            chronicle.log("council", "deliberation.complete", {
                "question": question[:200],
                "participants": result.participants,
                "confidence": result.confidence,
                "rounds": result.rounds,
            })

        engram = context.get("engram")
        if engram:
            engram.episodic.store(
                f"Council deliberation: {question[:100]} -> {result.recommendation[:200]}",
                source="council",
            )

        return result

    def _synthesize(
        self,
        question: str,
        participants: list[str],
        transcript: list[dict[str, Any]],
        context: dict[str, Any],
    ) -> DeliberationResult:
        if not transcript:
            return DeliberationResult(
                question=question, recommendation="No deliberation occurred.",
                confidence=0.0, consensus_view="", dissenting_views=[],
                key_uncertainties=[], participants=participants, rounds=0,
            )

        final_round = transcript[-1]["responses"]

        recommendation = " | ".join(
            f"{name}: {resp[:150]}" for name, resp in final_round.items()
        )

        dissent = []
        consensus_parts = []
        for name, resp in final_round.items():
            role = _DELIBERATION_ROLES.get(name, {}).get("role", "")
            if role == "adversarial":
                dissent.append(f"[{name}] {resp[:200]}")
            else:
                consensus_parts.append(resp[:200])

        consensus = " ".join(consensus_parts) if consensus_parts else ""
        confidence = min(1.0, len(participants) / self._config["max_modules"])

        return DeliberationResult(
            question=question,
            recommendation=recommendation,
            confidence=round(confidence, 2),
            consensus_view=consensus,
            dissenting_views=dissent,
            key_uncertainties=["LLM synthesis unavailable -- raw responses returned."],
            participants=participants,
            rounds=len(transcript),
            transcript=transcript,
        )

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        result = await self.deliberate(message, context)
        lines = [
            f"[Council] Deliberation complete ({result.rounds} rounds, {len(result.participants)} participants)",
            f"Participants: {', '.join(result.participants)}",
            f"Confidence: {result.confidence}",
            "",
            f"Recommendation: {result.recommendation}",
        ]
        if result.dissenting_views:
            lines.append("")
            lines.append("Dissenting views:")
            for d in result.dissenting_views:
                lines.append(f"  - {d}")
        if result.key_uncertainties:
            lines.append("")
            lines.append("Uncertainties:")
            for u in result.key_uncertainties:
                lines.append(f"  - {u}")
        return "\n".join(lines)
