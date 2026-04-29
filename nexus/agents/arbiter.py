"""
Arbiter -- AI-powered code review agent.
Reviews pull request diffs and source code for bugs, style issues,
maintainability concerns, and security vulnerabilities.

Inspired by:
  - Nayjest/Gito (MIT) — AI code reviewer with local LLM support, zero-retention
  - Nikita-Filonov/ai-review (MIT) — multi-platform code review with Ollama
  - coderabbitai/ai-pr-reviewer (MIT) — PR summarizer with chat capabilities
"""
import re
from dataclasses import dataclass
from typing import Any
from nexus.agents.base import AgentModule, TrustTier


@dataclass
class ReviewComment:
    line: int
    severity: str  # "critical", "warning", "suggestion", "nitpick"
    category: str
    message: str
    suggestion: str = ""


class ArbiterModule(AgentModule):
    name = "arbiter"
    description = "Code review agent — analyzes diffs and source code for bugs, style issues, and security concerns"
    version = "0.1.0"

    watch_events: list[str] = ["cortex.response"]
    coordination_targets: list[str] = ["vex", "carve"]

    def __init__(self):
        self._review_history: list[dict[str, Any]] = []

    @staticmethod
    def _parse_diff(diff_text: str) -> list[dict[str, Any]]:
        """Parse a unified diff into hunks with line numbers."""
        hunks: list[dict[str, Any]] = []
        current_file = ""
        current_hunk: dict[str, Any] | None = None

        for line in diff_text.split('\n'):
            if line.startswith('diff --git') or line.startswith('---') or line.startswith('+++'):
                if line.startswith('+++ b/'):
                    current_file = line[6:]
                elif line.startswith('+++ '):
                    current_file = line[4:]
                continue

            hunk_match = re.match(r'^@@\s+-(\d+)(?:,\d+)?\s+\+(\d+)(?:,\d+)?\s+@@', line)
            if hunk_match:
                if current_hunk and current_hunk["added_lines"]:
                    hunks.append(current_hunk)
                current_hunk = {
                    "file": current_file,
                    "start_line": int(hunk_match.group(2)),
                    "added_lines": [],
                    "removed_lines": [],
                }
                continue

            if current_hunk is not None:
                if line.startswith('+') and not line.startswith('+++'):
                    current_hunk["added_lines"].append(line[1:])
                elif line.startswith('-') and not line.startswith('---'):
                    current_hunk["removed_lines"].append(line[1:])

        if current_hunk and current_hunk["added_lines"]:
            hunks.append(current_hunk)

        return hunks

    @staticmethod
    def _detect_patterns(code: str) -> list[ReviewComment]:
        """Detect common code issues using pattern matching."""
        comments: list[ReviewComment] = []
        lines = code.split('\n')

        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith('#') or stripped.startswith('//'):
                continue

            # Unused imports (Python)
            if re.match(r'^import\s+\w+\s*$', stripped) or re.match(r'^from\s+\w+\s+import\s+', stripped):
                # Just note it -- real detection needs full AST
                pass

            # Long lines
            if len(line) > 120 and not line.strip().startswith('#'):
                comments.append(ReviewComment(
                    line=i, severity="nitpick", category="Style",
                    message=f"Line is {len(line)} characters (>120)",
                    suggestion="Break into multiple lines for readability",
                ))

            # Magic numbers
            if re.search(r'(?<!=)\s+\b\d{3,}\b(?!\s*[=:])', stripped) and not stripped.startswith(('#', '//')):
                if not any(kw in stripped.lower() for kw in ('port', 'status', 'http', 'year', 'version')):
                    comments.append(ReviewComment(
                        line=i, severity="suggestion", category="Maintainability",
                        message="Magic number detected",
                        suggestion="Extract to a named constant for clarity",
                    ))

            # Empty except
            if re.match(r'except\s*:\s*$', stripped):
                comments.append(ReviewComment(
                    line=i, severity="warning", category="Error Handling",
                    message="Bare except catches all exceptions including SystemExit and KeyboardInterrupt",
                    suggestion="Catch specific exceptions: except ValueError:",
                ))

            # TODO/FIXME/HACK
            if re.search(r'\b(TODO|FIXME|HACK|XXX)\b', stripped):
                comments.append(ReviewComment(
                    line=i, severity="nitpick", category="Code Quality",
                    message="Unresolved code annotation",
                ))

            # Print statements in non-test code
            if re.match(r'print\s*\(', stripped):
                comments.append(ReviewComment(
                    line=i, severity="suggestion", category="Code Quality",
                    message="Print statement found — use logging module in production code",
                    suggestion="Replace with logging.info() or logging.debug()",
                ))

        return comments

    async def analyze(self, message: str, context: dict[str, Any]) -> str:
        llm = context.get("llm")
        engram = context.get("engram")

        # Detect if input is a diff or raw code
        is_diff = message.strip().startswith('diff --git') or '@@' in message[:500]

        # Pattern-based analysis
        if is_diff:
            hunks = self._parse_diff(message)
            code_to_analyze = '\n'.join(
                '\n'.join(h["added_lines"]) for h in hunks
            )
        else:
            code_to_analyze = message
            hunks = []

        pattern_comments = self._detect_patterns(code_to_analyze)

        # LLM deep review
        llm_review = ""
        if llm:
            review_type = "diff" if is_diff else "code"
            prompt = (
                f"You are a senior software engineer performing a {review_type} review. "
                "Focus on:\n"
                "1. Bugs and logic errors\n"
                "2. Security vulnerabilities\n"
                "3. Performance issues\n"
                "4. API misuse\n"
                "5. Race conditions or concurrency issues\n"
                "6. Missing error handling for external calls\n\n"
                "For each issue, state the severity (critical/warning/suggestion), "
                "the specific line or area, and a concrete fix.\n"
                "If the code is well-written, acknowledge that.\n\n"
                f"Code:\n```\n{message[:4000]}\n```"
            )
            try:
                llm_review = await llm.complete(prompt)
            except Exception:
                llm_review = ""

        # Store review record
        self._review_history.append({
            "is_diff": is_diff,
            "hunks": len(hunks),
            "pattern_issues": len(pattern_comments),
            "has_llm_review": bool(llm_review),
        })

        # Store in memory
        if engram:
            try:
                engram.episodic.store(
                    f"Code review: {len(pattern_comments)} pattern issues found, "
                    f"{'diff' if is_diff else 'file'} review",
                    source=self.name,
                )
            except Exception:
                pass

        # Format output
        lines = [f"[Arbiter] Code Review {'(Diff)' if is_diff else '(Source)'}"]

        if is_diff and hunks:
            files = sorted(set(h["file"] for h in hunks if h["file"]))
            lines.append(f"  Files changed: {', '.join(files) if files else 'unknown'}")
            total_added = sum(len(h["added_lines"]) for h in hunks)
            total_removed = sum(len(h["removed_lines"]) for h in hunks)
            lines.append(f"  Lines: +{total_added} / -{total_removed}")

        if pattern_comments:
            lines.append(f"\n  Pattern-Based Findings ({len(pattern_comments)}):")
            for c in pattern_comments:
                icon = {"critical": "!!!", "warning": "! ", "suggestion": "? ", "nitpick": "  "}
                lines.append(f"    {icon.get(c.severity, '  ')} Line {c.line} [{c.severity}] {c.category}")
                lines.append(f"        {c.message}")
                if c.suggestion:
                    lines.append(f"        Fix: {c.suggestion}")
        else:
            lines.append("\n  No pattern-based issues detected.")

        if llm_review:
            lines.append(f"\n  -- AI Deep Review --")
            lines.append(f"  {llm_review[:1500]}")

        return "\n".join(lines)

    async def suggest(self, message: str, context: dict[str, Any]) -> str:
        """Suggest a code review when a diff or code block is present."""
        if message.strip().startswith("diff --git") or "@@" in message[:500]:
            return "Diff detected -- run a code review to catch bugs and style issues before merging."
        code_indicators = ("def ", "class ", "import ", "function ", "=>")
        if any(indicator in message for indicator in code_indicators):
            return "Code detected -- a review can surface bugs, API misuse, and performance issues."
        return ""

    async def monitor(self, event: dict[str, Any], context: dict[str, Any]) -> str | None:
        """Flag cortex responses that contain code or diffs for review."""
        response = event.get("data", {}).get("response", "")
        if "```" in response or "diff --git" in response or any(
            p in response for p in ("def ", "class ", "function ")
        ):
            comments = self._detect_patterns(response)
            if comments:
                return (
                    f"Cortex response contains code with {len(comments)} pattern issue(s) "
                    f"({', '.join(sorted({c.severity for c in comments}))}) -- review suggested."
                )
        return None

    async def coordinate(self, analysis_result: str, context: dict[str, Any]) -> str:
        """Route findings to vex for security depth-check and carve for complexity analysis."""
        parts = [
            "vex: run vulnerability scan on any code identified in this review",
            "carve: measure complexity of flagged functions and suggest refactoring targets",
        ]
        return "\n".join(parts)
