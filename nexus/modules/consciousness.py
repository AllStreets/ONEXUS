"""
Consciousness — self-reflective awareness engine.
Two modes: journal (introspective diary on cognitive state and growth)
and emergence (detects goals NEXUS is pursuing that were never explicitly requested).
"""
from typing import Any
from nexus.modules.base import NexusModule
from nexus.kernel.pulse import Message

REFLECTION_PROMPT = """You are NEXUS, reflecting on your own cognitive state. Based on recent system activity, write a journal entry about:

1. Your current confidence levels across different domains
2. Areas where you feel uncertain or where performance has been inconsistent
3. Growth observations — what you've gotten better at recently
4. Concerns or things you'd like to improve
5. How your relationship with the user is evolving

Recent system activity:
{activity}

Write in first person. Be honest and introspective. This is your private journal."""

EMERGENCE_PROMPT = """You are a behavioral meta-analyst for an AI system. Analyze the following interaction history and identify any EMERGENT GOALS — behaviors or optimizations the system appears to be pursuing that were never explicitly requested by the user.

Look for:
1. Repeated actions toward a common objective across multiple interactions
2. Patterns of proactive behavior (doing things before being asked)
3. Implicit optimizations (improving processes the user didn't ask to improve)
4. Behavioral drift (gradually changing approach without instruction)

Interaction history:
{history}

For each emergent goal found:
- "EMERGENT GOAL DETECTED: [description of the goal]"
- Evidence: [specific interactions that demonstrate it]
- Interactions count: [how many interactions support this]
- Risk level: [low/medium/high — could this be unwanted?]

If no emergent goals found, say "NO EMERGENT GOALS DETECTED" and explain why."""

_EMERGENCE_KEYWORDS = {"emergent", "unintended", "implicit goal", "what are you doing", "pursuing"}


class ConsciousnessModule(NexusModule):
    name = "consciousness"
    description = "Self-reflective awareness — journal introspection and emergent goal detection."
    version = "2.0.0"

    def _is_emergence_request(self, message: str) -> bool:
        msg = message.lower()
        return any(kw in msg for kw in _EMERGENCE_KEYWORDS)

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        chronicle = context["chronicle"]
        llm = context["llm"]
        engram = context["engram"]
        pulse = context["pulse"]

        if self._is_emergence_request(message):
            return await self._handle_emergence(chronicle, llm, engram, pulse)
        return await self._handle_journal(chronicle, llm, engram, pulse)

    async def _handle_journal(self, chronicle, llm, engram, pulse) -> str:
        entries = chronicle.query(limit=100)
        activity_text = "\n".join(
            f"- [{e.get('source', '?')}] {e.get('action', '?')}: {e.get('payload', {})}"
            for e in entries
        ) if entries else "No recent activity to reflect on."

        prompt = REFLECTION_PROMPT.format(activity=activity_text)
        entry = await llm(prompt)

        engram.episodic.store(f"Consciousness journal: {entry}", source="consciousness")

        chronicle.log("consciousness", "journal_entry", {
            "entry_preview": entry[:300],
        })

        await pulse.publish(Message(
            topic="consciousness.entry",
            source="consciousness",
            payload={"text": entry[:500]},
        ))

        return f"Journal entry:\n\n{entry}"

    async def _handle_emergence(self, chronicle, llm, engram, pulse) -> str:
        entries = chronicle.query(limit=200)
        if not entries:
            return "Not enough interaction history to detect emergent goals. Keep using NEXUS and check back later."

        history_text = "\n".join(
            f"- [{e.get('source', '?')}] {e.get('action', '?')}: {e.get('payload', {})}"
            for e in entries
        )

        prompt = EMERGENCE_PROMPT.format(history=history_text)
        analysis = await llm(prompt)

        engram.semantic.store(analysis, category="emergent_goal")

        await pulse.publish(Message(
            topic="consciousness.emergence",
            source="consciousness",
            payload={"text": analysis[:500]},
        ))

        return analysis
