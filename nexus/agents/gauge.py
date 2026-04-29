"""
Gauge -- performance metrics analyzer.
Analyzes performance data, benchmarks, timing profiles, and resource
utilization to identify bottlenecks and optimization opportunities.

Inspired by:
  - python/pyperformance (MIT) -- Python performance benchmark suite
  - plasma-umass/scalene (Apache 2.0) -- Python CPU/memory/GPU profiler
  - locustio/locust (MIT) -- load testing framework
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any
from nexus.agents.base import AgentModule, TrustTier


@dataclass
class PerfMetric:
    name: str
    value: float
    unit: str
    category: str  # "latency", "throughput", "memory", "cpu", "custom"


@dataclass
class Bottleneck:
    component: str
    metric: str
    severity: str  # "critical", "warning", "info"
    description: str
    suggestion: str


# Thresholds for common metrics
_THRESHOLDS: dict[str, dict[str, float]] = {
    "response_time_ms": {"warning": 500, "critical": 2000},
    "error_rate_pct": {"warning": 1, "critical": 5},
    "cpu_pct": {"warning": 70, "critical": 90},
    "memory_pct": {"warning": 75, "critical": 90},
    "p99_ms": {"warning": 1000, "critical": 5000},
    "throughput_rps": {"warning": 100, "critical": 10},  # below these = bad
}


class GaugeModule(AgentModule):
    name = "gauge"
    description = "Performance analyzer -- identifies bottlenecks, analyzes benchmarks, profiles resource usage"
    version = "0.1.0"

    watch_events: list[str] = ["cortex.response"]
    coordination_targets: list[str] = ["vigil"]

    def __init__(self):
        self._analyses: list[dict[str, Any]] = []

    @staticmethod
    def parse_metrics(text: str) -> list[PerfMetric]:
        """Parse performance metrics from text."""
        metrics: list[PerfMetric] = []

        # Pattern: "metric_name: 123.45ms" or "metric: 123 MB"
        for match in re.finditer(
            r'(\w[\w\s]*?):\s*([\d.]+)\s*(ms|s|us|ns|MB|GB|KB|%|rps|req/s|ops/s|qps)',
            text, re.IGNORECASE,
        ):
            name = match.group(1).strip().lower().replace(' ', '_')
            value = float(match.group(2))
            unit = match.group(3).lower()

            category = "custom"
            if unit in ("ms", "s", "us", "ns"):
                category = "latency"
            elif unit in ("mb", "gb", "kb"):
                category = "memory"
            elif unit == "%":
                if "cpu" in name:
                    category = "cpu"
                elif "mem" in name:
                    category = "memory"
            elif unit in ("rps", "req/s", "ops/s", "qps"):
                category = "throughput"

            metrics.append(PerfMetric(name=name, value=value, unit=unit, category=category))

        return metrics

    @staticmethod
    def normalize_to_ms(metric: PerfMetric) -> float:
        """Normalize latency metrics to milliseconds."""
        conversions = {"ms": 1, "s": 1000, "us": 0.001, "ns": 0.000001}
        return metric.value * conversions.get(metric.unit, 1)

    @staticmethod
    def find_bottlenecks(metrics: list[PerfMetric]) -> list[Bottleneck]:
        """Identify performance bottlenecks from metrics."""
        bottlenecks: list[Bottleneck] = []

        for m in metrics:
            # Check latency
            if m.category == "latency":
                ms_val = GaugeModule.normalize_to_ms(m)
                if ms_val > 2000:
                    bottlenecks.append(Bottleneck(
                        component=m.name, metric=f"{m.value}{m.unit}",
                        severity="critical",
                        description=f"Response time {ms_val:.0f}ms exceeds critical threshold",
                        suggestion="Profile slow operations, add caching, optimize queries",
                    ))
                elif ms_val > 500:
                    bottlenecks.append(Bottleneck(
                        component=m.name, metric=f"{m.value}{m.unit}",
                        severity="warning",
                        description=f"Response time {ms_val:.0f}ms exceeds warning threshold",
                        suggestion="Consider async processing or caching",
                    ))

            # Check CPU/memory percentage
            if m.unit == "%" and m.value > 90:
                bottlenecks.append(Bottleneck(
                    component=m.name, metric=f"{m.value}%",
                    severity="critical",
                    description=f"{m.name} at {m.value}% utilization",
                    suggestion="Scale resources, optimize hotspots, or reduce load",
                ))
            elif m.unit == "%" and m.value > 70:
                bottlenecks.append(Bottleneck(
                    component=m.name, metric=f"{m.value}%",
                    severity="warning",
                    description=f"{m.name} at {m.value}% utilization",
                    suggestion="Monitor closely, plan for scaling",
                ))

        return bottlenecks

    @staticmethod
    def compare_metrics(before: list[PerfMetric], after: list[PerfMetric]) -> list[dict[str, Any]]:
        """Compare two sets of metrics to find regressions/improvements."""
        before_map = {m.name: m for m in before}
        after_map = {m.name: m for m in after}

        comparisons: list[dict[str, Any]] = []
        for name in set(before_map) & set(after_map):
            b, a = before_map[name], after_map[name]
            if b.value > 0:
                change_pct = ((a.value - b.value) / b.value) * 100
                status = "regression" if change_pct > 10 else "improvement" if change_pct < -10 else "stable"
                comparisons.append({
                    "metric": name, "before": b.value, "after": a.value,
                    "change_pct": round(change_pct, 1), "status": status,
                })

        return comparisons

    @staticmethod
    def summarize(metrics: list[PerfMetric]) -> dict[str, Any]:
        """Generate a summary of metrics by category."""
        by_category: dict[str, list[PerfMetric]] = defaultdict(list)
        for m in metrics:
            by_category[m.category].append(m)

        summary: dict[str, Any] = {"total_metrics": len(metrics)}
        for cat, items in by_category.items():
            values = [m.value for m in items]
            summary[cat] = {
                "count": len(items),
                "min": min(values),
                "max": max(values),
                "avg": sum(values) / len(values),
            }
        return summary

    async def analyze(self, message: str, context: dict[str, Any]) -> str:
        llm = context.get("llm")
        engram = context.get("engram")

        metrics = self.parse_metrics(message)

        if not metrics:
            if llm:
                prompt = (
                    "Analyze the following performance data and identify bottlenecks:\n\n"
                    f"{message[:4000]}\n\n"
                    "Provide: 1) Key metrics 2) Bottlenecks 3) Optimization suggestions"
                )
                try:
                    analysis = await llm.complete(prompt)
                    return f"[Gauge] Performance Analysis\n\n{analysis[:2000]}"
                except Exception:
                    pass
            return "[Gauge] No metrics detected. Provide performance data with units (ms, MB, %, rps)."

        bottlenecks = self.find_bottlenecks(metrics)
        summary = self.summarize(metrics)
        self._analyses.append({"metrics": len(metrics), "bottlenecks": len(bottlenecks)})

        if engram:
            try:
                engram.episodic.store(
                    f"Performance analysis: {len(metrics)} metrics, {len(bottlenecks)} bottlenecks",
                    source=self.name,
                )
            except Exception:
                pass

        lines = [f"[Gauge] Performance Analysis"]
        lines.append(f"  Metrics parsed: {len(metrics)}")

        # Group by category
        by_cat: dict[str, list[PerfMetric]] = defaultdict(list)
        for m in metrics:
            by_cat[m.category].append(m)

        for cat, items in by_cat.items():
            lines.append(f"\n  {cat.upper()} ({len(items)}):")
            for m in items:
                lines.append(f"    {m.name}: {m.value} {m.unit}")

        if bottlenecks:
            lines.append(f"\n  Bottlenecks ({len(bottlenecks)}):")
            for b in bottlenecks:
                marker = "!!!" if b.severity == "critical" else "! " if b.severity == "warning" else "  "
                lines.append(f"    {marker} [{b.severity.upper()}] {b.component}: {b.description}")
                lines.append(f"        Suggestion: {b.suggestion}")
        else:
            lines.append("\n  No bottlenecks detected. Performance looks healthy.")

        if llm and bottlenecks:
            prompt = (
                "Given these performance bottlenecks, provide optimization recommendations:\n\n"
                + "\n".join(f"- {b.component}: {b.description}" for b in bottlenecks)
                + "\n\nProvide: prioritized fixes with estimated impact."
            )
            try:
                analysis = await llm.complete(prompt)
                lines.append(f"\n  -- Optimization Plan --\n  {analysis[:1000]}")
            except Exception:
                pass

        return "\n".join(lines)

    async def suggest(self, message: str, context: dict[str, Any]) -> str:
        if re.search(r'\b(slow|latency|performance|bottleneck|timeout|throughput|benchmark)\b', message, re.IGNORECASE):
            return "Provide metrics with units (ms, %, MB, rps) and Gauge will identify bottlenecks."
        return ""

    async def monitor(self, event: dict[str, Any], context: dict[str, Any]) -> str | None:
        response = event.get("data", {}).get("response", "")
        if re.search(r'\b(\d+\s*(?:ms|s|us|ns|%|MB|GB|rps))\b', response, re.IGNORECASE):
            return f"[Gauge] Performance metrics detected in cortex response: {response[:200]}"
        return None

    async def coordinate(self, analysis_result: str, context: dict[str, Any]) -> str:
        cortex = context.get("cortex")
        if not cortex:
            return ""
        if "bottleneck" in analysis_result.lower() or "critical" in analysis_result.lower():
            try:
                vigil_result = await cortex.route("vigil", analysis_result, context)
                return f"[vigil] {vigil_result[:500]}"
            except Exception:
                pass
        return ""
