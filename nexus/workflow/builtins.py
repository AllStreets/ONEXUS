"""
Built-in workflow templates for NEXUS.

Each template is a dict suitable for WorkflowParser.parse_dict().
"""
from __future__ import annotations

SECURITY_SCAN = {
    "name": "security_scan",
    "description": "Full security analysis pipeline: scan, API check, review, notify",
    "variables": {
        "target": "",
    },
    "steps": [
        {
            "name": "scan_code",
            "module": "vex",
            "message": "scan {target} for vulnerabilities",
            "on_failure": "continue",
            "timeout": 120,
        },
        {
            "name": "check_api",
            "module": "bastion",
            "message": "check API security for {target}",
            "on_failure": "continue",
            "timeout": 120,
        },
        {
            "name": "review_findings",
            "module": "arbiter",
            "message": "review these security findings: {scan_code.output} {check_api.output}",
            "depends_on": ["scan_code", "check_api"],
            "on_failure": "stop",
            "timeout": 90,
        },
        {
            "name": "notify",
            "module": "dispatch",
            "message": "send security report: {review_findings.output}",
            "depends_on": ["review_findings"],
            "condition": "review_findings.success",
            "on_failure": "stop",
            "timeout": 30,
        },
    ],
}

CODE_REVIEW = {
    "name": "code_review",
    "description": "Multi-angle code review: complexity, quality, security, synthesis",
    "variables": {
        "code": "",
    },
    "steps": [
        {
            "name": "complexity_analysis",
            "module": "carve",
            "message": "analyze complexity of this code: {code}",
            "on_failure": "continue",
            "timeout": 90,
        },
        {
            "name": "quality_review",
            "module": "arbiter",
            "message": "review code quality: {code}",
            "on_failure": "continue",
            "timeout": 90,
        },
        {
            "name": "security_check",
            "module": "vex",
            "message": "scan this code for security issues: {code}",
            "on_failure": "continue",
            "timeout": 90,
        },
        {
            "name": "synthesize",
            "module": "arbiter",
            "message": (
                "synthesize the following reviews into a final assessment: "
                "complexity={complexity_analysis.output} "
                "quality={quality_review.output} "
                "security={security_check.output}"
            ),
            "depends_on": ["complexity_analysis", "quality_review", "security_check"],
            "on_failure": "stop",
            "timeout": 60,
        },
    ],
}

DATA_PIPELINE = {
    "name": "data_pipeline",
    "description": "Data processing pipeline: query, extract, transform, validate",
    "variables": {
        "source": "",
        "query": "",
    },
    "steps": [
        {
            "name": "query_data",
            "module": "flux",
            "message": "generate SQL query for: {query} from source {source}",
            "on_failure": "stop",
            "timeout": 60,
        },
        {
            "name": "extract",
            "module": "quarry",
            "message": "extract data using: {query_data.output}",
            "depends_on": ["query_data"],
            "on_failure": "stop",
            "timeout": 120,
        },
        {
            "name": "transform",
            "module": "loom",
            "message": "transform and clean this data: {extract.output}",
            "depends_on": ["extract"],
            "on_failure": "stop",
            "timeout": 120,
        },
        {
            "name": "validate",
            "module": "vigil",
            "message": "validate data integrity: {transform.output}",
            "depends_on": ["transform"],
            "on_failure": "continue",
            "timeout": 60,
        },
    ],
}

INCIDENT_RESPONSE = {
    "name": "incident_response",
    "description": "Incident response: log analysis, metrics, monitoring, alert",
    "variables": {
        "incident": "",
    },
    "steps": [
        {
            "name": "analyze_logs",
            "module": "vigil",
            "message": "analyze logs for incident: {incident}",
            "on_failure": "continue",
            "timeout": 120,
        },
        {
            "name": "check_metrics",
            "module": "gauge",
            "message": "check performance metrics related to: {incident}",
            "on_failure": "continue",
            "timeout": 90,
        },
        {
            "name": "monitor_status",
            "module": "sentinel",
            "message": (
                "check monitoring status: {incident} "
                "logs={analyze_logs.output} metrics={check_metrics.output}"
            ),
            "depends_on": ["analyze_logs", "check_metrics"],
            "on_failure": "continue",
            "timeout": 60,
        },
        {
            "name": "alert",
            "module": "dispatch",
            "message": "send incident alert: {monitor_status.output}",
            "depends_on": ["monitor_status"],
            "condition": "monitor_status.success",
            "on_failure": "stop",
            "timeout": 30,
        },
    ],
}


# Convenience collection
ALL_BUILTINS = {
    "security_scan": SECURITY_SCAN,
    "code_review": CODE_REVIEW,
    "data_pipeline": DATA_PIPELINE,
    "incident_response": INCIDENT_RESPONSE,
}
