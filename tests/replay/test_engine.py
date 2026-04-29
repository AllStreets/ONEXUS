from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from nexus.kernel.chronicle import Chronicle
from nexus.kernel.aegis import Aegis
from nexus.kernel.engram import Engram
from nexus.replay.engine import (
    ReplayEngine,
    _trust_tier,
    _tier_change_label,
    _duration_label,
)
from nexus.replay.models import (
    TimelineEvent,
    TrustEvent,
    SystemSnapshot,
    SnapshotDiff,
    SessionReplay,
    RoutingTrace,
)


@pytest.fixture
def tmp_db(tmp_path):
    """Create a temporary SQLite database path."""
    return str(tmp_path / "nexus_test.db")


@pytest.fixture
def chronicle(tmp_db):
    c = Chronicle(tmp_db)
    c.init_db()
    return c


@pytest.fixture
def aegis(tmp_db):
    a = Aegis(tmp_db)
    a.init_db()
    return a


@pytest.fixture
def engram(tmp_path):
    db = tmp_path / "nexus_test.db"
    e = Engram(db)
    e.init_db()
    return e


@pytest.fixture
def engine(chronicle, aegis, engram):
    return ReplayEngine(chronicle, aegis, engram)


# ------------------------------------------------------------------
# Helper function tests
# ------------------------------------------------------------------


class TestTrustTier:
    def test_blocked(self):
        assert _trust_tier(0) == "BLOCKED"

    def test_untrusted(self):
        assert _trust_tier(20) == "UNTRUSTED"

    def test_skill(self):
        assert _trust_tier(40) == "SKILL"

    def test_advisor(self):
        assert _trust_tier(60) == "ADVISOR"

    def test_partner(self):
        assert _trust_tier(80) == "PARTNER"

    def test_autonomous(self):
        assert _trust_tier(95) == "AUTONOMOUS"
        assert _trust_tier(100) == "AUTONOMOUS"


class TestTierChangeLabel:
    def test_no_change(self):
        assert _tier_change_label(45, 55) is None  # both SKILL

    def test_promotion(self):
        assert _tier_change_label(55, 65) == "SKILL -> ADVISOR"

    def test_demotion(self):
        assert _tier_change_label(65, 35) == "ADVISOR -> UNTRUSTED"


class TestDurationLabel:
    def test_seconds(self):
        assert _duration_label("2026-01-01T00:00:00+00:00", "2026-01-01T00:00:30+00:00") == "30s"

    def test_minutes(self):
        assert _duration_label("2026-01-01T00:00:00+00:00", "2026-01-01T00:05:30+00:00") == "5m 30s"

    def test_hours(self):
        assert _duration_label("2026-01-01T00:00:00+00:00", "2026-01-01T02:15:00+00:00") == "2h 15m"


# ------------------------------------------------------------------
# Engine tests
# ------------------------------------------------------------------


class TestGetTimeline:
    @pytest.mark.asyncio
    async def test_empty_timeline(self, engine):
        events = await engine.get_timeline()
        assert events == []

    @pytest.mark.asyncio
    async def test_timeline_returns_events(self, engine, chronicle):
        chronicle.log("cortex", "route_message", {"target": "general"})
        chronicle.log("aegis", "trust_adjust", {"module": "general", "delta": 5})

        events = await engine.get_timeline()
        assert len(events) == 2
        assert all(isinstance(e, TimelineEvent) for e in events)

    @pytest.mark.asyncio
    async def test_timeline_filter_by_source(self, engine, chronicle):
        chronicle.log("cortex", "route_message", {})
        chronicle.log("aegis", "trust_adjust", {})

        events = await engine.get_timeline(source="cortex")
        assert len(events) == 1
        assert events[0].source == "cortex"

    @pytest.mark.asyncio
    async def test_timeline_with_session_id(self, engine, chronicle):
        chronicle.log("cortex", "message", {"session_id": "sess-001", "text": "hi"})

        events = await engine.get_timeline()
        assert len(events) == 1
        assert events[0].session_id == "sess-001"


class TestGetSnapshot:
    @pytest.mark.asyncio
    async def test_empty_snapshot(self, engine):
        snap = await engine.get_snapshot("2026-12-31T23:59:59+00:00")
        assert isinstance(snap, SystemSnapshot)
        assert snap.total_events == 0
        assert snap.active_modules == []

    @pytest.mark.asyncio
    async def test_snapshot_with_modules(self, engine, aegis, chronicle):
        aegis.set_policy("general", allowed=True)
        chronicle.log("cortex", "test_event", {})

        snap = await engine.get_snapshot("2099-01-01T00:00:00+00:00")
        assert snap.total_events == 1
        assert len(snap.active_modules) == 1
        assert snap.active_modules[0]["name"] == "general"

    @pytest.mark.asyncio
    async def test_snapshot_trust_replay(self, engine, aegis, chronicle):
        aegis.set_policy("general", allowed=True)
        # Simulate trust adjustments
        aegis.adjust_trust("general", 30, "initial setup")
        aegis.adjust_trust("general", 20, "good performance")

        snap = await engine.get_snapshot("2099-01-01T00:00:00+00:00")
        assert snap.trust_scores["general"] == 50

    @pytest.mark.asyncio
    async def test_snapshot_memory_stats(self, engine, engram):
        engram.working.set("key1", "value1")
        engram.working.set("key2", "value2")

        snap = await engine.get_snapshot("2099-01-01T00:00:00+00:00")
        assert snap.memory_stats["working"] == 2


class TestGetSession:
    @pytest.mark.asyncio
    async def test_no_sessions(self, engine):
        session = await engine.get_session()
        assert session.session_id == "none"
        assert session.total_events == 0

    @pytest.mark.asyncio
    async def test_session_by_id(self, engine, chronicle):
        chronicle.log("cortex", "message", {"session_id": "sess-001", "text": "hello"})
        chronicle.log("cortex", "route_message", {"session_id": "sess-001", "target": "general"})
        chronicle.log("cortex", "message", {"session_id": "sess-002", "text": "other"})

        session = await engine.get_session(session_id="sess-001")
        assert session.session_id == "sess-001"
        assert session.total_events == 2

    @pytest.mark.asyncio
    async def test_session_modules_used(self, engine, chronicle):
        chronicle.log("cortex", "message", {"session_id": "s1"})
        chronicle.log("general", "response", {"session_id": "s1"})

        session = await engine.get_session(session_id="s1")
        assert "cortex" in session.modules_used
        assert "general" in session.modules_used


class TestDiffSnapshots:
    @pytest.mark.asyncio
    async def test_empty_diff(self, engine):
        diff = await engine.diff_snapshots(
            "2026-01-01T00:00:00+00:00",
            "2026-01-02T00:00:00+00:00",
        )
        assert isinstance(diff, SnapshotDiff)
        assert diff.events_between == 0
        assert diff.new_modules == []
        assert diff.removed_modules == []

    @pytest.mark.asyncio
    async def test_diff_with_events(self, engine, chronicle):
        chronicle.log("cortex", "event_a", {})
        chronicle.log("cortex", "event_b", {})

        diff = await engine.diff_snapshots(
            "2020-01-01T00:00:00+00:00",
            "2099-01-01T00:00:00+00:00",
        )
        assert diff.events_between == 2


class TestGetTrustHistory:
    @pytest.mark.asyncio
    async def test_no_history(self, engine):
        events = await engine.get_trust_history("nonexistent")
        assert events == []

    @pytest.mark.asyncio
    async def test_trust_history_with_changes(self, engine, aegis):
        aegis.set_policy("general", allowed=True)
        aegis.adjust_trust("general", 30, "setup")
        aegis.adjust_trust("general", 35, "promoted")

        events = await engine.get_trust_history("general")
        assert len(events) == 2
        assert all(isinstance(e, TrustEvent) for e in events)
        assert events[0].old_score == 0
        assert events[0].new_score == 30
        assert events[1].old_score == 30
        assert events[1].new_score == 65

    @pytest.mark.asyncio
    async def test_trust_history_tier_change(self, engine, aegis):
        aegis.set_policy("general", allowed=True)
        aegis.adjust_trust("general", 55, "big jump")  # 0 -> 55 (BLOCKED -> SKILL)

        events = await engine.get_trust_history("general")
        assert len(events) == 1
        assert events[0].tier_change is not None
        assert "SKILL" in events[0].tier_change


class TestGetRoutingTrace:
    @pytest.mark.asyncio
    async def test_no_traces(self, engine):
        traces = await engine.get_routing_trace()
        assert traces == []

    @pytest.mark.asyncio
    async def test_routing_traces(self, engine, chronicle):
        chronicle.log("cortex", "route_message", {
            "target": "general",
            "message": "What is the weather?",
            "keyword_matches": ["weather"],
            "score": 90,
            "response": "It is sunny.",
            "duration_ms": 15.2,
        })

        traces = await engine.get_routing_trace()
        assert len(traces) == 1
        assert isinstance(traces[0], RoutingTrace)
        assert traces[0].target_module == "general"
        assert traces[0].message_preview == "What is the weather?"
        assert traces[0].keyword_matches == ["weather"]
        assert traces[0].score == 90
        assert traces[0].duration_ms == 15.2
