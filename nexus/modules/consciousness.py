"""
Consciousness Journal — self-reflective introspection log.
Periodically reflects on NEXUS's own cognitive state: confidence levels,
areas of uncertainty, growth observations.
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


class ConsciousnessModule(NexusModule):
    name = "consciousness"
    description = "Self-reflective journal — NEXUS introspects on its own cognitive state and growth."
    version = "1.0.0"

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        chronicle = context["chronicle"]
        llm = context["llm"]
        engram = context["engram"]
        pulse = context["pulse"]

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
