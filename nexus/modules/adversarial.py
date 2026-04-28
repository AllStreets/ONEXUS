"""
Adversarial Self-Improvement — system-wide red-teaming.
Analyzes Chronicle logs for failure patterns, generates stress tests,
and files findings as Pulse events.
"""
from typing import Any
from nexus.modules.base import NexusModule
from nexus.kernel.pulse import Message


ANALYSIS_PROMPT = """You are a red-team security analyst for an AI system. Analyze the following recent system activity logs and identify:
1. Failure patterns or repeated errors
2. Inconsistencies between module responses
3. Potential edge cases that weren't handled
4. Slow or degraded responses
5. Trust violations or suspicious patterns

For each finding, rate severity (low/medium/high/critical) and suggest a specific stress test.

Recent activity:
{logs}

Provide findings as a structured report."""


class AdversarialModule(NexusModule):
    name = "adversarial"
    description = "System-wide red-teaming — analyzes logs for failures and generates stress tests."
    version = "1.0.0"

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        chronicle = context["chronicle"]
        llm = context["llm"]
        pulse = context["pulse"]

        entries = chronicle.query(limit=100)
        if not entries:
            return "No recent activity to analyze. Insufficient data for red-teaming."

        log_text = "\n".join(
            f"- [{e.get('source', '?')}] {e.get('action', '?')}: {e.get('payload', {})}"
            for e in entries
        )
        prompt = ANALYSIS_PROMPT.format(logs=log_text)
        report = await llm(prompt)

        chronicle.log("adversarial", "red_team_session", {
            "entries_analyzed": len(entries),
            "report_preview": report[:300],
        })

        await pulse.publish(Message(
            topic="adversarial.report",
            source="adversarial",
            payload={"text": report, "entries_analyzed": len(entries)},
        ))

        return f"Adversarial analysis complete.\n\n{report}"
