from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TimelineEvent:
    timestamp: str
    source: str
    event_type: str
    data: dict[str, Any]
    session_id: str | None = None


@dataclass
class TrustEvent:
    timestamp: str
    module: str
    old_score: int
    new_score: int
    reason: str
    tier_change: str | None = None  # e.g., "SKILL -> ADVISOR"


@dataclass
class RoutingTrace:
    timestamp: str
    message_preview: str
    target_module: str
    keyword_matches: list[str]
    score: int
    response_preview: str
    trust_at_time: int
    duration_ms: float


@dataclass
class SystemSnapshot:
    timestamp: str
    active_modules: list[dict[str, Any]]  # name, trust, status
    trust_scores: dict[str, int]
    total_events: int
    memory_stats: dict[str, int]  # counts per tier
    recent_events: list[TimelineEvent] = field(default_factory=list)


@dataclass
class SnapshotDiff:
    timestamp_a: str
    timestamp_b: str
    trust_changes: list[TrustEvent]
    new_modules: list[str]
    removed_modules: list[str]
    events_between: int
    duration: str


@dataclass
class SessionReplay:
    session_id: str
    start_time: str
    end_time: str
    messages: list[dict[str, Any]]  # user message + routed response pairs
    trust_changes: list[TrustEvent]
    modules_used: list[str]
    total_events: int
