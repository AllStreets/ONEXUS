# tests/modules/test_gauge.py
import pytest
from unittest.mock import AsyncMock
from nexus.agents.gauge import GaugeModule, PerfMetric, Bottleneck


@pytest.fixture
def gauge():
    return GaugeModule()


def test_gauge_attrs(gauge):
    assert gauge.name == "gauge"
    assert gauge.version == "0.1.0"


def test_parse_metrics_latency(gauge):
    text = "response_time: 250ms\np99_latency: 1200ms"
    metrics = gauge.parse_metrics(text)
    assert len(metrics) == 2
    assert metrics[0].category == "latency"
    assert metrics[0].value == 250


def test_parse_metrics_memory(gauge):
    text = "heap_usage: 512MB\ncache_size: 128KB"
    metrics = gauge.parse_metrics(text)
    assert len(metrics) == 2
    assert all(m.category == "memory" for m in metrics)


def test_parse_metrics_throughput(gauge):
    text = "requests: 5000rps"
    metrics = gauge.parse_metrics(text)
    assert len(metrics) == 1
    assert metrics[0].category == "throughput"


def test_parse_metrics_percentage(gauge):
    text = "cpu_usage: 85%"
    metrics = gauge.parse_metrics(text)
    assert len(metrics) == 1
    assert metrics[0].category == "cpu"


def test_parse_metrics_empty(gauge):
    assert gauge.parse_metrics("no metrics here") == []


def test_normalize_to_ms(gauge):
    assert gauge.normalize_to_ms(PerfMetric("t", 1.5, "s", "latency")) == 1500
    assert gauge.normalize_to_ms(PerfMetric("t", 500, "us", "latency")) == 0.5
    assert gauge.normalize_to_ms(PerfMetric("t", 200, "ms", "latency")) == 200


def test_find_bottlenecks_critical_latency(gauge):
    metrics = [PerfMetric("api", 3000, "ms", "latency")]
    bottlenecks = gauge.find_bottlenecks(metrics)
    assert len(bottlenecks) == 1
    assert bottlenecks[0].severity == "critical"


def test_find_bottlenecks_warning_latency(gauge):
    metrics = [PerfMetric("api", 800, "ms", "latency")]
    bottlenecks = gauge.find_bottlenecks(metrics)
    assert len(bottlenecks) == 1
    assert bottlenecks[0].severity == "warning"


def test_find_bottlenecks_healthy(gauge):
    metrics = [PerfMetric("api", 50, "ms", "latency")]
    bottlenecks = gauge.find_bottlenecks(metrics)
    assert len(bottlenecks) == 0


def test_find_bottlenecks_high_cpu(gauge):
    metrics = [PerfMetric("cpu_usage", 95, "%", "cpu")]
    bottlenecks = gauge.find_bottlenecks(metrics)
    assert len(bottlenecks) == 1
    assert bottlenecks[0].severity == "critical"


def test_compare_metrics(gauge):
    before = [PerfMetric("api", 200, "ms", "latency")]
    after = [PerfMetric("api", 300, "ms", "latency")]
    comparisons = gauge.compare_metrics(before, after)
    assert len(comparisons) == 1
    assert comparisons[0]["status"] == "regression"
    assert comparisons[0]["change_pct"] == 50.0


def test_compare_metrics_improvement(gauge):
    before = [PerfMetric("api", 500, "ms", "latency")]
    after = [PerfMetric("api", 200, "ms", "latency")]
    comparisons = gauge.compare_metrics(before, after)
    assert comparisons[0]["status"] == "improvement"


def test_summarize(gauge):
    metrics = [
        PerfMetric("a", 100, "ms", "latency"),
        PerfMetric("b", 200, "ms", "latency"),
        PerfMetric("c", 512, "MB", "memory"),
    ]
    summary = gauge.summarize(metrics)
    assert summary["total_metrics"] == 3
    assert summary["latency"]["count"] == 2
    assert summary["latency"]["avg"] == 150


@pytest.mark.asyncio
async def test_handle_parses_metrics(gauge):
    context = {"llm": None, "engram": None}
    text = "response_time: 3000ms\ncpu_usage: 92%\nmemory: 1024MB"
    result = await gauge.handle(text, context)
    assert "[Gauge]" in result
    assert "Bottlenecks" in result


@pytest.mark.asyncio
async def test_handle_no_metrics(gauge):
    context = {"llm": None, "engram": None}
    result = await gauge.handle("check performance", context)
    assert "No metrics detected" in result


@pytest.mark.asyncio
async def test_handle_stores_analysis(gauge):
    context = {"llm": None, "engram": None}
    await gauge.handle("latency: 100ms", context)
    assert len(gauge._analyses) == 1
