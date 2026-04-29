from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from nexus.kernel.chronicle import Chronicle
from nexus.kernel.aegis import Aegis
from nexus.kernel.engram import Engram
from nexus.replay.models import (
    TimelineEvent,
    TrustEvent,
    RoutingTrace,
    SystemSnapshot,
    SnapshotDiff,
    SessionReplay,
)

# Trust tier boundaries
_TRUST_TIERS = [
    (0, "BLOCKED"),
    (20, "UNTRUSTED"),
    (40, "SKILL"),
    (60, "ADVISOR"),
    (80, "PARTNER"),
    (95, "AUTONOMOUS"),
]


def _trust_tier(score: int) -> str:
    """Return the tier name for a given trust score."""
    tier = "BLOCKED"
    for threshold, name in _TRUST_TIERS:
        if score >= threshold:
            tier = name
    return tier


def _tier_change_label(old_score: int, new_score: int) -> str | None:
    """Return a tier transition label if the tier changed, else None."""
    old_tier = _trust_tier(old_score)
    new_tier = _trust_tier(new_score)
    if old_tier != new_tier:
        return f"{old_tier} -> {new_tier}"
    return None


def _parse_iso(ts: str) -> datetime:
    """Parse an ISO timestamp string to a datetime, handling various formats."""
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        # Fallback: strip trailing Z and retry
        return datetime.fromisoformat(ts.rstrip("Z"))


def _duration_label(start: str, end: str) -> str:
    """Return a human-readable duration between two ISO timestamps."""
    dt_a = _parse_iso(start)
    dt_b = _parse_iso(end)
    delta = abs(dt_b - dt_a)
    total_seconds = int(delta.total_seconds())
    if total_seconds < 60:
        return f"{total_seconds}s"
    if total_seconds < 3600:
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes}m {seconds}s"
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    return f"{hours}h {minutes}m"


class ReplayEngine:
    """Time-travel through NEXUS history using Chronicle audit data."""

    def __init__(self, chronicle: Chronicle, aegis: Aegis, engram: Engram) -> None:
        self.chronicle = chronicle
        self.aegis = aegis
        self.engram = engram

    async def get_timeline(
        self,
        start: str | None = None,
        end: str | None = None,
        source: str | None = None,
        limit: int = 100,
    ) -> list[TimelineEvent]:
        """Get a timeline of events, optionally filtered by time range and source."""
        rows = self.chronicle.query(
            source=source,
            since=start,
            until=end,
            limit=limit,
        )
        events: list[TimelineEvent] = []
        for row in rows:
            payload = row.get("payload", {})
            session_id = payload.get("session_id")
            events.append(
                TimelineEvent(
                    timestamp=row["timestamp"],
                    source=row["source"],
                    event_type=row["action"],
                    data=payload,
                    session_id=session_id,
                )
            )
        return events

    async def get_snapshot(self, timestamp: str) -> SystemSnapshot:
        """Reconstruct system state at a specific point in time.

        Replays all trust adjustments up to *timestamp* to derive
        historical scores, gathers memory statistics, and lists
        active modules at that moment.
        """
        # -- trust scores at timestamp via trust log replay --
        trust_scores: dict[str, int] = {}
        policies = self.aegis.list_policies()
        module_names = [p["module"] for p in policies]

        for module in module_names:
            history = self.aegis.trust_history(module, limit=100_000)
            score = 0
            for entry in history:
                if entry["timestamp"] <= timestamp:
                    score = entry["new_trust"]
                else:
                    break
            trust_scores[module] = score

        # -- active modules (those with a policy) --
        active_modules: list[dict[str, Any]] = []
        for p in policies:
            mod_name = p["module"]
            active_modules.append(
                {
                    "name": mod_name,
                    "trust": trust_scores.get(mod_name, 0),
                    "tier": _trust_tier(trust_scores.get(mod_name, 0)),
                    "allowed": p["allowed"],
                    "network_allowed": p["network_allowed"],
                }
            )

        # -- events up to timestamp --
        all_events = self.chronicle.query(until=timestamp, limit=100_000)
        total_events = len(all_events)

        # -- recent events (last 20 before timestamp) --
        recent_raw = self.chronicle.query(until=timestamp, limit=20)
        recent_events = [
            TimelineEvent(
                timestamp=r["timestamp"],
                source=r["source"],
                event_type=r["action"],
                data=r.get("payload", {}),
                session_id=r.get("payload", {}).get("session_id"),
            )
            for r in recent_raw
        ]

        # -- memory stats --
        memory_stats = self._memory_stats()

        return SystemSnapshot(
            timestamp=timestamp,
            active_modules=active_modules,
            trust_scores=trust_scores,
            total_events=total_events,
            memory_stats=memory_stats,
            recent_events=recent_events,
        )

    async def get_session(self, session_id: str | None = None) -> SessionReplay:
        """Reconstruct a full conversation session.

        Groups events by session_id, shows the message-routing-response
        chain, and includes trust changes that occurred during the session.
        """
        # Fetch all events to find session-related ones
        all_events = self.chronicle.query(limit=100_000)

        if session_id is None:
            # Find the most recent session
            for ev in all_events:
                payload = ev.get("payload", {})
                sid = payload.get("session_id")
                if sid:
                    session_id = sid
                    break
            if session_id is None:
                return SessionReplay(
                    session_id="none",
                    start_time="",
                    end_time="",
                    messages=[],
                    trust_changes=[],
                    modules_used=[],
                    total_events=0,
                )

        session_events = [
            ev
            for ev in all_events
            if ev.get("payload", {}).get("session_id") == session_id
        ]

        if not session_events:
            return SessionReplay(
                session_id=session_id,
                start_time="",
                end_time="",
                messages=[],
                trust_changes=[],
                modules_used=[],
                total_events=0,
            )

        # Sort chronologically (chronicle returns DESC)
        session_events.sort(key=lambda e: e["timestamp"])

        start_time = session_events[0]["timestamp"]
        end_time = session_events[-1]["timestamp"]

        # Build message pairs and collect modules used
        messages: list[dict[str, Any]] = []
        modules_used_set: set[str] = set()

        for ev in session_events:
            payload = ev.get("payload", {})
            if ev["action"] in ("route_message", "message_routed", "message"):
                messages.append(
                    {
                        "timestamp": ev["timestamp"],
                        "action": ev["action"],
                        "source": ev["source"],
                        "data": payload,
                    }
                )
            modules_used_set.add(ev["source"])

        # Trust changes during session window
        trust_changes = await self._trust_changes_between(start_time, end_time)

        return SessionReplay(
            session_id=session_id,
            start_time=start_time,
            end_time=end_time,
            messages=messages,
            trust_changes=trust_changes,
            modules_used=sorted(modules_used_set),
            total_events=len(session_events),
        )

    async def diff_snapshots(
        self, timestamp_a: str, timestamp_b: str
    ) -> SnapshotDiff:
        """Compare system state between two points in time."""
        snap_a = await self.get_snapshot(timestamp_a)
        snap_b = await self.get_snapshot(timestamp_b)

        # Trust changes between the two timestamps
        trust_changes = await self._trust_changes_between(timestamp_a, timestamp_b)

        # Module differences
        modules_a = {m["name"] for m in snap_a.active_modules}
        modules_b = {m["name"] for m in snap_b.active_modules}
        new_modules = sorted(modules_b - modules_a)
        removed_modules = sorted(modules_a - modules_b)

        # Count events between the two timestamps
        earlier = min(timestamp_a, timestamp_b)
        later = max(timestamp_a, timestamp_b)
        between = self.chronicle.query(since=earlier, until=later, limit=100_000)
        events_between = len(between)

        duration = _duration_label(timestamp_a, timestamp_b)

        return SnapshotDiff(
            timestamp_a=timestamp_a,
            timestamp_b=timestamp_b,
            trust_changes=trust_changes,
            new_modules=new_modules,
            removed_modules=removed_modules,
            events_between=events_between,
            duration=duration,
        )

    async def get_trust_history(
        self, module: str, limit: int = 50
    ) -> list[TrustEvent]:
        """Get trust score changes over time for a module."""
        raw = self.aegis.trust_history(module, limit=limit)
        events: list[TrustEvent] = []
        for entry in raw:
            delta = entry["delta"]
            new_score = entry["new_trust"]
            old_score = max(0, min(100, new_score - delta))
            tier_change = _tier_change_label(old_score, new_score)
            events.append(
                TrustEvent(
                    timestamp=entry["timestamp"],
                    module=module,
                    old_score=old_score,
                    new_score=new_score,
                    reason=entry["reason"],
                    tier_change=tier_change,
                )
            )
        return events

    async def get_routing_trace(
        self, message_id: str | None = None, limit: int = 20
    ) -> list[RoutingTrace]:
        """Trace how messages were routed through modules."""
        if message_id:
            rows = self.chronicle.query(action="route_message", limit=limit)
            rows = [
                r
                for r in rows
                if r.get("payload", {}).get("message_id") == message_id
            ]
        else:
            rows = self.chronicle.query(action="route_message", limit=limit)

        traces: list[RoutingTrace] = []
        for row in rows:
            payload = row.get("payload", {})
            module = payload.get("target", payload.get("module", "unknown"))
            message = payload.get("message", payload.get("input", ""))
            response = payload.get("response", payload.get("output", ""))
            keywords = payload.get("keyword_matches", [])
            score = payload.get("score", 0)
            duration = payload.get("duration_ms", 0.0)

            # Derive trust at that time
            trust_at_time = 0
            history = self.aegis.trust_history(module, limit=100_000)
            for entry in history:
                if entry["timestamp"] <= row["timestamp"]:
                    trust_at_time = entry["new_trust"]
                else:
                    break

            traces.append(
                RoutingTrace(
                    timestamp=row["timestamp"],
                    message_preview=message[:120] if message else "",
                    target_module=module,
                    keyword_matches=keywords,
                    score=score,
                    response_preview=response[:120] if response else "",
                    trust_at_time=trust_at_time,
                    duration_ms=duration,
                )
            )
        return traces

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _trust_changes_between(
        self, start: str, end: str
    ) -> list[TrustEvent]:
        """Collect all trust changes across all modules between two timestamps."""
        earlier = min(start, end)
        later = max(start, end)
        changes: list[TrustEvent] = []
        policies = self.aegis.list_policies()
        for p in policies:
            module = p["module"]
            history = self.aegis.trust_history(module, limit=100_000)
            for entry in history:
                if earlier <= entry["timestamp"] <= later:
                    delta = entry["delta"]
                    new_score = entry["new_trust"]
                    old_score = max(0, min(100, new_score - delta))
                    tier_change = _tier_change_label(old_score, new_score)
                    changes.append(
                        TrustEvent(
                            timestamp=entry["timestamp"],
                            module=module,
                            old_score=old_score,
                            new_score=new_score,
                            reason=entry["reason"],
                            tier_change=tier_change,
                        )
                    )
        changes.sort(key=lambda e: e.timestamp)
        return changes

    def _memory_stats(self) -> dict[str, int]:
        """Return counts of memories per tier."""
        stats: dict[str, int] = {"working": 0, "episodic": 0, "semantic": 0}

        # Working memory
        stats["working"] = len(self.engram.working._store)

        # Episodic memory count
        try:
            conn = self.engram.episodic._conn()
            row = conn.execute("SELECT COUNT(*) AS cnt FROM episodic").fetchone()
            stats["episodic"] = row["cnt"] if row else 0
            conn.close()
        except Exception:
            pass

        # Semantic memory count
        try:
            conn = self.engram.semantic._conn()
            row = conn.execute("SELECT COUNT(*) AS cnt FROM semantic").fetchone()
            stats["semantic"] = row["cnt"] if row else 0
            conn.close()
        except Exception:
            pass

        return stats
