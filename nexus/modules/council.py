# nexus/modules/council.py
"""
Council -- multi-agent deliberation orchestrator.
Selects relevant modules, runs structured multi-round debate,
synthesizes a recommendation with preserved dissent.

Inspired by Marvin Minsky's Society of Mind -- intelligence emerges
from the interaction of many simpler agents.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from nexus.modules.base import NexusModule


_DELIBERATION_ROLES: dict[str, dict[str, Any]] = {
    "specter": {
        "role": "adversarial",
        "instruction": "Find weaknesses, hidden assumptions, and failure modes.",
        "triggers": ["decision", "should i", "plan", "strategy", "risk"],
    },
    "sandbox": {
        "role": "temporal",
        "instruction": "Simulate hypothetical outcomes and consequences.",
        "triggers": ["future", "long-term", "timeline", "when", "deadline", "what if"],
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
    version = "0.2.0"

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

        result = await self._synthesize(question, available, transcript, context)

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

    def _response_agreement_score(self, responses: dict[str, str]) -> float:
        """
        Rough proxy for agreement: measures how much unique content overlaps
        across responses via mean pairwise Jaccard similarity on word sets.
        Returns 0.0 (full disagreement) to 1.0 (identical).
        """
        texts = list(responses.values())
        if len(texts) < 2:
            return 1.0
        stopwords = {"the", "a", "an", "is", "it", "to", "of", "and", "or", "in", "that", "this"}
        word_sets = [set(t.lower().split()) - stopwords for t in texts]
        pairs = 0
        total_sim = 0.0
        for i in range(len(word_sets)):
            for j in range(i + 1, len(word_sets)):
                a, b = word_sets[i], word_sets[j]
                union = a | b
                if union:
                    total_sim += len(a & b) / len(union)
                pairs += 1
        return total_sim / pairs if pairs else 1.0

    async def _synthesize(
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

        # Confidence: blend participant coverage with response agreement.
        # Very high agreement is penalised slightly (potential groupthink).
        coverage = min(1.0, len(participants) / self._config["max_modules"])
        agreement = self._response_agreement_score(final_round)
        agreement_weight = agreement if agreement <= 0.9 else 0.9 - (agreement - 0.9) * 0.5
        confidence = round(coverage * 0.6 + agreement_weight * 0.4, 2)

        # Separate adversarial voices from consensus voices
        dissent: list[str] = []
        consensus_parts: list[str] = []
        for name, resp in final_round.items():
            role = _DELIBERATION_ROLES.get(name, {}).get("role", "")
            if role == "adversarial":
                dissent.append(f"[{name}] {resp[:200]}")
            else:
                consensus_parts.append(resp[:200])
        consensus = " ".join(consensus_parts) if consensus_parts else ""

        # LLM synthesis path
        llm = context.get("llm")
        if llm is not None:
            transcript_lines: list[str] = []
            for entry in transcript:
                transcript_lines.append(f"--- Round {entry['round']} ---")
                for mod_name, resp in entry["responses"].items():
                    role_label = _DELIBERATION_ROLES.get(mod_name, {}).get("role", "general")
                    transcript_lines.append(f"[{mod_name} / {role_label}]: {resp[:400]}")
            transcript_text = "\n".join(transcript_lines)

            prompt = (
                "You are synthesizing a multi-agent deliberation council. "
                "Below is the full transcript across all rounds, followed by the original question. "
                "Produce a structured synthesis that integrates every perspective. "
                "Be specific — reference the actual content from the transcript.\n\n"
                f"QUESTION: {question}\n\n"
                f"TRANSCRIPT:\n{transcript_text}\n\n"
                "Respond in this exact format:\n"
                "RECOMMENDATION:\n"
                "<A clear, actionable recommendation integrating the perspectives above>\n\n"
                "KEY UNCERTAINTIES:\n"
                "1. <uncertainty drawn from the deliberation>\n"
                "2. <uncertainty drawn from the deliberation>\n"
                "3. <uncertainty drawn from the deliberation>\n\n"
                "DISSENTING VIEWS:\n"
                "<Summarise significant disagreements or adversarial challenges raised>\n\n"
                "CONSENSUS:\n"
                "<One sentence capturing broad agreement among non-adversarial participants>"
            )

            try:
                raw = await llm(prompt)
            except Exception:
                raw = None

            if raw:
                def _section(text: str, header: str) -> str:
                    m = re.search(
                        rf"{re.escape(header)}\s*\n(.*?)(?=\n[A-Z ]+:\n|\Z)",
                        text,
                        re.DOTALL | re.IGNORECASE,
                    )
                    return m.group(1).strip() if m else ""

                rec = _section(raw, "RECOMMENDATION:") or raw[:400]

                uncertainties_block = _section(raw, "KEY UNCERTAINTIES:")
                uncertainties = [
                    line.lstrip("0123456789.- ").strip()
                    for line in uncertainties_block.splitlines()
                    if line.strip()
                ] or ["See full synthesis above."]

                llm_dissent = _section(raw, "DISSENTING VIEWS:")
                if llm_dissent:
                    dissent = [f"[synthesis] {llm_dissent[:300]}"]

                llm_consensus = _section(raw, "CONSENSUS:")
                if llm_consensus:
                    consensus = llm_consensus

                return DeliberationResult(
                    question=question,
                    recommendation=rec,
                    confidence=confidence,
                    consensus_view=consensus,
                    dissenting_views=dissent,
                    key_uncertainties=uncertainties,
                    participants=participants,
                    rounds=len(transcript),
                    transcript=transcript,
                )

        # Fallback: raw concatenation when no LLM is available or it failed
        recommendation = " | ".join(
            f"{name}: {resp[:150]}" for name, resp in final_round.items()
        )

        return DeliberationResult(
            question=question,
            recommendation=recommendation,
            confidence=confidence,
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
