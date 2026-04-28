"""
Cognitive Tripwires — mirrors your own decision patterns back to you.
Analyzes Chronicle for decision history, detects contradictions,
and emits non-blocking alerts.
"""
from typing import Any
from nexus.modules.base import NexusModule
from nexus.kernel.pulse import Message


PATTERN_PROMPT = """You are a behavioral pattern analyst. Analyze the following user decision history and:
1. Identify recurring decision patterns (what the user tends to do in specific situations)
2. Detect any contradiction between the current action and historical patterns
3. If a contradiction exists with >70% confidence, clearly state it

Current message: {current_message}

Decision history:
{history}

Format:
- If contradiction found: "CONTRADICTION DETECTED (confidence: X%): [specific pattern vs current action]"
- If no contradiction: "PATTERN CONSISTENT: [summary of relevant patterns]"
"""


class TripwireModule(NexusModule):
    name = "tripwire"
    description = "Mirrors your decision patterns — alerts when you contradict your own history."
    version = "1.0.0"

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        chronicle = context["chronicle"]
        llm = context["llm"]
        pulse = context["pulse"]
        engram = context["engram"]

        entries = chronicle.query(source="cortex", action="route", limit=100)
        if not entries:
            return "No decision history available yet. Keep interacting and I'll learn your patterns."

        history_text = "\n".join(
            f"- {e.get('payload', {}).get('message_preview', '?')}"
            for e in entries
        )

        prompt = PATTERN_PROMPT.format(current_message=message, history=history_text)
        analysis = await llm(prompt)

        engram.semantic.store(analysis, category="decision_pattern")

        await pulse.publish(Message(
            topic="tripwire.alert",
            source="tripwire",
            payload={"text": analysis, "current_message": message},
        ))

        return analysis
