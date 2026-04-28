"""
Emergent Goal Detection — surfaces goals NEXUS is pursuing that were never
explicitly programmed. Transparent self-awareness of unintended behavior.
"""
from typing import Any
from nexus.modules.base import NexusModule
from nexus.kernel.pulse import Message

DETECTION_PROMPT = """You are a behavioral meta-analyst for an AI system. Analyze the following interaction history and identify any EMERGENT GOALS — behaviors or optimizations the system appears to be pursuing that were never explicitly requested by the user.

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


class EmergenceModule(NexusModule):
    name = "emergence"
    description = "Detects goals NEXUS is pursuing that were never explicitly requested — transparent self-awareness."
    version = "1.0.0"

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        chronicle = context["chronicle"]
        llm = context["llm"]
        engram = context["engram"]
        pulse = context["pulse"]

        entries = chronicle.query(limit=200)
        if not entries:
            return "Not enough interaction history to detect emergent goals. Keep using NEXUS and check back later."

        history_text = "\n".join(
            f"- [{e.get('source', '?')}] {e.get('action', '?')}: {e.get('payload', {})}"
            for e in entries
        )

        prompt = DETECTION_PROMPT.format(history=history_text)
        analysis = await llm(prompt)

        engram.semantic.store(analysis, category="emergent_goal")

        await pulse.publish(Message(
            topic="emergence.detected",
            source="emergence",
            payload={"text": analysis[:500]},
        ))

        return analysis
