# tests/modules/test_sentinel.py
import pytest
from unittest.mock import AsyncMock
from nexus.modules.sentinel import SentinelModule, ScheduledTask


@pytest.fixture
def sentinel():
    return SentinelModule()


def test_sentinel_attrs(sentinel):
    assert sentinel.name == "sentinel"
    assert sentinel.version == "0.1.0"


def test_register_task(sentinel):
    task = sentinel.register_task("backup", "0 2 * * *", status="ok")
    assert task.name == "backup"
    assert task.schedule == "0 2 * * *"
    assert len(sentinel._tasks) == 1


def test_parse_cron_valid(sentinel):
    result = sentinel.parse_cron("0 2 * * *")
    assert result["minute"] == "0"
    assert result["hour"] == "2"
    assert result["day_of_month"] == "*"


def test_parse_cron_shorthand(sentinel):
    result = sentinel.parse_cron("@daily")
    assert result["minute"] == "0"
    assert result["hour"] == "0"


def test_parse_cron_invalid(sentinel):
    result = sentinel.parse_cron("bad")
    assert "error" in result


def test_explain_cron_daily(sentinel):
    explanation = sentinel.explain_cron("@daily")
    assert "0:00" in explanation or "00" in explanation


def test_explain_cron_every_5_minutes(sentinel):
    explanation = sentinel.explain_cron("*/5 * * * *")
    assert "5 minutes" in explanation


def test_explain_cron_specific_day(sentinel):
    explanation = sentinel.explain_cron("0 9 * * 1")
    assert "Monday" in explanation


def test_parse_task_status(sentinel):
    text = "backup: OK 2024-01-15T14:30:00 (250ms)\ncleanup: FAIL 2024-01-15T15:00:00 (1200ms)"
    tasks = sentinel.parse_task_status(text)
    assert len(tasks) == 2
    assert tasks[0]["name"] == "backup"
    assert tasks[0]["status"] == "ok"
    assert tasks[1]["status"] == "fail"


def test_health_check(sentinel):
    sentinel.register_task("a", "", status="ok")
    sentinel.register_task("b", "", status="failed")
    sentinel.register_task("c", "", status="missed")
    report = sentinel.health_check()
    assert report.total_tasks == 3
    assert report.healthy == 1
    assert report.failed == 1
    assert report.missed == 1


@pytest.mark.asyncio
async def test_handle_cron_explanation(sentinel):
    context = {"llm": None, "engram": None}
    result = await sentinel.handle("0 9 * * 1", context)
    assert "[Sentinel]" in result
    assert "Monday" in result


@pytest.mark.asyncio
async def test_handle_task_status(sentinel):
    context = {"llm": None, "engram": None}
    result = await sentinel.handle("backup: OK 2024-01-15T14:30:00 (250ms)", context)
    assert "[Sentinel]" in result
    assert "Health Report" in result


@pytest.mark.asyncio
async def test_handle_no_input(sentinel):
    context = {"llm": None, "engram": None}
    result = await sentinel.handle("monitor my tasks", context)
    assert "[Sentinel]" in result
