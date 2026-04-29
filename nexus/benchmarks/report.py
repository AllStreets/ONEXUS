"""
Report generation for benchmark results.
Supports terminal, markdown, and JSON output formats.
"""
from __future__ import annotations

import json
from typing import Any

from nexus.benchmarks.models import BenchmarkResult, SuiteResult


class ReportGenerator:
    """Generates benchmark reports in multiple formats."""

    def to_terminal(self, result: SuiteResult) -> str:
        """Rich formatted terminal output with pass/fail indicators."""
        lines: list[str] = []
        lines.append(f"Running {result.suite_name} benchmark...")

        for r in result.results:
            dur = f"{r.duration_ms:.0f}ms"
            if r.passed:
                lines.append(f"  [PASS] {r.case_name:<35} {dur:>6}")
            else:
                lines.append(f"  [FAIL] {r.case_name:<35} {dur:>6}")
                if r.error:
                    lines.append(f"         Error: {r.error}")
                for pattern in r.missed_patterns:
                    lines.append(f"         Expected: {pattern}")
                for pattern in r.false_matches:
                    lines.append(f"         Unexpected match: {pattern}")
                if r.output:
                    # Show a preview of the output for failed cases
                    preview = r.output.replace("\n", " ")[:80]
                    lines.append(f"         Got: {preview}")

        lines.append("")
        lines.append(
            f"{result.suite_name}: {result.passed}/{result.total_cases} passed "
            f"({result.accuracy:.1f}%)  "
            f"avg: {result.avg_duration_ms:.0f}ms  "
            f"peak: {result.peak_memory_kb:.0f}KB"
        )

        return "\n".join(lines)

    def to_markdown(self, result: SuiteResult) -> str:
        """Markdown report for documentation."""
        lines: list[str] = []
        lines.append(f"# {result.suite_name} Benchmark Report")
        lines.append("")
        lines.append(f"**Timestamp:** {result.timestamp}")
        lines.append(f"**Total Cases:** {result.total_cases}")
        lines.append(f"**Passed:** {result.passed}")
        lines.append(f"**Failed:** {result.failed}")
        lines.append(f"**Accuracy:** {result.accuracy:.1f}%")
        lines.append(f"**Avg Duration:** {result.avg_duration_ms:.1f}ms")
        lines.append(f"**Peak Memory:** {result.peak_memory_kb:.1f}KB")
        lines.append("")

        # Results table
        lines.append("| Case | Module | Status | Duration | Memory |")
        lines.append("|------|--------|--------|----------|--------|")

        for r in result.results:
            status = "PASS" if r.passed else "FAIL"
            lines.append(
                f"| {r.case_name} | {r.module_name} | {status} | "
                f"{r.duration_ms:.1f}ms | {r.memory_kb:.1f}KB |"
            )

        # Failed case details
        failed = [r for r in result.results if not r.passed]
        if failed:
            lines.append("")
            lines.append("## Failed Cases")
            lines.append("")
            for r in failed:
                lines.append(f"### {r.case_name}")
                if r.error:
                    lines.append(f"- **Error:** {r.error}")
                if r.missed_patterns:
                    lines.append(f"- **Missed patterns:** {', '.join(r.missed_patterns)}")
                if r.false_matches:
                    lines.append(f"- **Unexpected matches:** {', '.join(r.false_matches)}")
                if r.output:
                    lines.append(f"- **Output preview:** `{r.output[:200]}`")
                lines.append("")

        return "\n".join(lines)

    def to_json(self, result: SuiteResult) -> str:
        """JSON report for programmatic access."""
        data: dict[str, Any] = {
            "suite_name": result.suite_name,
            "timestamp": result.timestamp,
            "total_cases": result.total_cases,
            "passed": result.passed,
            "failed": result.failed,
            "accuracy": result.accuracy,
            "total_duration_ms": result.total_duration_ms,
            "avg_duration_ms": result.avg_duration_ms,
            "peak_memory_kb": result.peak_memory_kb,
            "results": [],
        }

        for r in result.results:
            data["results"].append({
                "case_name": r.case_name,
                "module_name": r.module_name,
                "passed": r.passed,
                "duration_ms": r.duration_ms,
                "memory_kb": r.memory_kb,
                "matched_patterns": r.matched_patterns,
                "missed_patterns": r.missed_patterns,
                "false_matches": r.false_matches,
                "error": r.error,
                "output_preview": r.output[:500] if r.output else "",
            })

        return json.dumps(data, indent=2)

    def to_summary(self, results: list[SuiteResult]) -> str:
        """Combined summary across all suites."""
        lines: list[str] = []

        total_cases = 0
        total_passed = 0
        total_duration = 0.0
        peak_memory = 0.0

        # Per-suite summaries
        for sr in results:
            total_cases += sr.total_cases
            total_passed += sr.passed
            total_duration += sr.total_duration_ms
            if sr.peak_memory_kb > peak_memory:
                peak_memory = sr.peak_memory_kb

        total_failed = total_cases - total_passed
        overall_accuracy = (total_passed / total_cases * 100) if total_cases else 0.0
        overall_avg = total_duration / total_cases if total_cases else 0.0

        # Per-agent breakdown
        agent_stats: dict[str, dict[str, Any]] = {}
        for sr in results:
            for r in sr.results:
                if r.module_name not in agent_stats:
                    agent_stats[r.module_name] = {
                        "total": 0, "passed": 0, "total_ms": 0.0,
                    }
                agent_stats[r.module_name]["total"] += 1
                if r.passed:
                    agent_stats[r.module_name]["passed"] += 1
                agent_stats[r.module_name]["total_ms"] += r.duration_ms

        lines.append(
            f"Overall: {total_passed}/{total_cases} passed ({overall_accuracy:.1f}%)  "
            f"avg: {overall_avg:.0f}ms  peak: {peak_memory:.0f}KB"
        )
        lines.append("")
        lines.append("Per-Agent Breakdown:")

        for agent_name in sorted(agent_stats.keys()):
            s = agent_stats[agent_name]
            pct = (s["passed"] / s["total"] * 100) if s["total"] else 0.0
            avg = s["total_ms"] / s["total"] if s["total"] else 0.0
            lines.append(
                f"  {agent_name:<15} {s['passed']}/{s['total']} ({pct:.0f}%)  avg: {avg:.0f}ms"
            )

        return "\n".join(lines)
