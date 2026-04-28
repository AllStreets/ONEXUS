"""
Provenance Chains — full reasoning tree for every conclusion.
Traces Chronicle logs to build a chain from input through modules to output.
"""
from typing import Any
from nexus.modules.base import NexusModule

CHAIN_PROMPT = """You are a reasoning chain analyst. Given the following system activity logs, reconstruct the reasoning chain that led to the most recent conclusion:

Activity logs:
{logs}

Build a clear tree showing:
1. Original input
2. Which modules processed it and in what order
3. What each module concluded
4. Any challenges or objections raised
5. The final output and how it was derived

Include Chronicle event IDs as references. Format as a readable chain."""


class ProvenanceModule(NexusModule):
    name = "provenance"
    description = "Full reasoning tree for every conclusion — trace how NEXUS reached any answer."
    version = "1.0.0"

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        chronicle = context["chronicle"]
        llm = context["llm"]
        engram = context["engram"]

        entries = chronicle.query(limit=50)
        if not entries:
            return "No reasoning history available. Interact with NEXUS first, then ask to trace the reasoning."

        log_text = "\n".join(
            f"- [{e.get('event_id', '?')}] {e.get('source', '?')}.{e.get('action', '?')}: {e.get('payload', {})}"
            for e in entries
        )

        prompt = CHAIN_PROMPT.format(logs=log_text)
        chain = await llm(prompt)

        engram.episodic.store(f"Provenance chain: {chain[:500]}", source="provenance")

        return f"Reasoning chain:\n\n{chain}"
