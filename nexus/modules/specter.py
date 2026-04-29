# nexus/modules/specter.py
"""
Specter — adversarial red-team agent.
Runs structured adversarial analysis on high-stakes decisions:
counter-arguments, failure modes, hidden assumptions, worst-case scenarios.
Auto-activates based on detected stake level.
"""
from dataclasses import dataclass, field
from enum import IntEnum
import re
from typing import Any
from nexus.modules.base import NexusModule

_HIGH_STAKE_MARKERS = [
    "contract", "invest", "hire", "fire", "quit", "resign", "acquire",
    "merge", "lawsuit", "deploy", "production", "publish", "announce",
    "commit", "sign", "negotiate", "$", "salary", "equity", "fund",
    "non-compete", "partnership", "acquisition",
]
_MEDIUM_STAKE_MARKERS = [
    "switch", "migrate", "change", "restructure", "reorganize", "pivot",
    "launch", "release", "proposal", "strategy", "plan", "decision",
    "choose", "select", "evaluate",
]

# Domain detection: map keyword sets to a domain label used in generated text
_DOMAIN_MARKERS: dict[str, list[str]] = {
    "financial": ["invest", "fund", "salary", "equity", "$", "cost", "budget", "revenue", "profit"],
    "hiring/people": ["hire", "fire", "quit", "resign", "team", "employee", "staff", "role"],
    "legal/contractual": ["contract", "sign", "non-compete", "lawsuit", "agreement", "clause", "liability"],
    "technical/infrastructure": ["deploy", "production", "migrate", "architecture", "system", "codebase", "database"],
    "strategic/business": ["acquire", "merge", "acquisition", "partnership", "pivot", "launch", "market"],
    "negotiation": ["negotiate", "offer", "deal", "terms", "counterparty", "concession"],
}


class StakeLevel(IntEnum):
    CRITICAL = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3


@dataclass
class RedTeamReport:
    decision: str
    stake_level: StakeLevel
    counter_arguments: list[str]
    failure_modes: list[str]
    hidden_assumptions: list[str]
    worst_case: str
    recommendation: str


def _detect_domain(text: str) -> str:
    text_lower = text.lower()
    best_domain = "general"
    best_score = 0
    for domain, markers in _DOMAIN_MARKERS.items():
        score = sum(1 for m in markers if m in text_lower)
        if score > best_score:
            best_score = score
            best_domain = domain
    return best_domain


def _extract_key_claims(text: str) -> list[str]:
    """Pull noun phrases and key verbs from the decision text as concrete anchors."""
    # Strip common filler words and extract meaningful segments
    text = text.strip()
    # Split on punctuation boundaries and conjunctions to get sub-claims
    segments = re.split(r"[;,\n]| because | so | and | but | therefore | since ", text, flags=re.IGNORECASE)
    claims = [s.strip() for s in segments if len(s.strip()) > 15]
    # Return at most 3 most substantive claims
    return claims[:3] if claims else [text[:120]]


class SpecterModule(NexusModule):
    name = "specter"
    description = "Adversarial red-team — counter-arguments, failure modes, hidden assumptions"
    version = "0.2.0"

    def assess_stakes(self, text: str) -> StakeLevel:
        text_lower = text.lower()
        high_hits = sum(1 for m in _HIGH_STAKE_MARKERS if m in text_lower)
        med_hits = sum(1 for m in _MEDIUM_STAKE_MARKERS if m in text_lower)
        if high_hits >= 2:
            return StakeLevel.CRITICAL
        if high_hits >= 1:
            return StakeLevel.HIGH
        if med_hits >= 1:
            return StakeLevel.MEDIUM
        return StakeLevel.LOW

    def _analyze_heuristic(self, decision: str, context: str = "") -> RedTeamReport:
        """Rule-based analysis that derives content directly from the input text."""
        full_text = (decision + " " + context).strip()
        stake = self.assess_stakes(full_text)
        domain = _detect_domain(full_text)
        claims = _extract_key_claims(decision)

        # Counter-arguments: challenge each extracted claim directly
        counters: list[str] = []
        for claim in claims:
            counters.append(
                f"The premise '{claim[:80]}' may not hold — "
                f"the opposite position deserves equal scrutiny before committing."
            )
        # Add a domain-specific systemic counter
        domain_counters: dict[str, str] = {
            "financial": "Financial projections embedded in this decision are likely optimistic; "
                         "historical base rates for similar investments suggest worse expected outcomes.",
            "hiring/people": "People decisions carry hidden costs (onboarding, culture fit, severance) "
                             "that are rarely factored into the upfront calculus here.",
            "legal/contractual": "The contractual terms described create obligations that may outlast "
                                 "the conditions that made this decision attractive.",
            "technical/infrastructure": "Technical decisions made under time pressure accumulate debt; "
                                        "the proposed change likely has unexamined downstream dependencies.",
            "strategic/business": "The strategic framing assumes the competitive landscape remains stable, "
                                  "which is rarely true over the execution horizon of this kind of move.",
            "negotiation": "The opening position implied here signals information to the counterparty "
                           "that reduces your future leverage.",
            "general": "The status quo has survival-tested advantages that this decision discards; "
                       "those advantages deserve explicit accounting.",
        }
        counters.append(domain_counters.get(domain, domain_counters["general"]))

        # Failure modes: derived from domain + specifics in the decision
        domain_failures: dict[str, list[str]] = {
            "financial": [
                "Returns fail to materialize within the expected window, creating liquidity pressure.",
                "Market conditions shift before the position can be exited, locking in losses.",
                "A correlated risk not visible in the current model triggers simultaneous drawdown.",
            ],
            "hiring/people": [
                "The candidate or role fit breaks down within 6 months, triggering a costly restart.",
                "The departure or addition changes team dynamics in ways that reduce overall output.",
                "Legal exposure from the employment change (discrimination claims, IP disputes) exceeds projected value.",
            ],
            "legal/contractual": [
                "An ambiguous clause is interpreted against your interests in enforcement.",
                "Circumstances change and the agreement becomes a liability rather than an asset.",
                "The counterparty defaults or breaches, leaving you with an expensive remediation path.",
            ],
            "technical/infrastructure": [
                "A hidden dependency breaks in production, cascading into unplanned downtime.",
                "The migration path proves more complex than estimated, stalling parallel work.",
                "Rollback is unavailable or costly by the time the failure mode is detected.",
            ],
            "strategic/business": [
                "A competitor moves faster during the distraction window created by this initiative.",
                "The assumed customer demand fails to convert, leaving stranded investment.",
                "Internal execution capacity is thinner than planned, causing critical delays.",
            ],
            "negotiation": [
                "The counterparty reads the opening signal and anchors harder than anticipated.",
                "A walkaway threat is called and the deal collapses entirely.",
                "Time pressure forces concessions that undercut the stated floor.",
            ],
            "general": [
                "The timeline proves more aggressive than the complexity warrants.",
                "Key external dependencies fail to materialize on schedule.",
                "The decision triggers second-order effects that were not modeled.",
            ],
        }
        failures = domain_failures.get(domain, domain_failures["general"])

        # Hidden assumptions: surface what the decision text takes for granted
        assumptions: list[str] = []
        text_lower = full_text.lower()
        if any(w in text_lower for w in ["will", "should", "expect", "plan"]):
            assumptions.append(
                "The decision assumes the future will resemble the conditions used to build this plan."
            )
        if any(w in text_lower for w in ["they", "partner", "counterpart", "client", "team", "vendor"]):
            assumptions.append(
                "The decision assumes the other party's incentives and capabilities align with what you need from them."
            )
        if claims:
            assumptions.append(
                f"The framing '{claims[0][:70]}' assumes this is the right problem to solve — "
                f"the actual constraint may lie elsewhere."
            )
        assumptions.append(
            "You assume your information set is sufficient; in reality, the decision-relevant "
            "data you lack is likely more important than what you have."
        )

        # Worst case: compose from domain + specific decision content
        domain_worst: dict[str, str] = {
            "financial": (
                f"Worst case: the financial commitment in '{decision[:60]}...' cannot be recovered. "
                "Capital is locked, conditions worsen, and the cost of unwinding exceeds the original exposure."
            ),
            "hiring/people": (
                f"Worst case: the people change triggered by '{decision[:60]}...' creates legal, "
                "cultural, and operational damage simultaneously, with a recovery timeline measured in years."
            ),
            "legal/contractual": (
                f"Worst case: the agreement implied by '{decision[:60]}...' is enforced against you "
                "under the least favorable interpretation, generating liability that exceeds any benefit."
            ),
            "technical/infrastructure": (
                f"Worst case: the technical change in '{decision[:60]}...' causes a production failure "
                "that is not caught before customer impact, eroding trust and triggering an emergency response."
            ),
            "strategic/business": (
                f"Worst case: '{decision[:60]}...' consumes significant resources, produces no strategic "
                "advantage, and has foreclosed a better alternative that was available at the time of commitment."
            ),
            "negotiation": (
                f"Worst case: the negotiation approach in '{decision[:60]}...' collapses the deal entirely, "
                "damages the counterparty relationship, and leaves you in a worse position than before engagement."
            ),
            "general": (
                f"Worst case: '{decision[:60]}...' backfires entirely. The expected benefit does not arrive, "
                "the fallback position has been foreclosed, and recovery requires more resources than the original commitment."
            ),
        }
        worst = domain_worst.get(domain, domain_worst["general"])

        rec = (
            f"Given {stake.name} stakes in the {domain} domain: before committing, explicitly verify "
            f"the assumption '{assumptions[0][:100]}'. "
            f"What evidence would change this decision?"
        )

        return RedTeamReport(
            decision=decision,
            stake_level=stake,
            counter_arguments=counters,
            failure_modes=failures,
            hidden_assumptions=assumptions,
            worst_case=worst,
            recommendation=rec,
        )

    def analyze(
        self,
        decision: str,
        context: str = "",
        adversarial_angles: list[str] | None = None,
    ) -> RedTeamReport:
        report = self._analyze_heuristic(decision, context)
        if adversarial_angles:
            extra = [
                f"From the angle of {a}: the decision may fail because it has not adequately addressed '{a}' "
                f"in the context of '{decision[:60]}'."
                for a in adversarial_angles
            ]
            report.counter_arguments = extra + report.counter_arguments
        return report

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        stake = self.assess_stakes(message)

        llm = context.get("llm")
        if llm is not None:
            prompt = (
                "You are Specter, an adversarial red-team agent. Analyze the following decision or proposal "
                "and produce a structured adversarial report. Your analysis must be specific to the content "
                "provided — do not produce generic boilerplate.\n\n"
                f"Decision: {message}\n\n"
                "Respond in this exact format:\n"
                "COUNTER-ARGUMENTS:\n"
                "1. <specific counter referencing the decision>\n"
                "2. <specific counter referencing the decision>\n"
                "3. <specific counter referencing the decision>\n\n"
                "FAILURE MODES:\n"
                "1. <failure mode specific to this domain and decision>\n"
                "2. <failure mode specific to this domain and decision>\n"
                "3. <failure mode specific to this domain and decision>\n\n"
                "HIDDEN ASSUMPTIONS:\n"
                "1. <assumption implied by the decision text>\n"
                "2. <assumption implied by the decision text>\n"
                "3. <assumption implied by the decision text>\n\n"
                "WORST CASE:\n"
                "<one paragraph describing the worst realistic outcome specific to this decision>\n\n"
                "RECOMMENDATION:\n"
                "<one sentence recommendation given the stakes>"
            )
            try:
                raw = await llm(prompt)
                return f"[Specter] Red Team Analysis (stakes: {stake.name}, LLM-enhanced)\n\n{raw}"
            except Exception:
                pass  # Fall through to heuristic analysis

        # Heuristic path (no LLM or LLM failed)
        report = self._analyze_heuristic(message)
        lines = [
            f"[Specter] Red Team Analysis (stakes: {report.stake_level.name})",
            "",
            "Counter-arguments:",
        ]
        for i, c in enumerate(report.counter_arguments, 1):
            lines.append(f"  {i}. {c}")
        lines.append("")
        lines.append("Failure modes:")
        for i, f in enumerate(report.failure_modes, 1):
            lines.append(f"  {i}. {f}")
        lines.append("")
        lines.append("Hidden assumptions:")
        for i, a in enumerate(report.hidden_assumptions, 1):
            lines.append(f"  {i}. {a}")
        lines.append("")
        lines.append(f"Worst case: {report.worst_case}")
        lines.append("")
        lines.append(f"Recommendation: {report.recommendation}")
        return "\n".join(lines)
