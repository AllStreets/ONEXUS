"""
Rune -- regex pattern builder and explainer.
Constructs, explains, and tests regular expressions from natural
language descriptions or example strings.

Inspired by:
  - bruntonspall/regex-builder (Apache 2.0) -- fluent regex builder
  - MaLeLabTs/RegexGenerator (MIT) -- example-based regex generation
  - aloisdg/awesome-regex -- curated regex resources collection
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from nexus.agents.base import AgentModule, TrustTier


@dataclass
class RegexResult:
    pattern: str
    explanation: str
    test_matches: list[str]
    test_non_matches: list[str]
    flags: str


# Common regex building blocks
_COMMON_PATTERNS: dict[str, str] = {
    "email": r'[\w.+-]+@[\w-]+\.[\w.]+',
    "url": r'https?://[^\s<>"\']+',
    "ip": r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b',
    "ipv4": r'\b(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b',
    "phone": r'\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
    "date": r'\d{4}[-/]\d{2}[-/]\d{2}',
    "time": r'\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?',
    "hex_color": r'#[0-9a-fA-F]{3,8}',
    "uuid": r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
    "mac_address": r'(?:[0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}',
    "zip_code": r'\b\d{5}(?:-\d{4})?\b',
    "ssn": r'\b\d{3}-\d{2}-\d{4}\b',
    "credit_card": r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',
    "slug": r'[a-z0-9]+(?:-[a-z0-9]+)*',
    "semver": r'\bv?\d+\.\d+\.\d+(?:-[\w.]+)?(?:\+[\w.]+)?\b',
    "hashtag": r'#\w+',
    "mention": r'@\w+',
}

# Regex element explanations
_ELEMENT_EXPLANATIONS: dict[str, str] = {
    r'\d': "digit (0-9)",
    r'\w': "word character (letter, digit, underscore)",
    r'\s': "whitespace",
    r'\b': "word boundary",
    r'.': "any character",
    r'^': "start of string",
    r'$': "end of string",
    r'+': "one or more",
    r'*': "zero or more",
    r'?': "zero or one (optional)",
}


class RuneModule(AgentModule):
    name = "rune"
    description = "Regex builder -- constructs, explains, and tests regular expressions"
    version = "0.1.0"

    watch_events: list[str] = []
    coordination_targets: list[str] = []

    def __init__(self):
        self._history: list[RegexResult] = []

    @staticmethod
    def lookup_common(name: str) -> str | None:
        """Look up a common pattern by name."""
        name_lower = name.lower().replace(' ', '_').replace('-', '_')
        return _COMMON_PATTERNS.get(name_lower)

    @staticmethod
    def explain_pattern(pattern: str) -> str:
        """Generate a human-readable explanation of a regex pattern."""
        explanation: list[str] = []
        i = 0
        while i < len(pattern):
            c = pattern[i]

            # Character classes
            if c == '[':
                end = pattern.index(']', i + 1) if ']' in pattern[i + 1:] else len(pattern)
                char_class = pattern[i:end + 1]
                if char_class.startswith('[^'):
                    explanation.append(f"not any of {char_class[2:-1]}")
                else:
                    explanation.append(f"any of {char_class[1:-1]}")
                i = end + 1
                continue

            # Escape sequences
            if c == '\\' and i + 1 < len(pattern):
                seq = pattern[i:i + 2]
                if seq in _ELEMENT_EXPLANATIONS:
                    explanation.append(_ELEMENT_EXPLANATIONS[seq])
                else:
                    explanation.append(f"literal '{pattern[i + 1]}'")
                i += 2
                continue

            # Groups
            if c == '(':
                if pattern[i:i + 3] == '(?:':
                    explanation.append("non-capturing group")
                elif pattern[i:i + 4] == '(?P<':
                    name_end = pattern.index('>', i + 4)
                    explanation.append(f"named group '{pattern[i + 4:name_end]}'")
                    i = name_end + 1
                    continue
                elif pattern[i:i + 3] == '(?=':
                    explanation.append("lookahead")
                elif pattern[i:i + 3] == '(?!':
                    explanation.append("negative lookahead")
                else:
                    explanation.append("capturing group")
                i += 1
                continue

            # Quantifiers
            if c == '{':
                end = pattern.index('}', i + 1) if '}' in pattern[i + 1:] else len(pattern)
                quant = pattern[i:end + 1]
                if ',' in quant:
                    parts = quant[1:-1].split(',')
                    if parts[1].strip():
                        explanation.append(f"{parts[0]} to {parts[1].strip()} times")
                    else:
                        explanation.append(f"{parts[0]} or more times")
                else:
                    explanation.append(f"exactly {quant[1:-1]} times")
                i = end + 1
                continue

            # Simple elements
            if c in _ELEMENT_EXPLANATIONS:
                explanation.append(_ELEMENT_EXPLANATIONS[c])
            elif c == '|':
                explanation.append("OR")
            elif c == ')':
                explanation.append("end group")
            else:
                explanation.append(f"literal '{c}'")

            i += 1

        return " -> ".join(explanation) if explanation else "empty pattern"

    @staticmethod
    def test_pattern(pattern: str, test_strings: list[str]) -> dict[str, bool]:
        """Test a pattern against multiple strings."""
        results: dict[str, bool] = {}
        try:
            compiled = re.compile(pattern)
            for s in test_strings:
                results[s] = bool(compiled.search(s))
        except re.error:
            for s in test_strings:
                results[s] = False
        return results

    @staticmethod
    def validate_pattern(pattern: str) -> tuple[bool, str]:
        """Validate a regex pattern."""
        try:
            re.compile(pattern)
            return True, "Valid pattern"
        except re.error as e:
            return False, f"Invalid pattern: {e}"

    @staticmethod
    def detect_intent(message: str) -> str:
        """Detect what the user wants to do with regex."""
        msg_lower = message.lower()
        if any(w in msg_lower for w in ("explain", "what does", "break down", "meaning")):
            return "explain"
        if any(w in msg_lower for w in ("test", "match", "try", "check against")):
            return "test"
        if any(w in msg_lower for w in ("build", "create", "make", "generate", "pattern for")):
            return "build"
        if any(w in msg_lower for w in ("common", "standard", "built-in", "preset")):
            return "lookup"
        # If message contains a regex pattern, explain it
        if re.search(r'[\\{}\[\]+*?^$|()]', message):
            return "explain"
        return "build"

    async def analyze(self, message: str, context: dict[str, Any]) -> str:
        llm = context.get("llm")
        engram = context.get("engram")

        intent = self.detect_intent(message)

        if intent == "lookup":
            lines = [f"[Rune] Common Patterns"]
            msg_lower = message.lower()
            found = False
            for name, pattern in _COMMON_PATTERNS.items():
                if name.replace('_', ' ') in msg_lower or name in msg_lower:
                    lines.append(f"\n  {name}: {pattern}")
                    lines.append(f"  Explanation: {self.explain_pattern(pattern)}")
                    found = True
            if not found:
                lines.append(f"\n  Available patterns:")
                for name in sorted(_COMMON_PATTERNS.keys()):
                    lines.append(f"    {name}: {_COMMON_PATTERNS[name][:50]}")
            return "\n".join(lines)

        if intent == "explain":
            # Extract regex pattern from message
            pattern_match = re.search(r'[`\'"](.+?)[`\'"]|(?:pattern|regex)[:\s]+(\S+)', message)
            pattern = ""
            if pattern_match:
                pattern = pattern_match.group(1) or pattern_match.group(2) or ""
            if not pattern:
                # Try to find regex-like content
                for token in message.split():
                    if re.search(r'[\\{}\[\]+*?^$]', token) and len(token) > 3:
                        pattern = token
                        break

            if pattern:
                valid, msg = self.validate_pattern(pattern)
                explanation = self.explain_pattern(pattern)
                result = RegexResult(
                    pattern=pattern, explanation=explanation,
                    test_matches=[], test_non_matches=[], flags="",
                )
                self._history.append(result)

                lines = [f"[Rune] Pattern Explained"]
                lines.append(f"  Pattern: {pattern}")
                lines.append(f"  Valid: {'Yes' if valid else 'No -- ' + msg}")
                lines.append(f"  Breakdown: {explanation}")
                return "\n".join(lines)

        if intent == "test":
            # Extract pattern and test strings
            pattern_match = re.search(r'[`\'"](.+?)[`\'"]', message)
            pattern = pattern_match.group(1) if pattern_match else ""
            if pattern:
                # Extract test strings
                test_strings = re.findall(r'(?:against|with|on)\s+[`\'"](.+?)[`\'"]', message)
                if not test_strings:
                    test_strings = [s.strip() for s in message.split('\n')[1:] if s.strip()]
                results = self.test_pattern(pattern, test_strings)

                lines = [f"[Rune] Pattern Test"]
                lines.append(f"  Pattern: {pattern}")
                for s, matched in results.items():
                    icon = "+" if matched else "X"
                    lines.append(f"    {icon} '{s}' -> {'MATCH' if matched else 'NO MATCH'}")
                return "\n".join(lines)

        # Build mode -- use LLM if available
        if llm:
            prompt = (
                "Create a regex pattern for the following requirement:\n\n"
                f"{message[:2000]}\n\n"
                "Provide:\n"
                "1. The regex pattern\n"
                "2. A breakdown of each component\n"
                "3. Example matches and non-matches\n"
                "4. Any caveats or limitations"
            )
            try:
                result = await llm.complete(prompt)
                return f"[Rune] Pattern Builder\n\n{result[:2000]}"
            except Exception:
                pass

        # Without LLM, check for common pattern names
        msg_lower = message.lower()
        for name, pattern in _COMMON_PATTERNS.items():
            if name.replace('_', ' ') in msg_lower:
                explanation = self.explain_pattern(pattern)
                result_obj = RegexResult(
                    pattern=pattern, explanation=explanation,
                    test_matches=[], test_non_matches=[], flags="",
                )
                self._history.append(result_obj)
                return (
                    f"[Rune] Pattern: {name}\n"
                    f"  Regex: {pattern}\n"
                    f"  Explanation: {explanation}"
                )

        if engram:
            try:
                engram.episodic.store(
                    f"Regex assistance: {intent} -- {message[:60]}",
                    source=self.name,
                )
            except Exception:
                pass

        return "[Rune] Describe what you want to match, or provide a pattern to explain."

    async def suggest(self, message: str, context: dict[str, Any]) -> str:
        """Suggest building a regex when the message describes a text pattern to match."""
        pattern_indicators = ("match", "extract", "parse", "find all", "validate", "pattern for", "regex for")
        msg_lower = message.lower()
        if any(indicator in msg_lower for indicator in pattern_indicators):
            return "Text pattern described -- build a regex to match it precisely."
        return ""

    async def monitor(self, event: dict[str, Any], context: dict[str, Any]) -> str | None:
        """Rune has no background monitoring -- passive agent."""
        return None

    async def coordinate(self, analysis_result: str, context: dict[str, Any]) -> str:
        """Rune is standalone -- no cross-agent coordination."""
        return ""
