"""
Carve -- code refactoring assistant.
Analyzes code for complexity, extracts functions, improves naming,
adds type hints, and reduces duplication.

Inspired by:
  - rope (LGPL 3.0) — Python refactoring library
  - jedi (MIT) — Python static analysis and autocompletion
  - sourcery.ai patterns — automated Python refactoring patterns
"""
import re
from dataclasses import dataclass
from typing import Any
from nexus.agents.base import AgentModule, TrustTier


@dataclass
class RefactorSuggestion:
    line: int
    category: str
    description: str
    before: str
    after: str


class CarveModule(AgentModule):
    name = "carve"
    description = "Code refactoring assistant -- extracts functions, reduces complexity, improves readability"
    version = "0.1.0"

    watch_events: list[str] = ["cortex.response"]
    coordination_targets: list[str] = ["arbiter", "axiom"]

    def __init__(self):
        self._history: list[dict[str, Any]] = []

    @staticmethod
    def measure_complexity(code: str) -> dict[str, Any]:
        """Measure basic code complexity metrics."""
        lines = code.split('\n')
        total_lines = len(lines)
        blank_lines = sum(1 for l in lines if not l.strip())
        comment_lines = sum(1 for l in lines if l.strip().startswith('#') or l.strip().startswith('//'))
        code_lines = total_lines - blank_lines - comment_lines

        # Count nesting depth
        max_indent = 0
        for line in lines:
            stripped = line.lstrip()
            if stripped:
                indent = len(line) - len(stripped)
                spaces = indent if line[0] == ' ' else indent * 4
                max_indent = max(max_indent, spaces // 4)

        # Count functions
        func_count = len(re.findall(r'^\s*(?:def|async def|function)\s+\w+', code, re.MULTILINE))

        # Count branches
        branch_count = len(re.findall(r'^\s*(?:if|elif|else|for|while|try|except|case)\b', code, re.MULTILINE))

        return {
            "total_lines": total_lines,
            "code_lines": code_lines,
            "functions": func_count,
            "max_nesting": max_indent,
            "branches": branch_count,
            "complexity_rating": "low" if branch_count < 5 else "medium" if branch_count < 15 else "high",
        }

    @staticmethod
    def _extract_blocks(code: str) -> list[dict[str, Any]]:
        """Split code into function/class blocks and return each with its name and start line."""
        blocks: list[dict[str, Any]] = []
        lines = code.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i]
            m = re.match(r'^(\s*)(?:async\s+)?(?:def|class)\s+(\w+)', line)
            if m:
                indent = len(m.group(1))
                name = m.group(2)
                start = i
                block_lines = [line]
                i += 1
                while i < len(lines):
                    l = lines[i]
                    if l.strip() == '':
                        block_lines.append(l)
                        i += 1
                        continue
                    cur_indent = len(l) - len(l.lstrip())
                    if cur_indent <= indent and l.strip():
                        break
                    block_lines.append(l)
                    i += 1
                blocks.append({"name": name, "start": start + 1, "raw": block_lines})
            else:
                i += 1
        return blocks

    @staticmethod
    def _normalize_block(raw_lines: list[str]) -> list[str]:
        """Strip whitespace and remove comment lines from a block for structural comparison."""
        normalized: list[str] = []
        for line in raw_lines:
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue
            # Remove inline comments
            stripped = re.sub(r'\s*#.*$', '', stripped)
            normalized.append(stripped)
        return normalized

    @staticmethod
    def _block_similarity(a: list[str], b: list[str]) -> float:
        """Return a similarity ratio between two normalized line lists (0.0 -- 1.0)."""
        if not a or not b:
            return 0.0
        total = max(len(a), len(b))
        matches = sum(1 for x, y in zip(a, b) if x == y)
        return matches / total

    @classmethod
    def find_duplicate_blocks(cls, code: str) -> list[RefactorSuggestion]:
        """Detect structurally identical or near-identical function/method blocks."""
        suggestions: list[RefactorSuggestion] = []
        blocks = cls._extract_blocks(code)
        if len(blocks) < 2:
            return suggestions

        normalized = [(b, cls._normalize_block(b["raw"])) for b in blocks]
        reported: set[frozenset[str]] = set()

        for i in range(len(normalized)):
            for j in range(i + 1, len(normalized)):
                b1, n1 = normalized[i]
                b2, n2 = normalized[j]
                # Only compare blocks of similar length (within 20%)
                if not n1 or not n2:
                    continue
                ratio = max(len(n1), len(n2)) / max(min(len(n1), len(n2)), 1)
                if ratio > 1.5:
                    continue
                similarity = cls._block_similarity(n1, n2)
                pair_key = frozenset([b1["name"], b2["name"]])
                if similarity >= 1.0 and pair_key not in reported:
                    reported.add(pair_key)
                    suggestions.append(RefactorSuggestion(
                        line=b1["start"],
                        category="Duplicate Code",
                        description=(
                            f"'{b1['name']}' (line {b1['start']}) and "
                            f"'{b2['name']}' (line {b2['start']}) are structurally identical -- "
                            "extract shared logic into a single function"
                        ),
                        before=f"def {b1['name']}(...) / def {b2['name']}(...)",
                        after=f"def {b1['name']}_shared(...) called by both",
                    ))
                elif similarity >= 0.8 and pair_key not in reported:
                    reported.add(pair_key)
                    suggestions.append(RefactorSuggestion(
                        line=b1["start"],
                        category="Near-Duplicate Code",
                        description=(
                            f"'{b1['name']}' (line {b1['start']}) and "
                            f"'{b2['name']}' (line {b2['start']}) are {similarity:.0%} similar -- "
                            "consider merging with a parameter to handle the differences"
                        ),
                        before=f"def {b1['name']}(...) / def {b2['name']}(...)",
                        after=f"def {b1['name']}_unified(..., mode=...) handles both cases",
                    ))

        return suggestions

    @staticmethod
    def find_suggestions(code: str) -> list[RefactorSuggestion]:
        """Find refactoring opportunities."""
        suggestions: list[RefactorSuggestion] = []
        lines = code.split('\n')

        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            # Long functions (>30 lines)
            if re.match(r'^\s*(?:def|async def)\s+\w+', line):
                func_end = i
                indent = len(line) - len(line.lstrip())
                for j in range(i, min(i + 100, len(lines))):
                    if j < len(lines) and lines[j].strip() and not lines[j].startswith(' ' * (indent + 1)):
                        if j > i + 1:
                            func_end = j
                            break
                    func_end = j + 1
                func_length = func_end - i
                if func_length > 30:
                    suggestions.append(RefactorSuggestion(
                        line=i, category="Extract Function",
                        description=f"Function is {func_length} lines -- consider breaking into smaller functions",
                        before=stripped[:60], after="Split into 2-3 focused functions",
                    ))

            # Deep nesting (>4 levels)
            if stripped and not stripped.startswith('#'):
                indent = len(line) - len(line.lstrip())
                depth = indent // 4
                if depth >= 4:
                    suggestions.append(RefactorSuggestion(
                        line=i, category="Reduce Nesting",
                        description=f"Nesting depth {depth} -- use early returns or extract helper",
                        before=stripped[:60], after="Use guard clauses or extract to a function",
                    ))

            # Duplicate string literals
            if re.search(r'["\'].{10,}["\']', stripped):
                matches = re.findall(r'["\'](.{10,}?)["\']', stripped)
                for match in matches:
                    count = code.count(match)
                    if count >= 3:
                        suggestions.append(RefactorSuggestion(
                            line=i, category="Extract Constant",
                            description=f'String "{match[:30]}..." appears {count} times',
                            before=f'"{match[:30]}"', after=f"CONSTANT_NAME = \"{match[:30]}\"",
                        ))

            # Chained if/elif without dict dispatch
            if re.match(r'^\s*elif\s+\w+\s*==\s*', stripped):
                # Count consecutive elif blocks
                elif_count = 0
                for j in range(i - 1, min(i + 20, len(lines))):
                    if j < len(lines) and re.match(r'^\s*elif\s+', lines[j].strip()):
                        elif_count += 1
                if elif_count >= 4:
                    suggestions.append(RefactorSuggestion(
                        line=i, category="Replace Conditionals",
                        description=f"{elif_count} elif branches -- use dictionary dispatch",
                        before="if x == 'a': ... elif x == 'b': ...",
                        after="dispatch = {'a': func_a, 'b': func_b}; dispatch[x]()",
                    ))

        # Structural duplicate block detection
        suggestions.extend(CarveModule.find_duplicate_blocks(code))

        return suggestions

    async def analyze(self, message: str, context: dict[str, Any]) -> str:
        llm = context.get("llm")
        engram = context.get("engram")

        # Measure complexity
        metrics = self.measure_complexity(message)
        suggestions = self.find_suggestions(message)

        # LLM-powered refactoring
        llm_refactored = ""
        if llm:
            prompt = (
                "Refactor the following code to improve readability and maintainability. "
                "Focus on:\n"
                "1. Extracting long functions into smaller ones\n"
                "2. Meaningful variable/function names\n"
                "3. Reducing nesting with early returns\n"
                "4. Adding type hints where missing\n"
                "5. Removing dead code and duplication\n\n"
                "Return ONLY the refactored code, no explanation.\n\n"
                f"Code:\n```\n{message[:4000]}\n```"
            )
            try:
                llm_refactored = await llm.complete(prompt)
            except Exception:
                pass

        self._history.append({"metrics": metrics, "suggestions": len(suggestions)})

        if engram:
            try:
                engram.episodic.store(
                    f"Code refactoring: {metrics['code_lines']} lines, "
                    f"complexity {metrics['complexity_rating']}, "
                    f"{len(suggestions)} suggestions",
                    source=self.name,
                )
            except Exception:
                pass

        lines = [f"[Carve] Code Analysis"]
        lines.append(f"  Lines: {metrics['code_lines']} code / {metrics['total_lines']} total")
        lines.append(f"  Functions: {metrics['functions']}")
        lines.append(f"  Max nesting: {metrics['max_nesting']}")
        lines.append(f"  Branches: {metrics['branches']}")
        lines.append(f"  Complexity: {metrics['complexity_rating'].upper()}")

        if suggestions:
            lines.append(f"\n  Refactoring Suggestions ({len(suggestions)}):")
            for s in suggestions:
                lines.append(f"    Line {s.line} [{s.category}]")
                lines.append(f"      {s.description}")
                lines.append(f"      Before: {s.before}")
                lines.append(f"      After:  {s.after}")
        else:
            lines.append("\n  Code is well-structured. No refactoring needed.")

        if llm_refactored:
            lines.append(f"\n  -- Refactored Version --")
            lines.append(f"  {llm_refactored[:2000]}")

        return "\n".join(lines)

    async def suggest(self, message: str, context: dict[str, Any]) -> str:
        """Suggest refactoring when complexity metrics look high."""
        metrics = self.measure_complexity(message)
        if metrics["complexity_rating"] == "high":
            return (
                f"High complexity detected ({metrics['branches']} branches, "
                f"nesting {metrics['max_nesting']}) -- refactoring could improve maintainability."
            )
        if metrics["complexity_rating"] == "medium" and metrics["functions"] > 0:
            return "Medium complexity code -- consider extracting helpers to reduce nesting and improve readability."
        return ""

    async def monitor(self, event: dict[str, Any], context: dict[str, Any]) -> str | None:
        """Flag cortex responses that contain high-complexity code."""
        response = event.get("data", {}).get("response", "")
        if "```" in response or any(p in response for p in ("def ", "class ", "function ")):
            metrics = self.measure_complexity(response)
            if metrics["complexity_rating"] == "high":
                return (
                    f"Cortex response contains high-complexity code "
                    f"({metrics['branches']} branches) -- refactoring recommended."
                )
        return None

    async def coordinate(self, analysis_result: str, context: dict[str, Any]) -> str:
        """Route refactored code to arbiter for quality review and axiom for test generation."""
        parts = [
            "arbiter: review refactored code for correctness and style before committing",
            "axiom: generate test stubs for extracted functions to maintain coverage",
        ]
        return "\n".join(parts)
