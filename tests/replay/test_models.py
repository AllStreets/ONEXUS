from __future__ import annotations

from nexus.replay.models import (
    TimelineEvent,
    TrustEvent,
    RoutingTrace,
    SystemSnapshot,
    SnapshotDiff,
    SessionReplay,
)


class TestTimelineEvent:
    def test_basic_creation(self):
        ev = TimelineEvent(
            timestamp="2026-01-01T00:00:00+00:00",
            source="cortex",
            event_type="route_message",
            data={"target": "general"},
        )
        assert ev.timestamp == "2026-01-01T00:00:00+00:00"
        assert ev.source == "cortex"
        assert ev.event_type == "route_message"
        assert ev.data == {"target": "general"}
        assert ev.session_id is None

    def test_with_session_id(self):
        ev = TimelineEvent(
            timestamp="2026-01-01T00:00:00+00:00",
            source="cortex",
            event_type="route_message",
            data={},
            session_id="abc123",
        )
        assert ev.session_id == "abc123"


class TestTrustEvent:
    def test_basic(self):
        ev = TrustEvent(
            timestamp="2026-01-01T00:00:00+00:00",
            module="general",
            old_score=40,
            new_score=60,
            reason="good response",
        )
        assert ev.old_score == 40
        assert ev.new_score == 60
        assert ev.tier_change is None

    def test_with_tier_change(self):
        ev = TrustEvent(
            timestamp="2026-01-01T00:00:00+00:00",
            module="general",
            old_score=40,
            new_score=60,
            reason="promoted",
            tier_change="SKILL -> ADVISOR",
        )
        assert ev.tier_change == "SKILL -> ADVISOR"


class TestRoutingTrace:
    def test_creation(self):
        tr = RoutingTrace(
            timestamp="2026-01-01T00:00:00+00:00",
            message_preview="hello world",
            target_module="general",
            keyword_matches=["hello"],
            score=85,
            response_preview="Hi there",
            trust_at_time=50,
            duration_ms=12.5,
        )
        assert tr.target_module == "general"
        assert tr.keyword_matches == ["hello"]
        assert tr.duration_ms == 12.5


class TestSystemSnapshot:
    def test_defaults(self):
        snap = SystemSnapshot(
            timestamp="2026-01-01T00:00:00+00:00",
            active_modules=[],
            trust_scores={},
            total_events=0,
            memory_stats={"working": 0, "episodic": 0, "semantic": 0},
        )
        assert snap.recent_events == []
        assert snap.total_events == 0

    def test_with_data(self):
        snap = SystemSnapshot(
            timestamp="2026-01-01T00:00:00+00:00",
            active_modules=[{"name": "general", "trust": 50, "allowed": True}],
            trust_scores={"general": 50},
            total_events=42,
            memory_stats={"working": 3, "episodic": 10, "semantic": 5},
            recent_events=[
                TimelineEvent(
                    timestamp="2026-01-01T00:00:00+00:00",
                    source="cortex",
                    event_type="test",
                    data={},
                )
            ],
        )
        assert len(snap.active_modules) == 1
        assert snap.trust_scores["general"] == 50
        assert len(snap.recent_events) == 1


class TestSnapshotDiff:
    def test_creation(self):
        diff = SnapshotDiff(
            timestamp_a="2026-01-01T00:00:00+00:00",
            timestamp_b="2026-01-02T00:00:00+00:00",
            trust_changes=[],
            new_modules=["weather"],
            removed_modules=[],
            events_between=15,
            duration="24h 0m",
        )
        assert diff.new_modules == ["weather"]
        assert diff.events_between == 15


class TestSessionReplay:
    def test_creation(self):
        sr = SessionReplay(
            session_id="sess-001",
            start_time="2026-01-01T00:00:00+00:00",
            end_time="2026-01-01T00:05:00+00:00",
            messages=[{"action": "message", "data": {"text": "hello"}}],
            trust_changes=[],
            modules_used=["general"],
            total_events=5,
        )
        assert sr.session_id == "sess-001"
        assert len(sr.messages) == 1
        assert sr.modules_used == ["general"]
