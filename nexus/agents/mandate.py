"""
Mandate -- compliance checklist and gap analysis agent.
Generates compliance checklists against regulatory frameworks
(GDPR, SOC2, HIPAA, PCI-DSS) and identifies gaps.

Inspired by:
  - OWASP compliance checklists (CC BY-SA 4.0)
  - CIS Benchmarks (CC BY-NC-SA 4.0) -- control frameworks
  - NIST Cybersecurity Framework (public domain)
"""
import re
from dataclasses import dataclass, field
from typing import Any
from nexus.agents.base import AgentModule, TrustTier


@dataclass
class Control:
    id: str
    name: str
    description: str
    status: str  # "met", "partial", "missing", "unknown"
    evidence: str = ""


@dataclass
class GapAnalysis:
    framework: str
    controls_met: int
    controls_partial: int
    controls_missing: int
    controls: list[Control]


# Simplified compliance frameworks
_FRAMEWORKS: dict[str, list[dict[str, str]]] = {
    "gdpr": [
        {"id": "GDPR-1", "name": "Lawful Basis", "desc": "Processing has a lawful basis (consent, contract, legitimate interest)"},
        {"id": "GDPR-2", "name": "Data Minimization", "desc": "Only collect data necessary for the stated purpose"},
        {"id": "GDPR-3", "name": "Right to Access", "desc": "Users can request a copy of their personal data"},
        {"id": "GDPR-4", "name": "Right to Deletion", "desc": "Users can request erasure of personal data"},
        {"id": "GDPR-5", "name": "Data Portability", "desc": "Users can export data in machine-readable format"},
        {"id": "GDPR-6", "name": "Breach Notification", "desc": "72-hour notification requirement for data breaches"},
        {"id": "GDPR-7", "name": "Privacy by Design", "desc": "Data protection built into system design"},
        {"id": "GDPR-8", "name": "DPO Designation", "desc": "Data Protection Officer appointed if required"},
        {"id": "GDPR-9", "name": "International Transfers", "desc": "Adequate safeguards for cross-border data transfers"},
        {"id": "GDPR-10", "name": "Privacy Policy", "desc": "Clear, accessible privacy policy describing data practices"},
    ],
    "soc2": [
        {"id": "SOC2-CC1", "name": "Control Environment", "desc": "Organization demonstrates commitment to integrity and ethical values"},
        {"id": "SOC2-CC2", "name": "Communication", "desc": "Internal communication of security responsibilities"},
        {"id": "SOC2-CC3", "name": "Risk Assessment", "desc": "Risk identification and analysis processes"},
        {"id": "SOC2-CC4", "name": "Monitoring", "desc": "Ongoing monitoring of internal controls"},
        {"id": "SOC2-CC5", "name": "Control Activities", "desc": "Policies and procedures to mitigate risks"},
        {"id": "SOC2-CC6", "name": "Logical Access", "desc": "Authentication, authorization, and access control"},
        {"id": "SOC2-CC7", "name": "System Operations", "desc": "System monitoring, incident detection, and response"},
        {"id": "SOC2-CC8", "name": "Change Management", "desc": "Controlled changes to infrastructure and software"},
        {"id": "SOC2-CC9", "name": "Risk Mitigation", "desc": "Processes to identify and remediate vulnerabilities"},
    ],
    "hipaa": [
        {"id": "HIPAA-1", "name": "Access Controls", "desc": "Unique user IDs, emergency access, auto-logoff, encryption"},
        {"id": "HIPAA-2", "name": "Audit Controls", "desc": "Hardware, software, and process audit mechanisms"},
        {"id": "HIPAA-3", "name": "Integrity Controls", "desc": "Protect ePHI from improper alteration or destruction"},
        {"id": "HIPAA-4", "name": "Transmission Security", "desc": "Encryption for ePHI in transit"},
        {"id": "HIPAA-5", "name": "Breach Notification", "desc": "Notify affected individuals within 60 days"},
        {"id": "HIPAA-6", "name": "Business Associates", "desc": "BAA agreements with all vendors handling PHI"},
        {"id": "HIPAA-7", "name": "Minimum Necessary", "desc": "Limit PHI access to minimum necessary for job function"},
        {"id": "HIPAA-8", "name": "Training", "desc": "Workforce security awareness training"},
    ],
}


class MandateModule(AgentModule):
    name = "mandate"
    description = "Compliance gap analysis -- generates checklists for GDPR, SOC2, HIPAA and identifies gaps"
    version = "0.1.0"

    watch_events: list = []
    coordination_targets: list = ["redline"]

    def __init__(self):
        self._analyses: list[GapAnalysis] = []

    @staticmethod
    def detect_framework(message: str) -> str:
        """Detect which compliance framework is being asked about."""
        msg_lower = message.lower()
        for fw in _FRAMEWORKS:
            if fw in msg_lower:
                return fw
        if any(w in msg_lower for w in ("privacy", "personal data", "consent")):
            return "gdpr"
        if any(w in msg_lower for w in ("health", "medical", "patient", "phi")):
            return "hipaa"
        return "soc2"

    def assess(self, framework: str, practices: str) -> GapAnalysis:
        """Assess compliance against a framework based on described practices."""
        controls_def = _FRAMEWORKS.get(framework, _FRAMEWORKS["soc2"])
        practices_lower = practices.lower()
        controls: list[Control] = []

        for ctrl in controls_def:
            # Simple keyword matching to assess status
            keywords = ctrl["desc"].lower().split()
            matches = sum(1 for kw in keywords if len(kw) > 4 and kw in practices_lower)
            match_ratio = matches / max(len([k for k in keywords if len(k) > 4]), 1)

            if match_ratio > 0.3:
                status = "met"
            elif match_ratio > 0.1:
                status = "partial"
            else:
                status = "missing"

            controls.append(Control(
                id=ctrl["id"], name=ctrl["name"],
                description=ctrl["desc"], status=status,
            ))

        met = sum(1 for c in controls if c.status == "met")
        partial = sum(1 for c in controls if c.status == "partial")
        missing = sum(1 for c in controls if c.status == "missing")

        return GapAnalysis(
            framework=framework.upper(),
            controls_met=met, controls_partial=partial,
            controls_missing=missing, controls=controls,
        )

    def list_frameworks(self) -> list[str]:
        return list(_FRAMEWORKS.keys())

    async def analyze(self, message: str, context: dict[str, Any]) -> str:
        llm = context.get("llm")
        engram = context.get("engram")

        framework = self.detect_framework(message)
        analysis = self.assess(framework, message)
        self._analyses.append(analysis)

        # LLM-enhanced gap analysis
        llm_analysis = ""
        if llm:
            missing = [c for c in analysis.controls if c.status == "missing"]
            if missing:
                prompt = (
                    f"For {framework.upper()} compliance, these controls are missing:\n"
                    + "\n".join(f"- {c.id} {c.name}: {c.description}" for c in missing[:5])
                    + "\n\nFor each missing control, provide:\n"
                    "1. Specific remediation steps\n"
                    "2. Estimated effort (hours/days)\n"
                    "3. Priority (critical/high/medium/low)"
                )
                try:
                    llm_analysis = await llm.complete(prompt)
                except Exception:
                    pass

        if engram:
            try:
                total = len(analysis.controls)
                engram.episodic.store(
                    f"Compliance assessment: {framework.upper()}, "
                    f"{analysis.controls_met}/{total} met, "
                    f"{analysis.controls_missing}/{total} missing",
                    source=self.name,
                )
            except Exception:
                pass

        total = len(analysis.controls)
        pct = (analysis.controls_met / total * 100) if total else 0

        lines = [f"[Mandate] {analysis.framework} Compliance Assessment"]
        lines.append(f"  Score: {analysis.controls_met}/{total} controls met ({pct:.0f}%)")
        lines.append(f"  Met: {analysis.controls_met} | Partial: {analysis.controls_partial} | Missing: {analysis.controls_missing}")

        if analysis.controls_missing > 0:
            lines.append(f"\n  Missing Controls:")
            for c in analysis.controls:
                if c.status == "missing":
                    lines.append(f"    X  {c.id} - {c.name}")
                    lines.append(f"       {c.description}")

        if analysis.controls_partial > 0:
            lines.append(f"\n  Partially Met:")
            for c in analysis.controls:
                if c.status == "partial":
                    lines.append(f"    ~  {c.id} - {c.name}")

        lines.append(f"\n  Controls Met:")
        for c in analysis.controls:
            if c.status == "met":
                lines.append(f"    +  {c.id} - {c.name}")

        if llm_analysis:
            lines.append(f"\n  -- Remediation Plan --")
            lines.append(f"  {llm_analysis[:1000]}")

        return "\n".join(lines)

    async def suggest(self, message: str, context: dict[str, Any]) -> str:
        keywords = ("privacy", "compliance", "regulation", "gdpr", "hipaa", "soc2", "pci", "audit")
        if any(kw in message.lower() for kw in keywords):
            return "Run mandate to assess compliance gaps against GDPR, SOC2, or HIPAA frameworks."
        return ""

    async def monitor(self, event: dict[str, Any], context: dict[str, Any]) -> str | None:
        return None

    async def coordinate(self, analysis_result: str, context: dict[str, Any]) -> str:
        cortex = context.get("cortex")
        if not cortex:
            return ""
        try:
            redline_result = await cortex.route("redline", analysis_result, context)
            if redline_result:
                return f"[redline] {redline_result}"
        except Exception:
            pass
        return ""
