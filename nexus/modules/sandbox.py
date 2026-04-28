"""
Temporal Sandbox — fork memory and simulate outcomes before committing.
Runs proposed actions through the LLM against historical patterns
without modifying real state.
"""
from typing import Any
from nexus.modules.base import NexusModule
from nexus.kernel.pulse import Message

SIMULATION_PROMPT = """You are a scenario simulator. Given the proposed action and historical context, project the likely outcome:

Proposed action: {action}

Historical context (similar past events):
{context_data}

Provide:
1. Most likely outcome (with confidence %)
2. Best case scenario
3. Worst case scenario
4. Key risks or uncertainties
5. Recommendation: proceed, modify, or abandon

This is a simulation only — no real actions will be taken."""


class SandboxModule(NexusModule):
    name = "sandbox"
    description = "Fork memory and simulate outcomes — test scenarios without real consequences."
    version = "1.0.0"

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        engram = context["engram"]
        llm = context["llm"]
        chronicle = context["chronicle"]
        pulse = context["pulse"]

        memories = engram.episodic.recall(message, limit=20)
        context_text = "\n".join(f"- {m['content']}" for m in memories) if memories else "No relevant historical data."

        prompt = SIMULATION_PROMPT.format(action=message, context_data=context_text)
        simulation = await llm(prompt)

        # Log but do NOT store in episodic — this is hypothetical
        chronicle.log("sandbox", "simulation", {
            "action": message[:200],
            "result_preview": simulation[:300],
        })

        await pulse.publish(Message(
            topic="sandbox.simulation",
            source="sandbox",
            payload={"text": simulation, "action": message[:200]},
        ))

        return f"Simulation (no real actions taken):\n\n{simulation}"
