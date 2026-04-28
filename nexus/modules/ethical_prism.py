"""
Ethical Prism — multi-framework ethical analysis for high-stakes decisions.
Runs a decision through 7 ethical frameworks, then synthesizes where they
agree, conflict, and what the tensions reveal. Does not recommend — presents the landscape.
"""
from typing import Any
from nexus.modules.base import NexusModule
from nexus.kernel.pulse import Message


FRAMEWORKS = [
    {
        "name": "Utilitarian",
        "prompt": "Analyze this decision from a UTILITARIAN perspective. Focus on consequences: what produces the greatest good for the greatest number? Consider all stakeholders and weigh outcomes.",
    },
    {
        "name": "Deontological",
        "prompt": "Analyze this decision from a DEONTOLOGICAL (duty-based) perspective. Is the action itself right or wrong, regardless of consequences? What rules or duties apply?",
    },
    {
        "name": "Virtue Ethics",
        "prompt": "Analyze this decision from a VIRTUE ETHICS perspective. What would a person of good character do? Which virtues are at stake?",
    },
    {
        "name": "Care Ethics",
        "prompt": "Analyze this decision from a CARE ETHICS perspective. Who is affected and what relationships are at stake? Who is vulnerable?",
    },
    {
        "name": "Contractualist",
        "prompt": "Analyze this decision from a CONTRACTUALIST perspective. Could all affected parties reasonably accept this action? Is it fair?",
    },
    {
        "name": "Rights-Based",
        "prompt": "Analyze this decision from a RIGHTS-BASED perspective. Does this violate anyone's fundamental rights — autonomy, privacy, dignity, freedom, property?",
    },
    {
        "name": "Pragmatic Ethics",
        "prompt": "Analyze this decision from a PRAGMATIC ETHICS perspective. What actually works in practice given real-world constraints?",
    },
]


SYNTHESIS_PROMPT = """You are an ethical synthesis engine. You have received analyses of a decision from 7 ethical frameworks. Synthesize them:

Decision: {decision}

Framework analyses:
{analyses}

Provide:
1. CONSENSUS: Where do most frameworks agree?
2. TENSIONS: Where do frameworks conflict?
3. DISSENT: Which framework(s) dissent from the majority, and why?
4. KEY QUESTION: What is the single most important ethical question this decision raises?

Do NOT recommend an action. Present the ethical landscape and let the human decide."""


class EthicalPrismModule(NexusModule):
    name = "ethical_prism"
    description = "Multi-framework ethical analysis — 7 lenses on high-stakes decisions, no moralizing."
    version = "1.0.0"

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        llm = context["llm"]
        engram = context["engram"]
        chronicle = context["chronicle"]
        pulse = context["pulse"]

        # Run each framework analysis
        analyses: list[str] = []
        for framework in FRAMEWORKS:
            prompt = f"{framework['prompt']}\n\nDecision: {message}"
            result = await llm(prompt)
            analyses.append(f"**{framework['name']}:**\n{result}")

        # Synthesize
        all_analyses = "\n\n".join(analyses)
        synthesis_prompt = SYNTHESIS_PROMPT.format(decision=message, analyses=all_analyses)
        synthesis = await llm(synthesis_prompt)

        # Store the full analysis
        full_output = f"Ethical Prism Analysis\n\n{all_analyses}\n\nSynthesis:\n{synthesis}"
        engram.episodic.store(f"Ethical analysis: {full_output[:500]}", source="ethical_prism")

        # Log to Chronicle
        chronicle.log("ethical_prism", "analysis", {
            "decision": message[:200],
            "frameworks_used": len(FRAMEWORKS),
            "synthesis_preview": synthesis[:300],
        })

        # Publish
        await pulse.publish(Message(
            topic="ethical_prism.analysis",
            source="ethical_prism",
            payload={"text": synthesis[:500], "decision": message[:200]},
        ))

        return full_output
