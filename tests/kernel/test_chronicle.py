import pytest
from nexus.kernel.chronicle import Chronicle


@pytest.fixture
def chronicle(tmp_config):
    c = Chronicle(tmp_config.db_path)
    c.init_db()
    return c


def test_log_event(chronicle):
    chronicle.log("module.oracle", "trigger_fired", {"trigger": "calendar_check"})
    events = chronicle.query(source="module.oracle")
    assert len(events) == 1
    assert events[0]["action"] == "trigger_fired"
    assert events[0]["payload"]["trigger"] == "calendar_check"


def test_query_by_action(chronicle):
    chronicle.log("cortex", "route", {"target": "general"})
    chronicle.log("cortex", "route", {"target": "oracle"})
    chronicle.log("aegis", "trust_check", {"module": "general", "allowed": True})
    events = chronicle.query(action="route")
    assert len(events) == 2


def test_query_time_range(chronicle):
    chronicle.log("test", "old_event", {})
    events = chronicle.query(source="test")
    assert len(events) == 1
    assert "timestamp" in events[0]


def test_event_has_id_and_timestamp(chronicle):
    chronicle.log("test", "check_fields", {"data": 1})
    events = chronicle.query(source="test")
    e = events[0]
    assert "event_id" in e
    assert "timestamp" in e
    assert len(e["event_id"]) == 12


def test_query_limit(chronicle):
    for i in range(20):
        chronicle.log("bulk", "event", {"i": i})
    events = chronicle.query(source="bulk", limit=5)
    assert len(events) == 5
