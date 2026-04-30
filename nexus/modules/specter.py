# nexus/modules/specter.py
"""
Specter -- adversarial red-team engine.

Absorbs: adversarial.

Runs structured adversarial analysis on high-stakes decisions:
counter-arguments, failure modes, hidden assumptions, worst-case scenarios.
Auto-activates based on detected stake level.

Now includes red_team_audit() for Chronicle log analysis with real pattern
matching (not just LLM prompting) and stress_test() for generating specific
test scenarios based on detected failure patterns.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

from nexus.modules.base import NexusModule
from nexus.kernel.pulse import Message


# ---------------------------------------------------------------------------
# Stake / domain detection
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Red-team audit dataclasses (from adversarial, made real)
# ---------------------------------------------------------------------------

@dataclass
class AuditFinding:
    category: str  # error_pattern, inconsistency, slow_response, repeated_failure
    severity: str  # critical, high, medium, low
    description: str
    evidence: list[str]
    occurrences: int


@dataclass
class AuditReport:
    entries_analyzed: int
    findings: list[AuditFinding]
    error_rate: float
    most_failing_module: str
    slow_response_count: int
    summary: str


@dataclass
class StressTest:
    name: str
    description: str
    target_module: str
    test_input: str
    expected_failure: str
    severity: str


# ---------------------------------------------------------------------------
# Existing report dataclass
# ---------------------------------------------------------------------------

@dataclass
class RedTeamReport:
    decision: str
    stake_level: StakeLevel
    counter_arguments: list[str]
    failure_modes: list[str]
    hidden_assumptions: list[str]
    worst_case: str
    recommendation: str


# ---------------------------------------------------------------------------
# Domain detection
# ---------------------------------------------------------------------------

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
    text = text.strip()
    segments = re.split(
        r"[;,\n]| because | so | and | but | therefore | since ",
        text, flags=re.IGNORECASE,
    )
    claims = [s.strip() for s in segments if len(s.strip()) > 15]
    return claims[:3] if claims else [text[:120]]


# ===========================================================================
# Specter Module
# ===========================================================================

class SpecterModule(NexusModule):
    name = "specter"
    description = (
        "Adversarial red-team engine -- counter-arguments, failure modes, "
        "hidden assumptions, Chronicle audit, stress testing"
    )
    version = "1.0.0"

    # -------------------------------------------------------------------
    # Stake assessment
    # -------------------------------------------------------------------

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

    # -------------------------------------------------------------------
    # Heuristic analysis (existing)
    # -------------------------------------------------------------------

    def _analyze_heuristic(self, decision: str, context: str = "") -> RedTeamReport:
        full_text = (decision + " " + context).strip()
        stake = self.assess_stakes(full_text)
        domain = _detect_domain(full_text)
        claims = _extract_key_claims(decision)

        counters: list[str] = []
        for claim in claims:
            counters.append(
                f"The premise '{claim[:80]}' may not hold -- "
                f"the opposite position deserves equal scrutiny before committing."
            )
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
                f"The framing '{claims[0][:70]}' assumes this is the right problem to solve -- "
                f"the actual constraint may lie elsewhere."
            )
        assumptions.append(
            "You assume your information set is sufficient; in reality, the decision-relevant "
            "data you lack is likely more important than what you have."
        )

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

    # ===================================================================
    # Red-team audit (absorbed from adversarial, made REAL)
    # ===================================================================

    def red_team_audit(self, chronicle) -> AuditReport:
        """
        Analyze Chronicle logs for failure patterns using real pattern matching.
        No LLM required -- pure algorithmic analysis.
        """
        entries = chronicle.query(limit=500)
        if not entries:
            return AuditReport(
                entries_analyzed=0,
                findings=[],
                error_rate=0.0,
                most_failing_module="none",
                slow_response_count=0,
                summary="No Chronicle entries to audit.",
            )

        findings: list[AuditFinding] = []
        error_entries: list[dict] = []
        module_errors: Counter = Counter()
        module_actions: Counter = Counter()
        slow_responses: list[dict] = []
        action_sequences: list[tuple[str, str]] = []  # (source, action) pairs

        for entry in entries:
            source = entry.get("source", "unknown")
            action = entry.get("action", "")
            payload = entry.get("payload", {})

            module_actions[source] += 1
            action_sequences.append((source, action))

            # Detect errors: look for error-indicating patterns
            payload_str = str(payload).lower()
            action_lower = action.lower()
            is_error = any(kw in payload_str or kw in action_lower for kw in [
                "error", "fail", "exception", "timeout", "crash", "refused",
                "denied", "invalid", "broken", "abort",
            ])
            if is_error:
                error_entries.append(entry)
                module_errors[source] += 1

            # Detect slow responses
            duration = payload.get("duration_ms") or payload.get("duration") or payload.get("elapsed_ms")
            if duration is not None:
                try:
                    dur_val = float(duration)
                    if dur_val > 5000:  # > 5 seconds
                        slow_responses.append(entry)
                except (ValueError, TypeError):
                    pass

        total = len(entries)

        # --- Finding: Repeated errors from same module ---
        for mod, count in module_errors.most_common():
            if count >= 2:
                evidence = []
                for e in error_entries:
                    if e.get("source") == mod:
                        evidence.append(
                            f"[{e.get('action', '?')}] {str(e.get('payload', {}))[:100]}"
                        )
                severity = "critical" if count >= 5 else "high" if count >= 3 else "medium"
                findings.append(AuditFinding(
                    category="repeated_failure",
                    severity=severity,
                    description=f"Module '{mod}' has {count} error(s) in the last {total} entries.",
                    evidence=evidence[:5],
                    occurrences=count,
                ))

        # --- Finding: Slow responses ---
        if slow_responses:
            slow_sources = Counter(e.get("source", "?") for e in slow_responses)
            for mod, count in slow_sources.most_common():
                evidence = []
                for e in slow_responses:
                    if e.get("source") == mod:
                        dur = e.get("payload", {}).get("duration_ms") or e.get("payload", {}).get("duration", "?")
                        evidence.append(f"[{e.get('action', '?')}] {dur}ms")
                findings.append(AuditFinding(
                    category="slow_response",
                    severity="medium" if count < 3 else "high",
                    description=f"Module '{mod}' had {count} slow response(s) (>5s).",
                    evidence=evidence[:5],
                    occurrences=count,
                ))

        # --- Finding: Inconsistent action sequences ---
        # Look for the same source performing contradictory actions close together
        action_pairs: Counter = Counter()
        for i in range(len(action_sequences) - 1):
            src_a, act_a = action_sequences[i]
            src_b, act_b = action_sequences[i + 1]
            if src_a == src_b:
                action_pairs[(src_a, act_a, act_b)] += 1

        for (src, act_a, act_b), count in action_pairs.most_common(5):
            # Flag if the same module alternates between success and error actions
            if count >= 3:
                findings.append(AuditFinding(
                    category="inconsistency",
                    severity="medium",
                    description=(
                        f"Module '{src}' repeatedly transitions '{act_a}' -> '{act_b}' "
                        f"({count} times), suggesting unstable behavior."
                    ),
                    evidence=[f"{act_a} -> {act_b}"] * min(count, 3),
                    occurrences=count,
                ))

        # --- Finding: Module never succeeds ---
        for mod in module_actions:
            if mod in module_errors and module_errors[mod] == module_actions[mod] and module_actions[mod] >= 2:
                findings.append(AuditFinding(
                    category="error_pattern",
                    severity="critical",
                    description=f"Module '{mod}' has a 100% error rate ({module_errors[mod]}/{module_actions[mod]}).",
                    evidence=[f"All {module_actions[mod]} entries are errors"],
                    occurrences=module_errors[mod],
                ))

        # Sort by severity
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        findings.sort(key=lambda f: severity_order.get(f.severity, 99))

        error_rate = len(error_entries) / total if total > 0 else 0.0
        most_failing = module_errors.most_common(1)[0][0] if module_errors else "none"

        summary_parts = [f"Audited {total} Chronicle entries."]
        if findings:
            summary_parts.append(f"Found {len(findings)} issue(s).")
            crits = sum(1 for f in findings if f.severity == "critical")
            if crits:
                summary_parts.append(f"{crits} CRITICAL.")
        else:
            summary_parts.append("No issues detected.")
        summary_parts.append(f"Error rate: {error_rate:.1%}.")

        return AuditReport(
            entries_analyzed=total,
            findings=findings,
            error_rate=round(error_rate, 4),
            most_failing_module=most_failing,
            slow_response_count=len(slow_responses),
            summary=" ".join(summary_parts),
        )

    # ===================================================================
    # Stress test generation (from adversarial concept, made real)
    # ===================================================================

    def stress_test(self, audit: AuditReport) -> list[StressTest]:
        """
        Generate specific stress test scenarios based on audit findings.
        Each test targets a discovered weakness with a concrete test input.
        """
        tests: list[StressTest] = []

        for finding in audit.findings:
            if finding.category == "repeated_failure":
                # Extract the failing action pattern from evidence
                failing_actions = set()
                for ev in finding.evidence:
                    match = re.match(r'\[([^\]]+)\]', ev)
                    if match:
                        failing_actions.add(match.group(1))
                action_desc = ", ".join(failing_actions) if failing_actions else "unknown action"

                tests.append(StressTest(
                    name=f"stress_{finding.category}_{len(tests)}",
                    description=(
                        f"Stress test for {finding.description} -- "
                        f"rapidly invoke the failing action pattern ({action_desc}) "
                        f"to confirm the failure is reproducible."
                    ),
                    target_module=finding.description.split("'")[1] if "'" in finding.description else "unknown",
                    test_input=f"Trigger action: {action_desc}",
                    expected_failure=f"Error in {action_desc}",
                    severity=finding.severity,
                ))

            elif finding.category == "slow_response":
                mod = finding.description.split("'")[1] if "'" in finding.description else "unknown"
                tests.append(StressTest(
                    name=f"stress_latency_{len(tests)}",
                    description=(
                        f"Latency stress test for module '{mod}' -- "
                        f"send a burst of concurrent requests to confirm degradation under load."
                    ),
                    target_module=mod,
                    test_input="Concurrent burst of 10 requests",
                    expected_failure="Response time exceeds 5s threshold",
                    severity=finding.severity,
                ))

            elif finding.category == "inconsistency":
                mod = finding.description.split("'")[1] if "'" in finding.description else "unknown"
                tests.append(StressTest(
                    name=f"stress_consistency_{len(tests)}",
                    description=(
                        f"Consistency test for module '{mod}' -- "
                        f"send identical inputs twice and compare outputs for divergence."
                    ),
                    target_module=mod,
                    test_input="Identical input pair for comparison",
                    expected_failure="Output divergence on identical input",
                    severity=finding.severity,
                ))

            elif finding.category == "error_pattern":
                mod = finding.description.split("'")[1] if "'" in finding.description else "unknown"
                tests.append(StressTest(
                    name=f"stress_total_failure_{len(tests)}",
                    description=(
                        f"Recovery test for module '{mod}' (100% error rate) -- "
                        f"verify module can be reloaded and test basic functionality."
                    ),
                    target_module=mod,
                    test_input="Basic smoke test after module reload",
                    expected_failure="Module fails to respond even after reload",
                    severity="critical",
                ))

        return tests

    # ===================================================================
    # handle()
    # ===================================================================

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        lower = message.lower()

        # Red-team audit mode
        if "audit" in lower or "red.team" in lower or "red-team" in lower or "red team" in lower:
            chronicle = context.get("chronicle")
            if not chronicle:
                return "[Specter] Chronicle unavailable -- cannot run audit."
            audit = self.red_team_audit(chronicle)
            lines = [f"[Specter] Red-Team Audit ({audit.entries_analyzed} entries analyzed)"]
            lines.append(f"  {audit.summary}")
            if audit.findings:
                lines.append("")
                lines.append("Findings:")
                for f in audit.findings:
                    lines.append(f"  [{f.severity.upper()}] {f.category}: {f.description}")
                    for ev in f.evidence[:2]:
                        lines.append(f"    Evidence: {ev}")

                # Auto-generate stress tests
                tests = self.stress_test(audit)
                if tests:
                    lines.append("")
                    lines.append("Generated stress tests:")
                    for t in tests:
                        lines.append(f"  [{t.severity.upper()}] {t.name}: {t.description}")
                        lines.append(f"    Target: {t.target_module}")
            else:
                lines.append("  No issues found.")
            return "\n".join(lines)

        # Standard adversarial analysis
        stake = self.assess_stakes(message)

        llm = context.get("llm")
        if llm is not None:
            prompt = (
                "You are Specter, an adversarial red-team agent. Analyze the following decision or proposal "
                "and produce a structured adversarial report. Your analysis must be specific to the content "
                "provided -- do not produce generic boilerplate.\n\n"
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

        # Heuristic path
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
