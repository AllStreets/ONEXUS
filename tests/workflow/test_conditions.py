"""Tests for nexus.workflow.conditions."""
from __future__ import annotations

import pytest

from nexus.workflow.conditions import ConditionEvaluator, ConditionError
from nexus.workflow.models import StepResult


def _result(name: str, success: bool = True, output: str = "") -> StepResult:
    return StepResult(step_name=name, module="m", output=output, success=success, duration=0.1)


@pytest.fixture
def evaluator():
    return ConditionEvaluator()


class TestBasicConditions:
    def test_empty_expression_is_true(self, evaluator):
        assert evaluator.evaluate("", {}) is True
        assert evaluator.evaluate("   ", {}) is True

    def test_success_true(self, evaluator):
        results = {"step_a": _result("step_a", success=True)}
        assert evaluator.evaluate("step_a.success", results) is True

    def test_success_false(self, evaluator):
        results = {"step_a": _result("step_a", success=False)}
        assert evaluator.evaluate("step_a.success", results) is False

    def test_output_contains(self, evaluator):
        results = {"scan": _result("scan", output="found critical vulnerability")}
        assert evaluator.evaluate("scan.output contains 'critical'", results) is True
        assert evaluator.evaluate("scan.output contains 'harmless'", results) is False

    def test_missing_step_raises(self, evaluator):
        with pytest.raises(ConditionError, match="not found"):
            evaluator.evaluate("missing.success", {})

    def test_unknown_attribute_raises(self, evaluator):
        results = {"s": _result("s")}
        with pytest.raises(ConditionError, match="Unknown attribute"):
            evaluator.evaluate("s.bogus", results)


class TestLogicalOperators:
    def test_and_true(self, evaluator):
        results = {
            "a": _result("a", success=True),
            "b": _result("b", success=True),
        }
        assert evaluator.evaluate("a.success and b.success", results) is True

    def test_and_false(self, evaluator):
        results = {
            "a": _result("a", success=True),
            "b": _result("b", success=False),
        }
        assert evaluator.evaluate("a.success and b.success", results) is False

    def test_or(self, evaluator):
        results = {
            "a": _result("a", success=False),
            "b": _result("b", success=True),
        }
        assert evaluator.evaluate("a.success or b.success", results) is True

    def test_not(self, evaluator):
        results = {"a": _result("a", success=False)}
        assert evaluator.evaluate("not a.success", results) is True

    def test_complex_expression(self, evaluator):
        results = {
            "a": _result("a", success=True, output="all clear"),
            "b": _result("b", success=True),
        }
        expr = "a.success and b.success and a.output contains 'clear'"
        assert evaluator.evaluate(expr, results) is True

    def test_parentheses(self, evaluator):
        results = {
            "a": _result("a", success=False),
            "b": _result("b", success=True),
            "c": _result("c", success=True),
        }
        # Without parens: "not a.success and b.success or c.success"
        # is (not a.success) and b.success or c.success => True and True or True => True
        # With explicit parens we can override
        assert evaluator.evaluate("(a.success or b.success) and c.success", results) is True
        assert evaluator.evaluate("a.success and (b.success or c.success)", results) is False

    def test_double_not(self, evaluator):
        results = {"a": _result("a", success=True)}
        assert evaluator.evaluate("not not a.success", results) is True


class TestEdgeCases:
    def test_contains_missing_quote(self, evaluator):
        results = {"s": _result("s")}
        with pytest.raises(ConditionError):
            evaluator.evaluate("s.output contains noquote", results)

    def test_invalid_token(self, evaluator):
        with pytest.raises(ConditionError, match="Unexpected character"):
            evaluator.evaluate("@invalid", {})

    def test_skipped_attribute(self, evaluator):
        r = _result("a")
        r.skipped = True
        results = {"a": r}
        assert evaluator.evaluate("a.skipped", results) is True

    def test_error_attribute(self, evaluator):
        r = _result("a", success=False)
        r.error = "something broke"
        results = {"a": r}
        assert evaluator.evaluate("a.error contains 'broke'", results) is True
