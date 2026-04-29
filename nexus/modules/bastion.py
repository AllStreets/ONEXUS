"""
Bastion -- API security scanner and endpoint analyzer.
Analyzes API specs (OpenAPI/Swagger) for security vulnerabilities,
misconfigurations, and missing protections.

Inspired by:
  - flipkart-incubator/Astra (Apache 2.0) -- REST API security testing
  - scanapi/scanapi (MIT) -- automated API integration testing
  - cerberauth/vulnapi (MIT) -- API security vulnerability scanner
"""
import re
from dataclasses import dataclass
from typing import Any
from nexus.modules.base import NexusModule


@dataclass
class APIFinding:
    endpoint: str
    method: str
    category: str
    severity: str  # "critical", "high", "medium", "low", "info"
    issue: str
    recommendation: str


# Security check patterns for API specs
_AUTH_KEYWORDS = ("auth", "bearer", "token", "api_key", "apikey", "oauth", "jwt")
_SENSITIVE_PATHS = ("admin", "internal", "debug", "test", "config", "env", "secret")
_SENSITIVE_PARAMS = ("password", "secret", "token", "key", "credential", "ssn", "credit_card")


class BastionModule(NexusModule):
    name = "bastion"
    description = "API security scanner -- analyzes endpoints, specs, and configs for vulnerabilities"
    version = "0.1.0"

    def __init__(self):
        self._scans: list[dict[str, Any]] = []

    @staticmethod
    def parse_endpoints(text: str) -> list[dict[str, str]]:
        """Parse API endpoint definitions from text."""
        endpoints: list[dict[str, str]] = []

        # Match "GET /path", "POST /api/v1/users", etc.
        for match in re.finditer(
            r'\b(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+(/\S+)',
            text, re.IGNORECASE,
        ):
            endpoints.append({"method": match.group(1).upper(), "path": match.group(2)})

        # Match OpenAPI-style paths: "/users": { "get": ...
        for match in re.finditer(
            r'["\'](/[^"\']+)["\']\s*:\s*\{[^}]*["\']?(get|post|put|patch|delete)["\']?',
            text, re.IGNORECASE,
        ):
            endpoints.append({"method": match.group(2).upper(), "path": match.group(1)})

        return endpoints

    @staticmethod
    def check_endpoint_security(endpoint: dict[str, str]) -> list[APIFinding]:
        """Check a single endpoint for security issues."""
        findings: list[APIFinding] = []
        path = endpoint["path"].lower()
        method = endpoint["method"]

        # Check for sensitive paths exposed
        for sensitive in _SENSITIVE_PATHS:
            if sensitive in path:
                findings.append(APIFinding(
                    endpoint=endpoint["path"], method=method,
                    category="Exposure",
                    severity="high",
                    issue=f"Sensitive path '{sensitive}' exposed",
                    recommendation=f"Restrict access to {endpoint['path']} or remove from public API",
                ))

        # Check for ID enumeration risk
        if re.search(r'/\d+$|/\{id\}|/\{.*_id\}', path):
            if method in ("GET", "PUT", "DELETE"):
                findings.append(APIFinding(
                    endpoint=endpoint["path"], method=method,
                    category="BOLA",
                    severity="medium",
                    issue="Potential Broken Object Level Authorization (BOLA)",
                    recommendation="Implement object-level authorization checks",
                ))

        # Check for mass assignment risk on write endpoints
        if method in ("POST", "PUT", "PATCH"):
            findings.append(APIFinding(
                endpoint=endpoint["path"], method=method,
                category="Mass Assignment",
                severity="low",
                issue="Write endpoint may be vulnerable to mass assignment",
                recommendation="Whitelist allowed fields in request body validation",
            ))

        # Check for sensitive data in path params
        for param in _SENSITIVE_PARAMS:
            if param in path:
                findings.append(APIFinding(
                    endpoint=endpoint["path"], method=method,
                    category="Data Exposure",
                    severity="high",
                    issue=f"Sensitive parameter '{param}' in URL path",
                    recommendation="Move sensitive data to request body or headers",
                ))

        return findings

    @staticmethod
    def check_spec_security(text: str) -> list[APIFinding]:
        """Check API specification text for security issues."""
        findings: list[APIFinding] = []
        text_lower = text.lower()

        # Check for missing authentication
        if not any(kw in text_lower for kw in _AUTH_KEYWORDS):
            findings.append(APIFinding(
                endpoint="*", method="*",
                category="Authentication",
                severity="critical",
                issue="No authentication mechanism detected in API spec",
                recommendation="Implement OAuth2, JWT, or API key authentication",
            ))

        # Check for HTTP (not HTTPS)
        if re.search(r'http://[^s]', text):
            findings.append(APIFinding(
                endpoint="*", method="*",
                category="Transport",
                severity="high",
                issue="API uses HTTP instead of HTTPS",
                recommendation="Enforce HTTPS for all API endpoints",
            ))

        # Check for missing rate limiting
        if "rate" not in text_lower and "throttl" not in text_lower and "limit" not in text_lower:
            findings.append(APIFinding(
                endpoint="*", method="*",
                category="Rate Limiting",
                severity="medium",
                issue="No rate limiting mentioned in API spec",
                recommendation="Implement rate limiting to prevent abuse",
            ))

        # Check for missing CORS config
        if "cors" not in text_lower and "access-control" not in text_lower:
            findings.append(APIFinding(
                endpoint="*", method="*",
                category="CORS",
                severity="medium",
                issue="No CORS configuration detected",
                recommendation="Configure CORS headers to restrict cross-origin access",
            ))

        # Check for missing input validation
        if "validat" not in text_lower and "schema" not in text_lower:
            findings.append(APIFinding(
                endpoint="*", method="*",
                category="Validation",
                severity="medium",
                issue="No input validation or schema references found",
                recommendation="Define request/response schemas with validation rules",
            ))

        return findings

    @staticmethod
    def severity_score(findings: list[APIFinding]) -> int:
        """Calculate a total severity score."""
        weights = {"critical": 20, "high": 10, "medium": 5, "low": 2, "info": 1}
        return sum(weights.get(f.severity, 0) for f in findings)

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        llm = context.get("llm")
        engram = context.get("engram")

        endpoints = self.parse_endpoints(message)
        all_findings: list[APIFinding] = []

        # Check each endpoint
        for ep in endpoints:
            all_findings.extend(self.check_endpoint_security(ep))

        # Check overall spec
        all_findings.extend(self.check_spec_security(message))

        # Sort by severity
        sev_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        all_findings.sort(key=lambda f: sev_order.get(f.severity, 5))

        score = self.severity_score(all_findings)
        self._scans.append({"endpoints": len(endpoints), "findings": len(all_findings), "score": score})

        # LLM deep analysis
        llm_analysis = ""
        if llm and all_findings:
            critical = [f for f in all_findings if f.severity in ("critical", "high")]
            if critical:
                prompt = (
                    "Analyze these API security findings and provide remediation priority:\n\n"
                    + "\n".join(f"- [{f.severity.upper()}] {f.endpoint} {f.method}: {f.issue}" for f in critical[:8])
                    + "\n\nProvide: 1) Attack scenarios 2) Prioritized remediation 3) Quick wins"
                )
                try:
                    llm_analysis = await llm.complete(prompt)
                except Exception:
                    pass

        if engram:
            try:
                engram.episodic.store(
                    f"API scan: {len(endpoints)} endpoints, {len(all_findings)} findings, score {score}",
                    source=self.name,
                )
            except Exception:
                pass

        lines = [f"[Bastion] API Security Scan"]
        lines.append(f"  Endpoints: {len(endpoints)}")
        lines.append(f"  Findings: {len(all_findings)}")
        lines.append(f"  Risk Score: {score}")

        if all_findings:
            by_sev = {}
            for f in all_findings:
                by_sev.setdefault(f.severity, []).append(f)

            for sev in ("critical", "high", "medium", "low", "info"):
                items = by_sev.get(sev, [])
                if items:
                    lines.append(f"\n  [{sev.upper()}] ({len(items)})")
                    for f in items:
                        lines.append(f"    {f.method} {f.endpoint}: {f.issue}")
                        lines.append(f"      -> {f.recommendation}")
        else:
            lines.append("\n  No security issues detected.")

        if llm_analysis:
            lines.append(f"\n  -- Deep Analysis --\n  {llm_analysis[:1000]}")

        return "\n".join(lines)
