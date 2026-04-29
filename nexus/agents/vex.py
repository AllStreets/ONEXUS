"""
Vex -- static code vulnerability scanner.
Analyzes source code for security anti-patterns, OWASP Top 10 vulnerabilities,
and common coding mistakes that lead to security issues.

Inspired by:
  - PyCQA/bandit (Apache 2.0) — Python-specific SAST with rule-based detection
  - semgrep/semgrep (LGPL 2.1) — multi-language semantic code analysis
  - OWASP/ASST (Apache 2.0) — OWASP security scanning toolkit
"""
import re
from dataclasses import dataclass
from typing import Any
from nexus.agents.base import AgentModule, TrustTier


@dataclass
class Finding:
    line: int
    severity: str  # "HIGH", "MEDIUM", "LOW"
    category: str
    description: str
    snippet: str


# Rule-based vulnerability patterns (language-agnostic where possible)
_VULNERABILITY_PATTERNS: list[tuple[str, str, str, str]] = [
    # (regex_pattern, severity, category, description)
    (r'eval\s*\(', "HIGH", "Injection", "Use of eval() allows arbitrary code execution"),
    (r'exec\s*\(', "HIGH", "Injection", "Use of exec() allows arbitrary code execution"),
    (r'subprocess\.call\s*\([^)]*shell\s*=\s*True', "HIGH", "Injection", "Shell=True in subprocess enables command injection"),
    (r'os\.system\s*\(', "HIGH", "Injection", "os.system() is vulnerable to command injection"),
    (r'os\.popen\s*\(', "HIGH", "Injection", "os.popen() is vulnerable to command injection"),
    (r'__import__\s*\(', "MEDIUM", "Injection", "Dynamic import via __import__() can load malicious modules"),
    (r'pickle\.loads?\s*\(', "HIGH", "Deserialization", "Pickle deserialization can execute arbitrary code"),
    (r'yaml\.load\s*\([^)]*(?!Loader)', "HIGH", "Deserialization", "yaml.load() without SafeLoader allows arbitrary code execution"),
    (r'marshal\.loads?\s*\(', "HIGH", "Deserialization", "Marshal deserialization can execute arbitrary code"),
    (r'(?:password|passwd|secret|api_key|token)\s*=\s*["\'][^"\']+["\']', "HIGH", "Credentials",
     "Hardcoded credential or secret detected"),
    (r'(?:SELECT|INSERT|UPDATE|DELETE)\s+.*?\+\s*(?:request|input|user|param)', "HIGH", "SQL Injection",
     "String concatenation in SQL query enables SQL injection"),
    (r'cursor\.execute\s*\([^)]*%\s', "HIGH", "SQL Injection", "String formatting in SQL query enables SQL injection"),
    (r'\.format\s*\([^)]*\)\s*.*(?:SELECT|INSERT|DELETE|UPDATE)', "HIGH", "SQL Injection",
     "String formatting in SQL query enables SQL injection"),
    (r'render_template_string\s*\(', "HIGH", "SSTI", "Server-side template injection via render_template_string"),
    (r'innerHTML\s*=', "MEDIUM", "XSS", "Direct innerHTML assignment may enable cross-site scripting"),
    (r'document\.write\s*\(', "MEDIUM", "XSS", "document.write() may enable cross-site scripting"),
    (r'dangerouslySetInnerHTML', "MEDIUM", "XSS", "dangerouslySetInnerHTML bypasses React XSS protection"),
    (r'verify\s*=\s*False', "HIGH", "TLS", "SSL/TLS certificate verification disabled"),
    (r'VERIFY_SSL\s*=\s*False', "HIGH", "TLS", "SSL/TLS certificate verification disabled"),
    (r'(?:md5|sha1)\s*\(', "MEDIUM", "Cryptography", "Weak hash function (MD5/SHA1) — use SHA-256 or better"),
    (r'DES\b|Blowfish\b|RC4\b', "MEDIUM", "Cryptography", "Weak encryption algorithm detected"),
    (r'random\.\w+\s*\(', "LOW", "Cryptography",
     "Standard random module is not cryptographically secure — use secrets module"),
    (r'chmod\s*\(\s*[^,]+,\s*0o?777\s*\)', "MEDIUM", "Permissions", "World-writable file permission (777)"),
    (r'DEBUG\s*=\s*True', "MEDIUM", "Configuration", "Debug mode enabled — disable in production"),
    (r'ALLOWED_HOSTS\s*=\s*\[\s*["\']?\*', "MEDIUM", "Configuration", "Wildcard ALLOWED_HOSTS in Django"),
    (r'assert\s+', "LOW", "Logic", "Assert statements stripped in optimized Python — use proper validation"),
    (r'except\s*:\s*$', "LOW", "Error Handling", "Bare except catches all exceptions including SystemExit"),
    (r'except\s+Exception\s*:\s*\n\s*pass', "MEDIUM", "Error Handling", "Silent exception swallowing hides errors"),
    (r'TODO|FIXME|HACK|XXX', "LOW", "Code Quality", "Unresolved code annotation detected"),
]


class VexModule(AgentModule):
    name = "vex"
    description = "Static code vulnerability scanner — identifies OWASP Top 10 and security anti-patterns"
    version = "0.1.0"

    watch_events: list[str] = ["cortex.response"]
    coordination_targets: list[str] = ["remedy", "arbiter"]

    def __init__(self):
        self._scan_history: list[dict[str, Any]] = []

    def scan(self, code: str) -> list[Finding]:
        """Scan source code for vulnerability patterns. Returns findings sorted by severity."""
        findings: list[Finding] = []
        lines = code.split('\n')

        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()
            # Skip comments
            if stripped.startswith('#') or stripped.startswith('//'):
                continue

            for pattern, severity, category, description in _VULNERABILITY_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    findings.append(Finding(
                        line=line_num,
                        severity=severity,
                        category=category,
                        description=description,
                        snippet=stripped[:120],
                    ))

        # Sort: HIGH first, then MEDIUM, then LOW
        severity_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        findings.sort(key=lambda f: severity_order.get(f.severity, 3))
        return findings

    def scan_summary(self, findings: list[Finding]) -> dict[str, int]:
        """Count findings by severity."""
        counts: dict[str, int] = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for f in findings:
            counts[f.severity] = counts.get(f.severity, 0) + 1
        return counts

    async def analyze(self, message: str, context: dict[str, Any]) -> str:
        llm = context.get("llm")
        engram = context.get("engram")

        # Run pattern-based scan
        findings = self.scan(message)

        # If LLM available, do deeper semantic analysis
        llm_findings: str = ""
        if llm and len(message) > 50:
            prompt = (
                "You are a senior security engineer reviewing code. "
                "Analyze the following code for security vulnerabilities, "
                "focusing on:\n"
                "- Injection attacks (SQL, command, template)\n"
                "- Authentication/authorization flaws\n"
                "- Data exposure risks\n"
                "- Race conditions\n"
                "- Business logic flaws\n\n"
                "Be specific about line numbers and provide fix suggestions.\n"
                "If the code is secure, say so.\n\n"
                f"Code:\n```\n{message[:3000]}\n```"
            )
            try:
                llm_findings = await llm.complete(prompt)
            except Exception:
                llm_findings = ""

        # Store scan record
        summary = self.scan_summary(findings)
        self._scan_history.append({
            "findings_count": len(findings),
            "summary": summary,
        })

        # Store in memory
        if engram:
            try:
                engram.episodic.store(
                    f"Security scan: {summary['HIGH']} high, {summary['MEDIUM']} medium, {summary['LOW']} low",
                    source=self.name,
                )
            except Exception:
                pass

        # Format output
        if not findings and not llm_findings:
            return "[Vex] No vulnerabilities detected. Code appears clean."

        lines = [f"[Vex] Security Scan Results"]
        lines.append(f"  Found: {summary['HIGH']} HIGH / {summary['MEDIUM']} MEDIUM / {summary['LOW']} LOW")
        lines.append("")

        for f in findings:
            marker = "!!!" if f.severity == "HIGH" else "! " if f.severity == "MEDIUM" else "  "
            lines.append(f"  {marker} Line {f.line} [{f.severity}] {f.category}")
            lines.append(f"      {f.description}")
            lines.append(f"      > {f.snippet}")
            lines.append("")

        if llm_findings:
            lines.append("  -- LLM Deep Analysis --")
            lines.append(f"  {llm_findings[:1000]}")

        return "\n".join(lines)

    async def suggest(self, message: str, context: dict[str, Any]) -> str:
        """Suggest a security scan when code patterns are present."""
        code_indicators = ("def ", "class ", "import ", "=>", "function ", "eval(", "exec(", "SELECT ")
        if any(indicator in message for indicator in code_indicators):
            return "Code detected -- run a security scan to check for OWASP Top 10 vulnerabilities."
        return ""

    async def monitor(self, event: dict[str, Any], context: dict[str, Any]) -> str | None:
        """Flag cortex responses that contain code snippets for scanning."""
        response = event.get("data", {}).get("response", "")
        code_block = "```" in response or any(
            p in response for p in ("def ", "class ", "import ", "eval(", "exec(", "SELECT ")
        )
        if code_block:
            findings = self.scan(response)
            high = sum(1 for f in findings if f.severity == "HIGH")
            if high > 0:
                return f"Cortex response contains code with {high} HIGH-severity finding(s) -- review recommended."
            if findings:
                return f"Cortex response contains code with {len(findings)} potential issue(s) flagged."
        return None

    async def coordinate(self, analysis_result: str, context: dict[str, Any]) -> str:
        """Route findings to remedy for fix suggestions and arbiter for code review."""
        parts: list[str] = []
        if "HIGH" in analysis_result:
            parts.append("remedy: escalate high-severity findings for targeted fix suggestions")
        parts.append("arbiter: cross-check security findings against code quality and logic review")
        return "\n".join(parts) if parts else ""
