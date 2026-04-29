"""
Benchmark runner -- executes benchmark suites against NEXUS modules and agents.
"""
from __future__ import annotations

import asyncio
import re
import time
import tracemalloc
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock

from nexus.benchmarks.models import (
    BenchmarkCase,
    BenchmarkResult,
    BenchmarkSuite,
    SuiteResult,
)


# Agent/module class registry -- maps module name to its class.
_MODULE_REGISTRY: dict[str, type] = {}


def _build_registry() -> dict[str, type]:
    """Lazily discover all agent and module classes."""
    if _MODULE_REGISTRY:
        return _MODULE_REGISTRY

    # Agents
    from nexus.agents.vex import VexModule
    from nexus.agents.arbiter import ArbiterModule
    from nexus.agents.carve import CarveModule
    from nexus.agents.flux import FluxModule
    from nexus.agents.vigil import VigilModule
    from nexus.agents.rune import RuneModule
    from nexus.agents.remedy import RemedyModule
    from nexus.agents.redline import RedlineModule
    from nexus.agents.mandate import MandateModule
    from nexus.agents.bastion import BastionModule
    from nexus.agents.gauge import GaugeModule

    for cls in (
        VexModule, ArbiterModule, CarveModule, FluxModule, VigilModule,
        RuneModule, RemedyModule, RedlineModule, MandateModule,
        BastionModule, GaugeModule,
    ):
        _MODULE_REGISTRY[cls.name] = cls

    return _MODULE_REGISTRY


def _build_mock_context() -> dict[str, Any]:
    """Build a mock context that satisfies agent requirements without an LLM."""
    mock_aegis = AsyncMock()
    mock_aegis.get_trust = AsyncMock(return_value=0)

    return {
        "llm": None,
        "engram": None,
        "chronicle": None,
        "pulse": None,
        "cortex": None,
        "aegis": mock_aegis,
    }


class BenchmarkRunner:
    """Runs benchmarks against NEXUS modules and agents."""

    def __init__(self) -> None:
        self.results: list[BenchmarkResult] = []

    async def run_suite(self, suite: BenchmarkSuite) -> SuiteResult:
        """Run a complete benchmark suite and return aggregated results."""
        registry = _build_registry()
        results: list[BenchmarkResult] = []
        total_duration = 0.0
        peak_memory = 0.0

        for case in suite.cases:
            module_cls = registry.get(case.module_name)
            if module_cls is None:
                results.append(BenchmarkResult(
                    case_name=case.name,
                    module_name=case.module_name,
                    passed=False,
                    output="",
                    duration_ms=0.0,
                    memory_kb=0.0,
                    matched_patterns=[],
                    missed_patterns=case.expected_patterns[:],
                    false_matches=[],
                    error=f"Module '{case.module_name}' not found in registry",
                ))
                continue

            module = module_cls()
            result = await self.run_case(case, module)
            results.append(result)
            total_duration += result.duration_ms
            if result.memory_kb > peak_memory:
                peak_memory = result.memory_kb

        self.results.extend(results)

        passed = sum(1 for r in results if r.passed)
        failed = len(results) - passed
        avg_duration = total_duration / len(results) if results else 0.0
        accuracy = (passed / len(results) * 100) if results else 0.0

        return SuiteResult(
            suite_name=suite.name,
            total_cases=len(results),
            passed=passed,
            failed=failed,
            total_duration_ms=total_duration,
            avg_duration_ms=avg_duration,
            peak_memory_kb=peak_memory,
            results=results,
            accuracy=accuracy,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    async def run_case(self, case: BenchmarkCase, module: Any) -> BenchmarkResult:
        """Run a single benchmark case against a module instance."""
        context = _build_mock_context()
        output = ""
        error: str | None = None
        duration_ms = 0.0
        memory_kb = 0.0

        # Measure memory and wall-clock time
        tracemalloc.start()
        snapshot_before = tracemalloc.take_snapshot()
        t0 = time.perf_counter()

        try:
            output = await asyncio.wait_for(
                module.handle(case.input_message, context),
                timeout=case.timeout,
            )
        except asyncio.TimeoutError:
            error = f"Timed out after {case.timeout}s"
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"

        t1 = time.perf_counter()
        snapshot_after = tracemalloc.take_snapshot()
        tracemalloc.stop()

        duration_ms = (t1 - t0) * 1000

        # Calculate memory delta
        stats = snapshot_after.compare_to(snapshot_before, "lineno")
        memory_kb = sum(s.size_diff for s in stats) / 1024
        if memory_kb < 0:
            memory_kb = 0.0

        # Check expected patterns
        matched: list[str] = []
        missed: list[str] = []
        for pattern in case.expected_patterns:
            if re.search(pattern, output, re.IGNORECASE):
                matched.append(pattern)
            else:
                missed.append(pattern)

        # Check unexpected patterns (false positives)
        false_matches: list[str] = []
        for pattern in case.unexpected_patterns:
            if re.search(pattern, output, re.IGNORECASE):
                false_matches.append(pattern)

        passed = (not missed) and (not false_matches) and (error is None)

        return BenchmarkResult(
            case_name=case.name,
            module_name=case.module_name,
            passed=passed,
            output=output,
            duration_ms=duration_ms,
            memory_kb=memory_kb,
            matched_patterns=matched,
            missed_patterns=missed,
            false_matches=false_matches,
            error=error,
        )

    def generate_report(self, suite_result: SuiteResult) -> str:
        """Generate a formatted benchmark report (terminal format)."""
        from nexus.benchmarks.report import ReportGenerator
        return ReportGenerator().to_terminal(suite_result)
