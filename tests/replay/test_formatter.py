from __future__ import annotations

import pytest

from nexus.replay.formatter import ReplayFormatter
from nexus.replay.models import (
    TimelineEvent,
    TrustEvent,
    RoutingTrace,
    SystemSnapshot,
    SnapshotDiff,
    SessionReplay,
)


class TestFormatTimeline:
    def test_empty(self):
        fmt = ReplayFormatter()
        result = fmt.format_timeline([])
        assert result == "[no events]"

    def test_with_events(self):
        fmt = ReplayFormatter()
        events = [
            TimelineEvent(
                timestamp="2026-01-01T00:00:00+00:00",
                source="cortex",
                event_type="route_message",
                data={"target": "general"},
            ),
            TimelineEvent(
                timestamp="2026-01-01T00:00:01+00:00",
                source="aegis",
                event_type="trust_adjust",
                data={"module": "general", "delta": 5},
                session_id="sess-001",
            ),
        ]
        result = fmt.format_timeline(events)
        assert "Timeline" in result
        assert "cortex" in result
        assert "route_message" in result
        assert "sess-001" in result
        assert "(2 events)" in result

    def test_payload_summary(self):
        fmt = ReplayFormatter()
        events = [
            TimelineEvent(
                timestamp="2026-01-01T00:00:00+00:00",
                source="cortex",
                event_type="test",
                data={"key": "value"},
            ),
        ]
        result = fmt.format_timeline(events)
        assert "key=value" in result


class TestFormatSnapshot:
    def test_empty_snapshot(self):
        fmt = ReplayFormatter()
        snap = SystemSnapshot(
            timestamp="2026-01-01T00:00:00+00:00",
            active_modules=[],
            trust_scores={},
            total_events=0,
            memory_stats={"working": 0, "episodic": 0, "semantic": 0},
        )
        result = fmt.format_snapshot(snap)
        assert "Snapshot" in result
        assert "(none)" in result

    def test_with_modules(self):
        fmt = ReplayFormatter()
        snap = SystemSnapshot(
            timestamp="2026-01-01T00:00:00+00:00",
            active_modules=[
                {"name": "general", "trust": 65, "tier": "ADVISOR", "allowed": True, "network_allowed": False},
            ],
            trust_scores={"general": 65},
            total_events=42,
            memory_stats={"working": 2, "episodic": 10, "semantic": 5},
        )
        result = fmt.format_snapshot(snap)
        assert "general" in result
        assert "ADVISOR" in result
        assert "ALLOWED" in result
        assert "42" in result
        assert "episodic=10" in result


class TestFormatDiff:
    def test_diff(self):
        fmt = ReplayFormatter()
        diff = SnapshotDiff(
            timestamp_a="2026-01-01T00:00:00+00:00",
            timestamp_b="2026-01-02T00:00:00+00:00",
            trust_changes=[
                TrustEvent(
                    timestamp="2026-01-01T12:00:00+00:00",
                    module="general",
                    old_score=40,
                    new_score=65,
                    reason="good work",
                    tier_change="SKILL -> ADVISOR",
                ),
            ],
            new_modules=["weather"],
            removed_modules=[],
            events_between=25,
            duration="24h 0m",
        )
        result = fmt.format_diff(diff)
        assert "Diff" in result
        assert "SKILL -> ADVISOR" in result
        assert "weather" in result
        assert "25" in result

    def test_diff_no_changes(self):
        fmt = ReplayFormatter()
        diff = SnapshotDiff(
            timestamp_a="2026-01-01T00:00:00+00:00",
            timestamp_b="2026-01-02T00:00:00+00:00",
            trust_changes=[],
            new_modules=[],
            removed_modules=[],
            events_between=0,
            duration="24h 0m",
        )
        result = fmt.format_diff(diff)
        assert "(none)" in result


class TestFormatTrustHistory:
    def test_empty(self):
        fmt = ReplayFormatter()
        result = fmt.format_trust_history([])
        assert result == "[no trust history]"

    def test_with_events(self):
        fmt = ReplayFormatter()
        events = [
            TrustEvent(
                timestamp="2026-01-01T00:00:00+00:00",
                module="general",
                old_score=0,
                new_score=30,
                reason="initial",
            ),
            TrustEvent(
                timestamp="2026-01-01T01:00:00+00:00",
                module="general",
                old_score=30,
                new_score=65,
                reason="promoted",
                tier_change="UNTRUSTED -> ADVISOR",
            ),
        ]
        result = fmt.format_trust_history(events)
        assert "Trust History: general" in result
        assert "0 ->  30" in result
        assert "30 ->  65" in result
        assert "UNTRUSTED -> ADVISOR" in result
        assert "(2 changes)" in result


class TestFormatRoutingTrace:
    def test_empty(self):
        fmt = ReplayFormatter()
        result = fmt.format_routing_trace([])
        assert result == "[no routing traces]"

    def test_with_traces(self):
        fmt = ReplayFormatter()
        traces = [
            RoutingTrace(
                timestamp="2026-01-01T00:00:00+00:00",
                message_preview="What is the weather?",
                target_module="weather",
                keyword_matches=["weather"],
                score=90,
                response_preview="It is sunny.",
                trust_at_time=50,
                duration_ms=12.5,
            ),
        ]
        result = fmt.format_routing_trace(traces)
        assert "Routing Traces" in result
        assert "weather" in result
        assert "What is the weather?" in result
        assert "score=90" in result
        assert "trust=50" in result
        assert "12.5ms" in result


class TestFormatSession:
    def test_session(self):
        fmt = ReplayFormatter()
        session = SessionReplay(
            session_id="sess-001",
            start_time="2026-01-01T00:00:00+00:00",
            end_time="2026-01-01T00:05:00+00:00",
            messages=[
                {"timestamp": "2026-01-01T00:00:00+00:00", "action": "message", "source": "user", "data": {"message": "hello"}},
            ],
            trust_changes=[
                TrustEvent(
                    timestamp="2026-01-01T00:02:00+00:00",
                    module="general",
                    old_score=40,
                    new_score=60,
                    reason="positive feedback",
                    tier_change="SKILL -> ADVISOR",
                ),
            ],
            modules_used=["general", "cortex"],
            total_events=10,
        )
        result = fmt.format_session(session)
        assert "sess-001" in result
        assert "general" in result
        assert "cortex" in result
        assert "hello" in result
        assert "SKILL -> ADVISOR" in result
