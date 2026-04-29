"""Tests for benchmark report generation."""
from __future__ import annotations

import json

import pytest

from nexus.benchmarks.models import BenchmarkResult, SuiteResult
from nexus.benchmarks.report import ReportGenerator


@pytest.fixture
def reporter():
    return ReportGenerator()


@pytest.fixture
def sample_results():
    return [
        BenchmarkResult(
            case_name="vex_sql_injection",
            module_name="vex",
            passed=True,
            output="[Vex] Security Scan Results\n  Found: 1 HIGH / 0 MEDIUM / 0 LOW",
            duration_ms=12.5,
            memory_kb=128.0,
            matched_patterns=[r"(?i)sql.?inject"],
            missed_patterns=[],
            false_matches=[],
        ),
        BenchmarkResult(
            case_name="vex_xss",
            module_name="vex",
            passed=True,
            output="[Vex] Security Scan Results\n  XSS detected",
            duration_ms=8.3,
            memory_kb=96.0,
            matched_patterns=[r"(?i)xss"],
            missed_patterns=[],
            false_matches=[],
        ),
        BenchmarkResult(
            case_name="redline_liability",
            module_name="redline",
            passed=False,
            output="[Redline] No risky clauses found.",
            duration_ms=23.1,
            memory_kb=150.0,
            matched_patterns=[],
            missed_patterns=[r"(?i)liabilit"],
            false_matches=[],
        ),
    ]


@pytest.fixture
def suite_result(sample_results):
    return SuiteResult(
        suite_name="Test Suite",
        total_cases=3,
        passed=2,
        failed=1,
        total_duration_ms=43.9,
        avg_duration_ms=14.63,
        peak_memory_kb=150.0,
        results=sample_results,
        accuracy=66.7,
        timestamp="2024-01-01T00:00:00Z",
    )


def test_terminal_report_contains_pass_fail(reporter, suite_result):
    report = reporter.to_terminal(suite_result)
    assert "[PASS]" in report
    assert "[FAIL]" in report


def test_terminal_report_contains_suite_name(reporter, suite_result):
    report = reporter.to_terminal(suite_result)
    assert "Test Suite" in report


def test_terminal_report_contains_stats(reporter, suite_result):
    report = reporter.to_terminal(suite_result)
    assert "2/3 passed" in report
    assert "66.7%" in report


def test_terminal_report_shows_missed_patterns(reporter, suite_result):
    report = reporter.to_terminal(suite_result)
    assert "Expected:" in report
    assert "(?i)liabilit" in report


def test_terminal_report_shows_duration(reporter, suite_result):
    report = reporter.to_terminal(suite_result)
    assert "ms" in report


def test_markdown_report_has_headers(reporter, suite_result):
    report = reporter.to_markdown(suite_result)
    assert "# Test Suite Benchmark Report" in report
    assert "**Timestamp:**" in report


def test_markdown_report_has_table(reporter, suite_result):
    report = reporter.to_markdown(suite_result)
    assert "| Case | Module | Status | Duration | Memory |" in report
    assert "PASS" in report
    assert "FAIL" in report


def test_markdown_report_has_failed_section(reporter, suite_result):
    report = reporter.to_markdown(suite_result)
    assert "## Failed Cases" in report
    assert "redline_liability" in report


def test_markdown_no_failed_section_when_all_pass(reporter):
    results = [
        BenchmarkResult(
            case_name="test_pass",
            module_name="vex",
            passed=True,
            output="ok",
            duration_ms=5.0,
            memory_kb=64.0,
            matched_patterns=[],
            missed_patterns=[],
            false_matches=[],
        ),
    ]
    sr = SuiteResult(
        suite_name="All Pass",
        total_cases=1,
        passed=1,
        failed=0,
        total_duration_ms=5.0,
        avg_duration_ms=5.0,
        peak_memory_kb=64.0,
        results=results,
        accuracy=100.0,
        timestamp="2024-01-01T00:00:00Z",
    )
    report = reporter.to_markdown(sr)
    assert "## Failed Cases" not in report


def test_json_report_is_valid_json(reporter, suite_result):
    report = reporter.to_json(suite_result)
    data = json.loads(report)
    assert data["suite_name"] == "Test Suite"
    assert data["total_cases"] == 3
    assert data["passed"] == 2
    assert data["failed"] == 1


def test_json_report_has_results_array(reporter, suite_result):
    data = json.loads(reporter.to_json(suite_result))
    assert len(data["results"]) == 3
    for r in data["results"]:
        assert "case_name" in r
        assert "passed" in r
        assert "duration_ms" in r


def test_json_report_includes_error(reporter):
    results = [
        BenchmarkResult(
            case_name="err_case",
            module_name="vex",
            passed=False,
            output="",
            duration_ms=0.0,
            memory_kb=0.0,
            matched_patterns=[],
            missed_patterns=[],
            false_matches=[],
            error="Timed out after 5s",
        ),
    ]
    sr = SuiteResult(
        suite_name="Error Suite",
        total_cases=1,
        passed=0,
        failed=1,
        total_duration_ms=0.0,
        avg_duration_ms=0.0,
        peak_memory_kb=0.0,
        results=results,
        accuracy=0.0,
        timestamp="2024-01-01T00:00:00Z",
    )
    data = json.loads(reporter.to_json(sr))
    assert data["results"][0]["error"] == "Timed out after 5s"


def test_summary_report(reporter):
    sr1 = SuiteResult(
        suite_name="Suite A",
        total_cases=10,
        passed=9,
        failed=1,
        total_duration_ms=100.0,
        avg_duration_ms=10.0,
        peak_memory_kb=200.0,
        results=[
            BenchmarkResult(
                case_name=f"case_{i}",
                module_name="vex",
                passed=i < 9,
                output="out",
                duration_ms=10.0,
                memory_kb=20.0,
                matched_patterns=[],
                missed_patterns=[] if i < 9 else ["x"],
                false_matches=[],
            )
            for i in range(10)
        ],
        accuracy=90.0,
        timestamp="2024-01-01T00:00:00Z",
    )
    sr2 = SuiteResult(
        suite_name="Suite B",
        total_cases=5,
        passed=5,
        failed=0,
        total_duration_ms=50.0,
        avg_duration_ms=10.0,
        peak_memory_kb=150.0,
        results=[
            BenchmarkResult(
                case_name=f"b_case_{i}",
                module_name="carve",
                passed=True,
                output="out",
                duration_ms=10.0,
                memory_kb=15.0,
                matched_patterns=[],
                missed_patterns=[],
                false_matches=[],
            )
            for i in range(5)
        ],
        accuracy=100.0,
        timestamp="2024-01-01T00:00:00Z",
    )

    summary = reporter.to_summary([sr1, sr2])
    assert "14/15" in summary
    assert "93.3%" in summary
    assert "vex" in summary
    assert "carve" in summary
    assert "Per-Agent" in summary


def test_summary_empty_list(reporter):
    summary = reporter.to_summary([])
    assert "0/0" in summary
