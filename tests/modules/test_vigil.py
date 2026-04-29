# tests/modules/test_vigil.py
import pytest
from unittest.mock import AsyncMock
from nexus.agents.vigil import VigilModule, LogEntry, Anomaly


@pytest.fixture
def vigil():
    return VigilModule()


def test_vigil_attrs(vigil):
    assert vigil.name == "vigil"
    assert vigil.version == "0.1.0"


def test_parse_logs_iso_format(vigil):
    logs = (
        "2024-01-15T14:30:00 ERROR [app] Connection refused\n"
        "2024-01-15T14:30:01 INFO [app] Retrying connection\n"
    )
    entries = vigil.parse_logs(logs)
    assert len(entries) == 2
    assert entries[0].level == "ERROR"
    assert entries[0].source == "app"
    assert entries[0].message == "Connection refused"


def test_parse_logs_simple_format(vigil):
    logs = "[ERROR] - Something went wrong\n[INFO] - All good now\n"
    entries = vigil.parse_logs(logs)
    assert len(entries) == 2
    assert entries[0].level == "ERROR"
    assert entries[1].level == "INFO"


def test_parse_logs_empty(vigil):
    assert vigil.parse_logs("") == []
    assert vigil.parse_logs("random text no log format") == []


def test_detect_anomalies_error_patterns(vigil):
    entries = [
        LogEntry(timestamp="2024-01-15T14:30:00", level="ERROR", source="app",
                 message="Connection timeout to host 192.168.1.1", line_number=1),
        LogEntry(timestamp="2024-01-15T14:30:01", level="ERROR", source="app",
                 message="Connection timeout to host 192.168.1.2", line_number=2),
        LogEntry(timestamp="2024-01-15T14:30:02", level="ERROR", source="app",
                 message="Connection timeout to host 192.168.1.3", line_number=3),
        LogEntry(timestamp="2024-01-15T14:30:03", level="INFO", source="app",
                 message="OK", line_number=4),
    ]
    anomalies = vigil.detect_anomalies(entries)
    assert len(anomalies) >= 1


def test_detect_anomalies_high_error_rate(vigil):
    entries = [
        LogEntry(timestamp="t1", level="ERROR", source="x", message="fail", line_number=i)
        for i in range(8)
    ] + [
        LogEntry(timestamp="t2", level="INFO", source="x", message="ok", line_number=9),
        LogEntry(timestamp="t3", level="INFO", source="x", message="ok", line_number=10),
    ]
    anomalies = vigil.detect_anomalies(entries)
    assert any(a.pattern == "High error rate" for a in anomalies)


def test_detect_anomalies_no_errors(vigil):
    entries = [
        LogEntry(timestamp="t1", level="INFO", source="app", message="all good", line_number=1),
    ]
    anomalies = vigil.detect_anomalies(entries)
    assert len(anomalies) == 0


def test_generate_timeline(vigil):
    entries = [
        LogEntry(timestamp="2024-01-15T14:30:00", level="ERROR", source="db",
                 message="Connection lost", line_number=1),
        LogEntry(timestamp="2024-01-15T14:30:05", level="INFO", source="app",
                 message="Running fine", line_number=2),
        LogEntry(timestamp="2024-01-15T14:31:00", level="CRITICAL", source="db",
                 message="Database unreachable", line_number=3),
    ]
    timeline = vigil.generate_timeline(entries)
    assert len(timeline) == 2  # Only ERROR/FATAL/CRITICAL
    assert "Connection lost" in timeline[0]
    assert "Database unreachable" in timeline[1]


@pytest.mark.asyncio
async def test_handle_parses_logs(vigil):
    context = {"llm": None, "engram": None}
    logs = (
        "2024-01-15T14:30:00 ERROR [app] Disk full\n"
        "2024-01-15T14:30:01 ERROR [app] Write failed\n"
        "2024-01-15T14:30:02 INFO [app] Recovered\n"
    )
    result = await vigil.handle(logs, context)
    assert "[Vigil]" in result
    assert "Entries parsed: 3" in result


@pytest.mark.asyncio
async def test_handle_unparseable_no_llm(vigil):
    context = {"llm": None, "engram": None}
    result = await vigil.handle("this is not a log", context)
    assert "Could not parse" in result


@pytest.mark.asyncio
async def test_handle_unparseable_with_llm(vigil):
    mock_llm = AsyncMock()
    mock_llm.complete.return_value = "Analysis: probable disk failure"
    context = {"llm": mock_llm, "engram": None}
    result = await vigil.handle("some weird log data", context)
    assert "[Vigil]" in result
    mock_llm.complete.assert_called_once()


@pytest.mark.asyncio
async def test_handle_stores_analysis(vigil):
    context = {"llm": None, "engram": None}
    await vigil.handle("2024-01-15T14:30:00 ERROR [app] fail\n", context)
    assert len(vigil._analyses) == 1
