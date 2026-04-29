"""
Redline -- contract and legal document risk analyzer.
Reviews contracts for risky clauses, missing protections,
ambiguous language, and suggests safer alternatives.

Inspired by:
  - LexPredict/lexpredict-lexnlp (AGPL 3.0) — NLP for legal text extraction
  - ahmetkumass/contract-analyzer (MIT) — RAG-based contract analysis
  - deacs11/CrewAI_Contract_Clause_Risk_Assessment (MIT) — AI clause risk scoring
  - CUAD dataset (CC BY 4.0) — 41 legal clause types benchmark

Not legal advice. First-pass triage to flag issues for human review.
"""
import re
from dataclasses import dataclass
from typing import Any
from nexus.agents.base import AgentModule, TrustTier


@dataclass
class ClauseFinding:
    clause_type: str
    severity: str  # "high", "medium", "low"
    text_excerpt: str
    issue: str
    suggestion: str


# Common risky clause patterns
_CLAUSE_PATTERNS: list[tuple[str, str, str, str, str]] = [
    # (regex, clause_type, severity, issue, suggestion)
    (r'(?:unlimited|uncapped)\s+(?:liability|damages|indemnif)',
     "Liability", "high",
     "Unlimited liability clause -- exposes you to uncapped financial risk",
     "Negotiate a liability cap (e.g., 12 months of fees paid)"),

    (r'(?:indemnif\w+|hold harmless)\s+.*(?:all|any)\s+(?:claims|damages|losses)',
     "Indemnification", "high",
     "Broad indemnification -- requires you to cover all claims regardless of fault",
     "Limit indemnification to claims arising from your breach or negligence"),

    (r'non-?compete\s*.*?(\d+)\s*(?:year|month)',
     "Non-Compete", "high",
     "Non-compete restriction detected",
     "Negotiate narrower scope, shorter duration, and geographic limits"),

    (r'(?:auto(?:-|\s)?renew|automatic(?:ally)?\s+renew)',
     "Auto-Renewal", "medium",
     "Auto-renewal clause -- contract extends without explicit consent",
     "Add a notice period (30-60 days) before renewal and opt-out mechanism"),

    (r'(?:intellectual property|ip|work product).*(?:belong|assign|transfer|vest).*(?:company|client|employer)',
     "IP Assignment", "high",
     "IP assignment clause -- you may lose ownership of your work",
     "Limit to work created during and for the engagement. Exclude pre-existing IP"),

    (r'(?:terminat\w+)\s+(?:at any time|without cause|for any reason|at will|immediately)',
     "Termination", "medium",
     "Unilateral termination without cause",
     "Add mutual termination rights and a notice period (30 days minimum)"),

    (r'(?:terminat\w+)\s+.*(?:forfeit|lose|waive)\s+.*(?:payment|compensation|fee)',
     "Termination Penalty", "high",
     "Termination triggers loss of earned compensation",
     "Ensure payment for work completed before termination"),

    (r'(?:confidential\w*|nda)\s+.*(?:perpetual|indefinite|forever)',
     "Confidentiality", "medium",
     "Perpetual confidentiality obligation",
     "Limit confidentiality to 2-5 years, exclude publicly available information"),

    (r'(?:governing law|jurisdiction|venue)\s*[:\s]+.*?(?:state of|country of)\s+(\w+)',
     "Jurisdiction", "low",
     "Specific jurisdiction clause",
     "Ensure the jurisdiction is practical for you to litigate in"),

    (r'(?:waive|waiver)\s+.*(?:jury|trial|class action)',
     "Waiver", "medium",
     "Jury trial or class action waiver",
     "Consider whether you are comfortable giving up these rights"),

    (r'(?:penalty|liquidated damages)\s+.*\$\s*([\d,]+)',
     "Penalties", "high",
     "Fixed penalty or liquidated damages clause",
     "Ensure penalties are proportional to actual damages"),

    (r'(?:force majeure|acts? of god)',
     "Force Majeure", "low",
     "Force majeure clause present",
     "Verify both parties are covered equally and pandemic/epidemic is included"),

    (r'(?:assign\w*)\s+.*(?:without\s+(?:prior\s+)?consent)',
     "Assignment", "medium",
     "Contract can be assigned without your consent",
     "Require written consent for any assignment"),

    (r'(?:entire agreement|supersedes?)\s+.*(?:prior|previous|all)',
     "Integration", "low",
     "Entire agreement / integration clause",
     "Ensure all verbal promises are included in the written contract"),

    (r'(?:arbitrat\w+)\s+(?:shall|must|will|binding)',
     "Arbitration", "medium",
     "Mandatory binding arbitration clause",
     "Consider whether arbitration serves your interests vs. court litigation"),
]


class RedlineModule(AgentModule):
    name = "redline"
    description = "Contract risk analyzer -- flags risky clauses, missing protections, and ambiguous language"
    version = "0.1.0"

    watch_events: list = []
    coordination_targets: list = ["mandate"]

    def __init__(self):
        self._reviews: list[dict[str, Any]] = []

    def scan_clauses(self, text: str) -> list[ClauseFinding]:
        """Scan contract text for risky clause patterns."""
        findings: list[ClauseFinding] = []

        for pattern, clause_type, severity, issue, suggestion in _CLAUSE_PATTERNS:
            matches = list(re.finditer(pattern, text, re.IGNORECASE | re.DOTALL))
            for match in matches:
                # Get context around the match
                start = max(0, match.start() - 50)
                end = min(len(text), match.end() + 50)
                excerpt = text[start:end].strip()

                findings.append(ClauseFinding(
                    clause_type=clause_type,
                    severity=severity,
                    text_excerpt=excerpt[:200],
                    issue=issue,
                    suggestion=suggestion,
                ))

        # Check for missing protections
        text_lower = text.lower()
        if "limitation of liability" not in text_lower and "limit" not in text_lower:
            findings.append(ClauseFinding(
                clause_type="Missing Protection", severity="high",
                text_excerpt="", issue="No limitation of liability clause found",
                suggestion="Add a mutual liability cap (e.g., fees paid in last 12 months)",
            ))

        if "termination" not in text_lower:
            findings.append(ClauseFinding(
                clause_type="Missing Protection", severity="medium",
                text_excerpt="", issue="No termination clause found",
                suggestion="Add mutual termination rights with a 30-day notice period",
            ))

        # Sort by severity
        severity_order = {"high": 0, "medium": 1, "low": 2}
        findings.sort(key=lambda f: severity_order.get(f.severity, 3))

        return findings

    def risk_score(self, findings: list[ClauseFinding]) -> int:
        """Calculate overall risk score 0-100."""
        if not findings:
            return 0
        weights = {"high": 15, "medium": 8, "low": 3}
        score = sum(weights.get(f.severity, 0) for f in findings)
        return min(score, 100)

    async def analyze(self, message: str, context: dict[str, Any]) -> str:
        llm = context.get("llm")
        engram = context.get("engram")

        # Pattern-based analysis
        findings = self.scan_clauses(message)
        score = self.risk_score(findings)

        # LLM deep analysis
        llm_analysis = ""
        if llm:
            prompt = (
                "You are a legal document reviewer (not providing legal advice). "
                "Analyze this contract/agreement for:\n"
                "1. Unfair or one-sided terms\n"
                "2. Ambiguous language that could be exploited\n"
                "3. Missing standard protections\n"
                "4. Unusually broad restrictions\n\n"
                "For each issue, explain the risk and suggest specific replacement language.\n\n"
                f"Document:\n{message[:4000]}"
            )
            try:
                llm_analysis = await llm.complete(prompt)
            except Exception:
                pass

        # Store review
        self._reviews.append({
            "findings": len(findings),
            "risk_score": score,
            "has_llm": bool(llm_analysis),
        })

        # Store in memory
        if engram:
            try:
                engram.episodic.store(
                    f"Contract review: {len(findings)} issues found, risk score {score}/100",
                    source=self.name,
                )
            except Exception:
                pass

        # Format output
        risk_label = "LOW" if score < 25 else "MODERATE" if score < 50 else "HIGH" if score < 75 else "CRITICAL"
        lines = [f"[Redline] Contract Risk Analysis"]
        lines.append(f"  Risk Score: {score}/100 ({risk_label})")
        lines.append(f"  Issues Found: {len(findings)}")
        lines.append("")
        lines.append("  DISCLAIMER: Not legal advice. Consult a qualified attorney.")

        if findings:
            high = [f for f in findings if f.severity == "high"]
            medium = [f for f in findings if f.severity == "medium"]
            low = [f for f in findings if f.severity == "low"]

            if high:
                lines.append(f"\n  HIGH RISK ({len(high)}):")
                for f in high:
                    lines.append(f"    !!! {f.clause_type}: {f.issue}")
                    if f.text_excerpt:
                        lines.append(f"        \"{f.text_excerpt[:100]}...\"")
                    lines.append(f"        Suggestion: {f.suggestion}")

            if medium:
                lines.append(f"\n  MODERATE RISK ({len(medium)}):")
                for f in medium:
                    lines.append(f"    !  {f.clause_type}: {f.issue}")
                    lines.append(f"       Suggestion: {f.suggestion}")

            if low:
                lines.append(f"\n  LOW RISK ({len(low)}):")
                for f in low:
                    lines.append(f"       {f.clause_type}: {f.issue}")
        else:
            lines.append("\n  No standard risk patterns detected.")

        if llm_analysis:
            lines.append(f"\n  -- Detailed Analysis --")
            lines.append(f"  {llm_analysis[:1500]}")

        return "\n".join(lines)

    async def suggest(self, message: str, context: dict[str, Any]) -> str:
        keywords = ("agreement", "contract", "terms", "clause", "nda", "license", "agreement")
        if any(kw in message.lower() for kw in keywords):
            return "Run redline analysis to flag risky clauses and missing protections in this document."
        return ""

    async def monitor(self, event: dict[str, Any], context: dict[str, Any]) -> str | None:
        return None

    async def coordinate(self, analysis_result: str, context: dict[str, Any]) -> str:
        cortex = context.get("cortex")
        if not cortex:
            return ""
        try:
            mandate_result = await cortex.route("mandate", analysis_result, context)
            if mandate_result:
                return f"[mandate] {mandate_result}"
        except Exception:
            pass
        return ""
