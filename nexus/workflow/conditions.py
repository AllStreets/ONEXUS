"""
Safe condition evaluator for workflow step conditions.

Supports expressions like:
  - "step_name.success"
  - "step_name.output contains 'critical'"
  - "step_a.success and step_b.success"
  - "not step_name.success"
  - "step_a.success or step_b.output contains 'error'"
"""
from __future__ import annotations

import re
from typing import Any

from nexus.workflow.models import StepResult


class ConditionError(Exception):
    """Raised when a condition expression is invalid or references missing data."""


class ConditionEvaluator:
    """Evaluate simple boolean expressions against completed step results."""

    def evaluate(self, expression: str, results: dict[str, StepResult]) -> bool:
        """Evaluate a condition expression against step results.

        Returns True if the condition holds, False otherwise.
        """
        if not expression or not expression.strip():
            return True

        tokens = self._tokenize(expression.strip())
        value, remaining = self._parse_or(tokens, results)
        if remaining:
            raise ConditionError(f"Unexpected tokens after expression: {remaining}")
        return value

    # ── tokenizer ──────────────────────────────────────────────

    _TOKEN_RE = re.compile(
        r"""
        (?P<AND>\band\b)     |
        (?P<OR>\bor\b)       |
        (?P<NOT>\bnot\b)     |
        (?P<CONTAINS>\bcontains\b) |
        (?P<STRING>'[^']*')  |
        (?P<REF>[a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z_][a-zA-Z0-9_]*) |
        (?P<LPAREN>\()       |
        (?P<RPAREN>\))       |
        (?P<WS>\s+)
        """,
        re.VERBOSE,
    )

    def _tokenize(self, expr: str) -> list[tuple[str, str]]:
        tokens: list[tuple[str, str]] = []
        pos = 0
        while pos < len(expr):
            m = self._TOKEN_RE.match(expr, pos)
            if not m:
                raise ConditionError(
                    f"Unexpected character at position {pos}: '{expr[pos]}'"
                )
            kind = m.lastgroup
            assert kind is not None
            if kind != "WS":
                tokens.append((kind, m.group()))
            pos = m.end()
        return tokens

    # ── recursive descent parser ───────────────────────────────

    def _parse_or(
        self, tokens: list[tuple[str, str]], results: dict[str, StepResult]
    ) -> tuple[bool, list[tuple[str, str]]]:
        left, tokens = self._parse_and(tokens, results)
        while tokens and tokens[0][0] == "OR":
            tokens = tokens[1:]
            right, tokens = self._parse_and(tokens, results)
            left = left or right
        return left, tokens

    def _parse_and(
        self, tokens: list[tuple[str, str]], results: dict[str, StepResult]
    ) -> tuple[bool, list[tuple[str, str]]]:
        left, tokens = self._parse_not(tokens, results)
        while tokens and tokens[0][0] == "AND":
            tokens = tokens[1:]
            right, tokens = self._parse_not(tokens, results)
            left = left and right
        return left, tokens

    def _parse_not(
        self, tokens: list[tuple[str, str]], results: dict[str, StepResult]
    ) -> tuple[bool, list[tuple[str, str]]]:
        if tokens and tokens[0][0] == "NOT":
            tokens = tokens[1:]
            value, tokens = self._parse_not(tokens, results)
            return not value, tokens
        return self._parse_atom(tokens, results)

    def _parse_atom(
        self, tokens: list[tuple[str, str]], results: dict[str, StepResult]
    ) -> tuple[bool, list[tuple[str, str]]]:
        if not tokens:
            raise ConditionError("Unexpected end of expression")

        # Parenthesised sub-expression
        if tokens[0][0] == "LPAREN":
            tokens = tokens[1:]
            value, tokens = self._parse_or(tokens, results)
            if not tokens or tokens[0][0] != "RPAREN":
                raise ConditionError("Missing closing parenthesis")
            return value, tokens[1:]

        # Must be a REF
        if tokens[0][0] != "REF":
            raise ConditionError(f"Expected step reference, got '{tokens[0][1]}'")

        ref = tokens[0][1]
        tokens = tokens[1:]

        # Check for "contains 'string'" after the reference
        if tokens and tokens[0][0] == "CONTAINS":
            tokens = tokens[1:]
            if not tokens or tokens[0][0] != "STRING":
                raise ConditionError("'contains' must be followed by a quoted string")
            needle = tokens[0][1][1:-1]  # strip surrounding quotes
            tokens = tokens[1:]
            ref_value = self._resolve_ref(ref, results)
            if isinstance(ref_value, str):
                return needle in ref_value, tokens
            return False, tokens

        # Bare reference -- resolve to bool
        ref_value = self._resolve_ref(ref, results)
        return bool(ref_value), tokens

    # ── reference resolution ───────────────────────────────────

    def _resolve_ref(self, ref: str, results: dict[str, StepResult]) -> Any:
        """Resolve 'step_name.attr' against completed step results."""
        parts = ref.split(".", 1)
        if len(parts) != 2:
            raise ConditionError(f"Invalid reference '{ref}'; expected 'step.attr'")
        step_name, attr = parts

        if step_name not in results:
            raise ConditionError(f"Step '{step_name}' not found in results")

        result = results[step_name]
        if attr == "success":
            return result.success
        elif attr == "output":
            return result.output
        elif attr == "error":
            return result.error or ""
        elif attr == "skipped":
            return result.skipped
        elif attr == "duration":
            return result.duration
        else:
            raise ConditionError(
                f"Unknown attribute '{attr}' on step '{step_name}'; "
                f"valid attributes: success, output, error, skipped, duration"
            )
