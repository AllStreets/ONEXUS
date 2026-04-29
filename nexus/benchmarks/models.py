"""
Benchmark data models for NEXUS agent and module evaluation.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BenchmarkCase:
    """A single benchmark test case."""
    name: str
    module_name: str
    input_message: str
    expected_patterns: list[str]  # regex patterns output should match
    unexpected_patterns: list[str] = field(default_factory=list)  # patterns output should NOT match
    category: str = "accuracy"  # accuracy, performance, memory
    timeout: float = 5.0


@dataclass
class BenchmarkResult:
    """Result of running a single benchmark case."""
    case_name: str
    module_name: str
    passed: bool
    output: str
    duration_ms: float
    memory_kb: float
    matched_patterns: list[str]
    missed_patterns: list[str]
    false_matches: list[str]
    error: str | None = None


@dataclass
class BenchmarkSuite:
    """A named collection of benchmark cases."""
    name: str
    description: str
    cases: list[BenchmarkCase]


@dataclass
class SuiteResult:
    """Aggregated results for a complete benchmark suite."""
    suite_name: str
    total_cases: int
    passed: int
    failed: int
    total_duration_ms: float
    avg_duration_ms: float
    peak_memory_kb: float
    results: list[BenchmarkResult]
    accuracy: float  # percentage 0-100
    timestamp: str
