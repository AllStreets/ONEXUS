"""Tests for the benchmark runner."""
from __future__ import annotations

import pytest

from nexus.benchmarks.models import BenchmarkCase, BenchmarkSuite
from nexus.benchmarks.runner import BenchmarkRunner


@pytest.fixture
def runner():
    return BenchmarkRunner()


@pytest.fixture
def simple_suite():
    return BenchmarkSuite(
        name="Simple Test Suite",
        description="Minimal suite for testing the runner",
        cases=[
            BenchmarkCase(
                name="vex_eval_test",
                module_name="vex",
                input_message="scan: result = eval(user_input)",
                expected_patterns=[r"(?i)eval", r"(?i)inject|arbitrary"],
            ),
            BenchmarkCase(
                name="vex_clean_test",
                module_name="vex",
                input_message="scan: x = 1 + 2",
                expected_patterns=[r"(?i)no.*(vulnerabilit|issue|finding)|clean"],
            ),
        ],
    )


@pytest.mark.asyncio
async def test_run_suite_returns_suite_result(runner, simple_suite):
    result = await runner.run_suite(simple_suite)
    assert result.suite_name == "Simple Test Suite"
    assert result.total_cases == 2
    assert len(result.results) == 2
    assert result.timestamp


@pytest.mark.asyncio
async def test_run_suite_accuracy(runner, simple_suite):
    result = await runner.run_suite(simple_suite)
    assert result.passed + result.failed == result.total_cases
    assert 0 <= result.accuracy <= 100


@pytest.mark.asyncio
async def test_run_case_timing(runner):
    case = BenchmarkCase(
        name="timing_test",
        module_name="vex",
        input_message="scan: eval(x)",
        expected_patterns=[r"(?i)eval"],
    )
    from nexus.agents.vex import VexModule
    module = VexModule()
    result = await runner.run_case(case, module)
    assert result.duration_ms >= 0
    assert result.memory_kb >= 0


@pytest.mark.asyncio
async def test_run_case_pattern_matching(runner):
    case = BenchmarkCase(
        name="pattern_test",
        module_name="vex",
        input_message='scan: password = "secret123"',
        expected_patterns=[r"(?i)credential|secret|hardcoded"],
    )
    from nexus.agents.vex import VexModule
    module = VexModule()
    result = await runner.run_case(case, module)
    assert result.passed
    assert len(result.matched_patterns) > 0
    assert len(result.missed_patterns) == 0


@pytest.mark.asyncio
async def test_run_case_unexpected_pattern(runner):
    case = BenchmarkCase(
        name="unexpected_test",
        module_name="vex",
        input_message="scan: x = 1 + 2",
        expected_patterns=[r"(?i)no.*(vulnerabilit|issue|finding)|clean"],
        unexpected_patterns=[r"(?i)critical", r"(?i)high.?risk"],
    )
    from nexus.agents.vex import VexModule
    module = VexModule()
    result = await runner.run_case(case, module)
    assert len(result.false_matches) == 0


@pytest.mark.asyncio
async def test_run_case_missing_module(runner):
    suite = BenchmarkSuite(
        name="Missing Module Suite",
        description="Module does not exist",
        cases=[
            BenchmarkCase(
                name="missing_test",
                module_name="nonexistent_module",
                input_message="test",
                expected_patterns=[r"test"],
            ),
        ],
    )
    result = await runner.run_suite(suite)
    assert result.failed == 1
    assert result.results[0].error
    assert "not found" in result.results[0].error


@pytest.mark.asyncio
async def test_run_case_timeout(runner):
    case = BenchmarkCase(
        name="timeout_test",
        module_name="vex",
        input_message="scan: eval(x)",
        expected_patterns=[r"(?i)eval"],
        timeout=30.0,  # generous timeout for CI
    )
    from nexus.agents.vex import VexModule
    module = VexModule()
    result = await runner.run_case(case, module)
    assert result.error is None


@pytest.mark.asyncio
async def test_runner_accumulates_results(runner, simple_suite):
    assert len(runner.results) == 0
    await runner.run_suite(simple_suite)
    assert len(runner.results) == 2
    await runner.run_suite(simple_suite)
    assert len(runner.results) == 4


@pytest.mark.asyncio
async def test_run_suite_avg_duration(runner, simple_suite):
    result = await runner.run_suite(simple_suite)
    if result.total_cases > 0:
        expected_avg = result.total_duration_ms / result.total_cases
        assert abs(result.avg_duration_ms - expected_avg) < 0.01


@pytest.mark.asyncio
async def test_run_carve_case(runner):
    case = BenchmarkCase(
        name="carve_test",
        module_name="carve",
        input_message="analyze:\ndef f():\n" + "\n".join(f"    x = {i}" for i in range(50)),
        expected_patterns=[r"(?i)long|lines|extract|complex"],
    )
    from nexus.agents.carve import CarveModule
    module = CarveModule()
    result = await runner.run_case(case, module)
    assert result.passed


@pytest.mark.asyncio
async def test_run_remedy_case(runner):
    case = BenchmarkCase(
        name="remedy_test",
        module_name="remedy",
        input_message=(
            "diagnose:\n"
            "Traceback (most recent call last):\n"
            '  File "app.py", line 10, in <module>\n'
            "    import pandas\n"
            "ModuleNotFoundError: No module named 'pandas'"
        ),
        expected_patterns=[r"(?i)install|pip", r"(?i)ModuleNotFoundError"],
    )
    from nexus.agents.remedy import RemedyModule
    module = RemedyModule()
    result = await runner.run_case(case, module)
    assert result.passed


@pytest.mark.asyncio
async def test_run_flux_case(runner):
    case = BenchmarkCase(
        name="flux_test",
        module_name="flux",
        input_message="how many users?",
        expected_patterns=[r"(?i)SELECT", r"(?i)COUNT"],
    )
    from nexus.agents.flux import FluxModule
    module = FluxModule()
    result = await runner.run_case(case, module)
    assert result.passed


@pytest.mark.asyncio
async def test_generate_report(runner, simple_suite):
    suite_result = await runner.run_suite(simple_suite)
    report = runner.generate_report(suite_result)
    assert "Simple Test Suite" in report
    assert "[PASS]" in report or "[FAIL]" in report
