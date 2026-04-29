"""Tests for benchmark data models."""
from __future__ import annotations

from nexus.benchmarks.models import (
    BenchmarkCase,
    BenchmarkResult,
    BenchmarkSuite,
    SuiteResult,
)


def test_benchmark_case_defaults():
    case = BenchmarkCase(
        name="test_case",
        module_name="vex",
        input_message="scan: eval(x)",
        expected_patterns=[r"(?i)eval"],
    )
    assert case.name == "test_case"
    assert case.module_name == "vex"
    assert case.category == "accuracy"
    assert case.timeout == 5.0
    assert case.unexpected_patterns == []


def test_benchmark_case_with_unexpected():
    case = BenchmarkCase(
        name="test_no_fp",
        module_name="vex",
        input_message="scan: x = 1",
        expected_patterns=[r"(?i)clean"],
        unexpected_patterns=[r"(?i)critical"],
        category="accuracy",
        timeout=3.0,
    )
    assert len(case.unexpected_patterns) == 1
    assert case.timeout == 3.0


def test_benchmark_result_passed():
    result = BenchmarkResult(
        case_name="test",
        module_name="vex",
        passed=True,
        output="No vulnerabilities detected.",
        duration_ms=5.0,
        memory_kb=128.0,
        matched_patterns=[r"(?i)no"],
        missed_patterns=[],
        false_matches=[],
    )
    assert result.passed
    assert result.error is None
    assert result.duration_ms == 5.0


def test_benchmark_result_failed():
    result = BenchmarkResult(
        case_name="test",
        module_name="vex",
        passed=False,
        output="something",
        duration_ms=12.0,
        memory_kb=64.0,
        matched_patterns=[],
        missed_patterns=[r"(?i)sql"],
        false_matches=[],
        error="Timed out after 5s",
    )
    assert not result.passed
    assert result.error is not None


def test_benchmark_suite_creation():
    cases = [
        BenchmarkCase(
            name=f"case_{i}",
            module_name="vex",
            input_message=f"scan: test {i}",
            expected_patterns=[r"test"],
        )
        for i in range(5)
    ]
    suite = BenchmarkSuite(name="Test Suite", description="A test suite", cases=cases)
    assert suite.name == "Test Suite"
    assert len(suite.cases) == 5


def test_suite_result():
    result = SuiteResult(
        suite_name="Test",
        total_cases=10,
        passed=8,
        failed=2,
        total_duration_ms=150.0,
        avg_duration_ms=15.0,
        peak_memory_kb=256.0,
        results=[],
        accuracy=80.0,
        timestamp="2024-01-01T00:00:00Z",
    )
    assert result.accuracy == 80.0
    assert result.passed + result.failed == result.total_cases


def test_suite_result_perfect():
    result = SuiteResult(
        suite_name="Perfect",
        total_cases=5,
        passed=5,
        failed=0,
        total_duration_ms=50.0,
        avg_duration_ms=10.0,
        peak_memory_kb=100.0,
        results=[],
        accuracy=100.0,
        timestamp="2024-01-01T00:00:00Z",
    )
    assert result.accuracy == 100.0
    assert result.failed == 0


def test_multiple_expected_patterns():
    case = BenchmarkCase(
        name="multi_pattern",
        module_name="vex",
        input_message="scan: eval(x)",
        expected_patterns=[r"(?i)eval", r"(?i)inject", r"(?i)code.?exec"],
    )
    assert len(case.expected_patterns) == 3
