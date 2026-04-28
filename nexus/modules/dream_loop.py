"""
Dream Loop — background pattern discovery during idle time.
Replays recent episodic memories through the LLM to find patterns
and surfaces insights via Pulse notify events.
"""
from typing import Any
from nexus.modules.base import NexusModule
from nexus.kernel.pulse import Message


DREAM_PROMPT = """You are an introspective pattern-discovery engine. Analyze the following recent interactions and identify:
1. Recurring themes or topics
2. Behavioral patterns (timing, preferences, habits)
3. Connections between seemingly unrelated interactions
4. Insights the user might find valuable

Recent interactions:
{memories}

Provide a concise summary of discovered patterns. Be specific and actionable."""


class DreamLoopModule(NexusModule):
    name = "dream_loop"
    description = "Background pattern discovery — replays recent memories to find insights during idle time."
    version = "1.0.0"

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        engram = context["engram"]
        llm = context["llm"]
        chronicle = context["chronicle"]
        pulse = context["pulse"]

        memories = engram.episodic.recall("*", limit=50)
        if not memories:
            return "No recent memories to dream about. Interact more and try again later."

        memory_text = "\n".join(f"- {m['content']}" for m in memories)
        prompt = DREAM_PROMPT.format(memories=memory_text)
        insight = await llm(prompt)

        engram.semantic.store(insight, category="dream_insight")

        chronicle.log("dream_loop", "dream_session", {
            "memories_analyzed": len(memories),
            "insight_preview": insight[:200],
        })

        await pulse.publish(Message(
            topic="notify.dream_loop",
            source="dream_loop",
            payload={"text": f"Dream insight: {insight[:500]}"},
        ))

        return f"Dream session complete.\n\nInsight:\n{insight}"
