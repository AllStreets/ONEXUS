"""
Remedy -- error diagnosis and stack trace analyzer.
Parses error messages and stack traces, identifies root causes,
explains the problem in plain English, and suggests specific fixes.

Inspired by:
  - davoodwadi/llm_exceptions (MIT) — LLM-powered stack trace explanation
  - d4v3y0rk/llm_catcher (MIT) — instant diagnostics for Python exceptions
  - FloridSleeves/LLMDebugger (MIT) — step-by-step runtime verification
  - VishApp/multiagent-debugger (MIT) — multi-agent error analysis
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from nexus.agents.base import AgentModule, TrustTier


@dataclass
class ErrorDiagnosis:
    error_type: str
    error_message: str
    file_path: str
    line_number: int
    root_cause: str
    suggestion: str


# Common Python error patterns and their typical causes
_ERROR_PATTERNS: dict[str, dict[str, str]] = {
    "ModuleNotFoundError": {
        "cause": "Module is not installed or not in the Python path",
        "fix": "Install with: pip install {module}. Check virtual environment activation.",
    },
    "ImportError": {
        "cause": "Module exists but the specific name cannot be imported",
        "fix": "Check for typos in the import name. Verify the module version supports this import.",
    },
    "AttributeError": {
        "cause": "Object does not have the requested attribute or method",
        "fix": "Check the object type with type(obj). The method may be misspelled or not exist in this version.",
    },
    "TypeError": {
        "cause": "Operation applied to an object of incorrect type",
        "fix": "Check argument types. Common: passing None where a value is expected, or wrong number of arguments.",
    },
    "ValueError": {
        "cause": "Function received an argument with the right type but inappropriate value",
        "fix": "Validate input before passing. Check for empty strings, out-of-range numbers, or malformed data.",
    },
    "KeyError": {
        "cause": "Dictionary key does not exist",
        "fix": "Use dict.get(key, default) instead of dict[key]. Check that the key spelling matches.",
    },
    "IndexError": {
        "cause": "List or sequence index is out of range",
        "fix": "Check sequence length before accessing. Use try/except or bounds checking.",
    },
    "FileNotFoundError": {
        "cause": "File or directory does not exist at the specified path",
        "fix": "Verify path with os.path.exists(). Check working directory with os.getcwd().",
    },
    "PermissionError": {
        "cause": "Insufficient permissions to access the file or resource",
        "fix": "Check file permissions. Run with appropriate user or adjust file ownership.",
    },
    "ConnectionError": {
        "cause": "Network connection failed -- server unreachable or refusing connections",
        "fix": "Check network connectivity. Verify host/port. Add retry logic with exponential backoff.",
    },
    "TimeoutError": {
        "cause": "Operation exceeded time limit",
        "fix": "Increase timeout. Check if the remote service is responsive. Add async/concurrent handling.",
    },
    "RecursionError": {
        "cause": "Maximum recursion depth exceeded -- infinite recursion or deep call stack",
        "fix": "Check base case in recursive function. Consider iterative approach.",
    },
    "MemoryError": {
        "cause": "Operation ran out of available memory",
        "fix": "Process data in chunks. Use generators instead of lists. Reduce data size.",
    },
    "ZeroDivisionError": {
        "cause": "Division or modulo operation with zero as divisor",
        "fix": "Add a check: if divisor != 0. Consider what the correct behavior should be for zero.",
    },
    "UnicodeDecodeError": {
        "cause": "Cannot decode bytes to string with the specified encoding",
        "fix": "Try encoding='utf-8' or encoding='latin-1'. Use errors='replace' to handle gracefully.",
    },
    "sqlite3.OperationalError": {
        "cause": "SQLite operation failed -- table missing, locked database, or syntax error",
        "fix": "Run migrations/init_db(). Check for concurrent writes. Verify SQL syntax.",
    },
    "asyncio.TimeoutError": {
        "cause": "Async operation timed out",
        "fix": "Increase async timeout. Use asyncio.wait_for() with appropriate timeout value.",
    },
}


class RemedyModule(AgentModule):
    name = "remedy"
    description = "Error diagnosis agent -- analyzes stack traces, explains root causes, and suggests fixes"
    version = "0.1.0"

    watch_events: list[str] = ["cortex.response"]
    coordination_targets: list[str] = ["vex"]

    def __init__(self):
        self._diagnoses: list[ErrorDiagnosis] = []

    @staticmethod
    def parse_traceback(text: str) -> dict[str, Any]:
        """Parse a Python traceback into structured data."""
        result: dict[str, Any] = {
            "error_type": "",
            "error_message": "",
            "frames": [],
            "file_path": "",
            "line_number": 0,
        }

        # Extract the final error line
        error_match = re.search(
            r'^(\w+(?:\.\w+)*(?:Error|Exception|Warning))\s*:\s*(.+?)$',
            text, re.MULTILINE
        )
        if error_match:
            result["error_type"] = error_match.group(1)
            result["error_message"] = error_match.group(2).strip()

        # Extract frame locations
        frames = re.findall(
            r'File\s+"([^"]+)",\s+line\s+(\d+)(?:,\s+in\s+(\w+))?',
            text
        )
        result["frames"] = [
            {"file": f, "line": int(l), "function": fn or "<module>"}
            for f, l, fn in frames
        ]

        if result["frames"]:
            last = result["frames"][-1]
            result["file_path"] = last["file"]
            result["line_number"] = last["line"]

        return result

    def diagnose(self, parsed: dict[str, Any]) -> ErrorDiagnosis:
        """Generate a diagnosis from parsed traceback data."""
        error_type = parsed["error_type"]
        error_message = parsed["error_message"]

        # Look up known pattern
        pattern = _ERROR_PATTERNS.get(error_type, {})
        root_cause = pattern.get("cause", f"A {error_type} occurred")
        suggestion = pattern.get("fix", "Check the error message for details")

        # Enhance with specific context from the error message
        if error_type == "ModuleNotFoundError":
            mod_match = re.search(r"No module named '(\w+)'", error_message)
            if mod_match:
                suggestion = suggestion.format(module=mod_match.group(1))
            else:
                suggestion = suggestion.format(module="<module_name>")

        return ErrorDiagnosis(
            error_type=error_type,
            error_message=error_message,
            file_path=parsed.get("file_path", ""),
            line_number=parsed.get("line_number", 0),
            root_cause=root_cause,
            suggestion=suggestion,
        )

    async def analyze(self, message: str, context: dict[str, Any]) -> str:
        llm = context.get("llm")
        engram = context.get("engram")

        # Parse the traceback
        parsed = self.parse_traceback(message)

        if not parsed["error_type"]:
            # Try LLM for non-standard error formats
            if llm:
                prompt = (
                    "Analyze this error message or log output. Identify:\n"
                    "1. The specific error type\n"
                    "2. Root cause explanation in plain English\n"
                    "3. Step-by-step fix instructions\n"
                    "4. How to prevent this in the future\n\n"
                    f"Error:\n{message[:3000]}"
                )
                try:
                    return f"[Remedy] {await llm.complete(prompt)}"
                except Exception:
                    pass
            return "[Remedy] Could not parse error. Paste a full stack trace or error message."

        # Generate diagnosis
        diagnosis = self.diagnose(parsed)
        self._diagnoses.append(diagnosis)

        # LLM-enhanced analysis
        llm_analysis = ""
        if llm:
            prompt = (
                f"A Python program raised {diagnosis.error_type}: {diagnosis.error_message}\n"
                f"File: {diagnosis.file_path}, Line: {diagnosis.line_number}\n\n"
                "Explain:\n"
                "1. What exactly caused this error\n"
                "2. The most likely fix (with code)\n"
                "3. How to prevent it in the future\n\n"
                f"Full traceback:\n{message[:2000]}"
            )
            try:
                llm_analysis = await llm.complete(prompt)
            except Exception:
                pass

        # Store in memory
        if engram:
            try:
                engram.episodic.store(
                    f"Error diagnosed: {diagnosis.error_type}: {diagnosis.error_message[:100]}",
                    source=self.name,
                )
            except Exception:
                pass

        # Format output
        lines = [f"[Remedy] Error Diagnosis"]
        lines.append(f"  Type: {diagnosis.error_type}")
        lines.append(f"  Message: {diagnosis.error_message}")

        if diagnosis.file_path:
            lines.append(f"  Location: {diagnosis.file_path}:{diagnosis.line_number}")

        if parsed["frames"]:
            lines.append(f"\n  Call Stack ({len(parsed['frames'])} frames):")
            for frame in parsed["frames"][-5:]:  # Show last 5 frames
                lines.append(f"    {frame['file']}:{frame['line']} in {frame['function']}")

        lines.append(f"\n  Root Cause:")
        lines.append(f"    {diagnosis.root_cause}")

        lines.append(f"\n  Suggested Fix:")
        lines.append(f"    {diagnosis.suggestion}")

        if llm_analysis:
            lines.append(f"\n  -- Detailed Analysis --")
            lines.append(f"  {llm_analysis[:1000]}")

        return "\n".join(lines)

    async def suggest(self, message: str, context: dict[str, Any]) -> str:
        """Suggest error diagnosis when error-like patterns are present."""
        error_indicators = ("Traceback", "Error:", "Exception:", "raise ", "errno", "exit code")
        if any(indicator in message for indicator in error_indicators):
            return "Error pattern detected -- diagnose the stack trace to identify root cause and fix."
        return ""

    async def monitor(self, event: dict[str, Any], context: dict[str, Any]) -> str | None:
        """Flag cortex responses that contain error or traceback content."""
        response = event.get("data", {}).get("response", "")
        parsed = self.parse_traceback(response)
        if parsed["error_type"]:
            return (
                f"Cortex response references {parsed['error_type']} "
                f"at line {parsed['line_number']} -- diagnosis available."
            )
        if any(p in response for p in ("Traceback", "Error:", "Exception:", "exit code 1")):
            return "Cortex response contains error output -- run remedy for root cause analysis."
        return None

    async def coordinate(self, analysis_result: str, context: dict[str, Any]) -> str:
        """Route error patterns to vex to check if the error indicates a security vulnerability."""
        return "vex: scan error context for security implications (injection, deserialization, path traversal)"
