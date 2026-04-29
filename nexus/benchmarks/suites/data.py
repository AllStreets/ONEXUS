"""
Data agent benchmark suite.
Tests Flux, Vigil, and Gauge accuracy.
"""
from __future__ import annotations

from nexus.benchmarks.models import BenchmarkCase, BenchmarkSuite

_ERROR_LOG_BLOCK = (
    "2024-01-01T10:00:00 ERROR [app] connection refused to database\n"
    "2024-01-01T10:00:01 ERROR [app] timeout waiting for response\n"
    "2024-01-01T10:00:02 ERROR [app] connection refused to database\n"
    "2024-01-01T10:00:03 INFO [app] retrying connection\n"
    "2024-01-01T10:00:04 ERROR [app] connection refused to database\n"
    "2024-01-01T10:00:05 ERROR [app] connection refused to database\n"
)

_MIXED_LOG_BLOCK = (
    "2024-03-15T08:00:00 INFO [web] server started on port 8080\n"
    "2024-03-15T08:00:01 INFO [web] health check passed\n"
    "2024-03-15T08:00:02 DEBUG [db] connection pool initialized\n"
    "2024-03-15T08:01:00 INFO [web] GET /api/users 200 12ms\n"
    "2024-03-15T08:01:01 INFO [web] GET /api/items 200 8ms\n"
    "2024-03-15T08:01:05 WARNING [db] slow query detected: 2500ms\n"
    "2024-03-15T08:01:10 INFO [web] POST /api/orders 201 45ms\n"
)

_SPIKE_LOG_BLOCK = (
    "2024-06-01T12:00:00 ERROR [auth] invalid token\n"
    "2024-06-01T12:00:01 ERROR [auth] authentication failed\n"
    "2024-06-01T12:00:02 ERROR [auth] invalid token\n"
    "2024-06-01T12:00:03 ERROR [auth] rate limit exceeded\n"
    "2024-06-01T12:00:04 ERROR [auth] invalid token\n"
)

_SIMPLE_LOG = (
    "[ERROR] - disk usage at 95%\n"
    "[ERROR] - disk usage at 97%\n"
    "[WARNING] - swap memory active\n"
    "[ERROR] - disk usage at 99%\n"
)

DATA_SUITE = BenchmarkSuite(
    name="Data Agents",
    description="Benchmark Flux, Vigil, and Gauge accuracy",
    cases=[
        # ----------------------------------------------------------------
        # Flux -- SQL generation
        # ----------------------------------------------------------------
        BenchmarkCase(
            name="flux_count",
            module_name="flux",
            input_message="how many users are in the database?",
            expected_patterns=[r"(?i)SELECT", r"(?i)COUNT"],
        ),
        BenchmarkCase(
            name="flux_select_all",
            module_name="flux",
            input_message="show all records from the users table",
            expected_patterns=[r"(?i)SELECT", r"(?i)\*|users"],
        ),
        BenchmarkCase(
            name="flux_average",
            module_name="flux",
            input_message="what is the average salary?",
            expected_patterns=[r"(?i)SELECT", r"(?i)AVG"],
        ),
        BenchmarkCase(
            name="flux_maximum",
            module_name="flux",
            input_message="what is the maximum price?",
            expected_patterns=[r"(?i)SELECT", r"(?i)MAX"],
        ),
        BenchmarkCase(
            name="flux_minimum",
            module_name="flux",
            input_message="find the minimum score",
            expected_patterns=[r"(?i)SELECT", r"(?i)MIN"],
        ),
        BenchmarkCase(
            name="flux_sum_total",
            module_name="flux",
            input_message="what is the total revenue?",
            expected_patterns=[r"(?i)SELECT", r"(?i)SUM"],
        ),
        BenchmarkCase(
            name="flux_no_match",
            module_name="flux",
            input_message="tell me a joke about databases",
            expected_patterns=[r"(?i)flux|could not|pattern|configure"],
        ),

        # ----------------------------------------------------------------
        # Vigil -- log analysis
        # ----------------------------------------------------------------
        BenchmarkCase(
            name="vigil_error_pattern",
            module_name="vigil",
            input_message=f"analyze log:\n{_ERROR_LOG_BLOCK}",
            expected_patterns=[r"(?i)error|anomal", r"(?i)pattern|repeat|count"],
        ),
        BenchmarkCase(
            name="vigil_mixed_logs",
            module_name="vigil",
            input_message=f"analyze log:\n{_MIXED_LOG_BLOCK}",
            expected_patterns=[r"(?i)vigil|log|analysis|entries"],
        ),
        BenchmarkCase(
            name="vigil_error_spike",
            module_name="vigil",
            input_message=f"analyze log:\n{_SPIKE_LOG_BLOCK}",
            expected_patterns=[r"(?i)error|anomal", r"(?i)pattern|rate"],
        ),
        BenchmarkCase(
            name="vigil_simple_format",
            module_name="vigil",
            input_message=f"analyze log:\n{_SIMPLE_LOG}",
            expected_patterns=[r"(?i)error|anomal|entries"],
        ),
        BenchmarkCase(
            name="vigil_timestamp_parsing",
            module_name="vigil",
            input_message=(
                "analyze:\n"
                "2024-01-15T14:30:00 INFO [api] request received\n"
                "2024-01-15T14:30:01 ERROR [api] null pointer exception\n"
                "2024-01-15T14:30:02 ERROR [api] null pointer exception\n"
                "2024-01-15T14:30:03 INFO [api] request completed\n"
            ),
            expected_patterns=[r"(?i)vigil|log|analysis", r"(?i)error|anomal|entries"],
        ),

        # ----------------------------------------------------------------
        # Gauge -- performance analysis
        # ----------------------------------------------------------------
        BenchmarkCase(
            name="gauge_high_latency",
            module_name="gauge",
            input_message=(
                "analyze performance:\n"
                "response_time_ms: 3500\n"
                "p99_ms: 8000\n"
                "throughput_rps: 50\n"
                "error_rate_pct: 2.5\n"
                "cpu_pct: 85\n"
                "memory_pct: 72\n"
            ),
            expected_patterns=[r"(?i)gauge|performance|metric|bottleneck"],
        ),
        BenchmarkCase(
            name="gauge_healthy_metrics",
            module_name="gauge",
            input_message=(
                "analyze performance:\n"
                "response_time_ms: 45\n"
                "p99_ms: 120\n"
                "throughput_rps: 5000\n"
                "error_rate_pct: 0.01\n"
                "cpu_pct: 25\n"
                "memory_pct: 40\n"
            ),
            expected_patterns=[r"(?i)gauge|performance|metric"],
        ),
    ],
)
