from __future__ import annotations

from nexus.replay.models import (
    TimelineEvent,
    TrustEvent,
    RoutingTrace,
    SystemSnapshot,
    SnapshotDiff,
    SessionReplay,
)
from nexus.replay.engine import _trust_tier


class ReplayFormatter:
    """Formats replay data for terminal and API output."""

    # ------------------------------------------------------------------
    # Timeline
    # ------------------------------------------------------------------

    def format_timeline(self, events: list[TimelineEvent]) -> str:
        """Format timeline as a readable string with timestamps and descriptions."""
        if not events:
            return "[no events]"

        lines: list[str] = []
        lines.append("--- Timeline ---")
        lines.append("")
        for ev in events:
            ts_short = ev.timestamp[:19]
            session_tag = f"  session={ev.session_id}" if ev.session_id else ""
            lines.append(f"  {ts_short}  [{ev.source}] {ev.event_type}{session_tag}")
            if ev.data:
                # Show compact summary of payload keys
                summary = ", ".join(f"{k}={_brief(v)}" for k, v in ev.data.items() if k != "session_id")
                if summary:
                    lines.append(f"               {summary}")
        lines.append("")
        lines.append(f"  ({len(events)} events)")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def format_snapshot(self, snapshot: SystemSnapshot) -> str:
        """Format system snapshot with trust scores and module states."""
        lines: list[str] = []
        lines.append(f"--- Snapshot @ {snapshot.timestamp[:19]} ---")
        lines.append("")

        # Modules table
        lines.append("  Modules:")
        if snapshot.active_modules:
            for m in snapshot.active_modules:
                tier = m.get("tier", _trust_tier(m.get("trust", 0)))
                allowed = "ALLOWED" if m.get("allowed") else "DENIED"
                net = " +NET" if m.get("network_allowed") else ""
                lines.append(
                    f"    {m['name']:<20s}  trust={m['trust']:>3d}  "
                    f"tier={tier:<12s}  {allowed}{net}"
                )
        else:
            lines.append("    (none)")

        lines.append("")
        lines.append(f"  Total events up to this point: {snapshot.total_events}")

        # Memory
        lines.append(f"  Memory: working={snapshot.memory_stats.get('working', 0)}  "
                      f"episodic={snapshot.memory_stats.get('episodic', 0)}  "
                      f"semantic={snapshot.memory_stats.get('semantic', 0)}")

        # Recent events
        if snapshot.recent_events:
            lines.append("")
            lines.append("  Recent events:")
            for ev in snapshot.recent_events[:10]:
                lines.append(f"    {ev.timestamp[:19]}  [{ev.source}] {ev.event_type}")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Diff
    # ------------------------------------------------------------------

    def format_diff(self, diff: SnapshotDiff) -> str:
        """Format diff between two snapshots showing changes."""
        lines: list[str] = []
        lines.append(
            f"--- Diff: {diff.timestamp_a[:19]} -> {diff.timestamp_b[:19]} "
            f"({diff.duration}) ---"
        )
        lines.append("")
        lines.append(f"  Events between: {diff.events_between}")

        if diff.new_modules:
            lines.append(f"  New modules:     {', '.join(diff.new_modules)}")
        if diff.removed_modules:
            lines.append(f"  Removed modules: {', '.join(diff.removed_modules)}")

        if diff.trust_changes:
            lines.append("")
            lines.append("  Trust changes:")
            for tc in diff.trust_changes:
                tier_tag = f"  [{tc.tier_change}]" if tc.tier_change else ""
                lines.append(
                    f"    {tc.timestamp[:19]}  {tc.module}: "
                    f"{tc.old_score} -> {tc.new_score}  "
                    f"({tc.reason}){tier_tag}"
                )
        else:
            lines.append("  Trust changes: (none)")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Trust history
    # ------------------------------------------------------------------

    def format_trust_history(self, events: list[TrustEvent]) -> str:
        """Format trust history with score changes and tier transitions."""
        if not events:
            return "[no trust history]"

        module = events[0].module
        lines: list[str] = []
        lines.append(f"--- Trust History: {module} ---")
        lines.append("")
        for ev in events:
            delta_sign = "+" if ev.new_score >= ev.old_score else ""
            delta = ev.new_score - ev.old_score
            tier_tag = f"  [{ev.tier_change}]" if ev.tier_change else ""
            lines.append(
                f"  {ev.timestamp[:19]}  {ev.old_score:>3d} -> {ev.new_score:>3d}  "
                f"({delta_sign}{delta})  {ev.reason}{tier_tag}"
            )
        lines.append("")
        lines.append(f"  ({len(events)} changes)")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Routing trace
    # ------------------------------------------------------------------

    def format_routing_trace(self, traces: list[RoutingTrace]) -> str:
        """Format routing traces showing message flow."""
        if not traces:
            return "[no routing traces]"

        lines: list[str] = []
        lines.append("--- Routing Traces ---")
        lines.append("")
        for tr in traces:
            lines.append(f"  {tr.timestamp[:19]}  -> {tr.target_module}")
            if tr.message_preview:
                lines.append(f"    msg:      {tr.message_preview[:80]}")
            if tr.keyword_matches:
                lines.append(f"    keywords: {', '.join(tr.keyword_matches)}")
            lines.append(f"    score={tr.score}  trust={tr.trust_at_time}  "
                         f"duration={tr.duration_ms:.1f}ms")
            if tr.response_preview:
                lines.append(f"    response: {tr.response_preview[:80]}")
            lines.append("")
        lines.append(f"  ({len(traces)} traces)")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Session
    # ------------------------------------------------------------------

    def format_session(self, session: SessionReplay) -> str:
        """Format full session replay."""
        lines: list[str] = []
        lines.append(f"--- Session: {session.session_id} ---")
        lines.append(f"  {session.start_time[:19]} -> {session.end_time[:19]}")
        lines.append(f"  Events: {session.total_events}  "
                      f"Modules: {', '.join(session.modules_used) or '(none)'}")
        lines.append("")

        if session.messages:
            lines.append("  Messages:")
            for msg in session.messages:
                ts = msg.get("timestamp", "")[:19]
                action = msg.get("action", "")
                source = msg.get("source", "")
                data = msg.get("data", {})
                preview = data.get("message", data.get("input", ""))
                if isinstance(preview, str) and len(preview) > 80:
                    preview = preview[:80] + "..."
                lines.append(f"    {ts}  [{source}] {action}: {preview}")
            lines.append("")

        if session.trust_changes:
            lines.append("  Trust changes during session:")
            for tc in session.trust_changes:
                tier_tag = f"  [{tc.tier_change}]" if tc.tier_change else ""
                lines.append(
                    f"    {tc.module}: {tc.old_score} -> {tc.new_score}  "
                    f"({tc.reason}){tier_tag}"
                )

        return "\n".join(lines)


def _brief(value: object) -> str:
    """Return a brief string representation of a value for display."""
    s = str(value)
    if len(s) > 40:
        return s[:37] + "..."
    return s
