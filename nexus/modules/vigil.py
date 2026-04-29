"""
Vigil -- log analysis and incident diagnosis agent.
Analyzes log files for anomaly patterns, generates incident timelines,
and identifies probable root causes.

Inspired by:
  - elastic/sysgrok (Apache 2.0) — LLM-driven system analysis
  - stratosphereips/llm-log-analyzer (MIT) — local LLM log analysis
  - trawick/stacktraces.py (MIT) — Python stack trace analysis tools
"""
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any
from nexus.modules.base import NexusModule


@dataclass
class LogEntry:
    timestamp: str
    level: str
    source: str
    message: str
    line_number: int


@dataclass
class Anomaly:
    severity: str
    pattern: str
    count: int
    first_seen: str
    description: str


class VigilModule(NexusModule):
    name = "vigil"
    description = "Log analysis agent -- detects anomaly patterns, generates incident timelines, identifies root causes"
    version = "0.1.0"

    def __init__(self):
        self._analyses: list[dict[str, Any]] = []

    @staticmethod
    def parse_logs(text: str) -> list[LogEntry]:
        """Parse common log formats into structured entries."""
        entries: list[LogEntry] = []
        patterns = [
            # ISO timestamp + level: 2024-01-15T14:30:00 ERROR [app] message
            r'^(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?)\s+(DEBUG|INFO|WARN(?:ING)?|ERROR|FATAL|CRITICAL)\s+\[?(\w+)\]?\s+(.+)$',
            # Syslog-style: Jan 15 14:30:00 hostname app: message
            r'^(\w{3}\s+\d+\s+\d{2}:\d{2}:\d{2})\s+(\w+)\s+(\w+):\s+(.+)$',
            # Simple: [ERROR] message or ERROR: message
            r'^\[?(DEBUG|INFO|WARN(?:ING)?|ERROR|FATAL|CRITICAL)\]?\s*[:\-]\s*(.+)$',
        ]

        for i, line in enumerate(text.split('\n'), 1):
            stripped = line.strip()
            if not stripped:
                continue

            for pattern in patterns:
                match = re.match(pattern, stripped)
                if match:
                    groups = match.groups()
                    if len(groups) == 4:
                        entries.append(LogEntry(
                            timestamp=groups[0], level=groups[1].upper(),
                            source=groups[2], message=groups[3], line_number=i,
                        ))
                    elif len(groups) == 2:
                        entries.append(LogEntry(
                            timestamp="", level=groups[0].upper(),
                            source="", message=groups[1], line_number=i,
                        ))
                    break

        return entries

    @staticmethod
    def detect_anomalies(entries: list[LogEntry]) -> list[Anomaly]:
        """Find anomaly patterns in log entries."""
        anomalies: list[Anomaly] = []

        # Count errors by type
        error_entries = [e for e in entries if e.level in ("ERROR", "FATAL", "CRITICAL")]
        if error_entries:
            error_patterns: Counter[str] = Counter()
            for e in error_entries:
                # Normalize: strip numbers and IDs
                normalized = re.sub(r'\b\d+\b', 'N', e.message)
                normalized = re.sub(r'\b[0-9a-f]{8,}\b', 'ID', normalized, flags=re.IGNORECASE)
                error_patterns[normalized[:80]] += 1

            for pattern, count in error_patterns.most_common(10):
                severity = "critical" if count > 10 else "warning" if count > 3 else "info"
                first = next(e for e in error_entries if re.sub(r'\b\d+\b', 'N', e.message)[:80].startswith(pattern[:40]))
                anomalies.append(Anomaly(
                    severity=severity, pattern=pattern, count=count,
                    first_seen=first.timestamp,
                    description=f"Error pattern repeated {count} time(s)",
                ))

        # Detect error spike
        if entries:
            total = len(entries)
            errors = len(error_entries)
            error_rate = errors / total if total > 0 else 0
            if error_rate > 0.3:
                anomalies.append(Anomaly(
                    severity="critical", pattern="High error rate",
                    count=errors, first_seen=entries[0].timestamp,
                    description=f"Error rate is {error_rate*100:.0f}% ({errors}/{total} entries)",
                ))

        return anomalies

    @staticmethod
    def generate_timeline(entries: list[LogEntry]) -> list[str]:
        """Generate incident timeline from log entries."""
        timeline: list[str] = []
        error_entries = [e for e in entries if e.level in ("ERROR", "FATAL", "CRITICAL")]

        for e in error_entries[:20]:
            ts = e.timestamp if e.timestamp else f"Line {e.line_number}"
            timeline.append(f"  {ts} [{e.level}] {e.source}: {e.message[:100]}")

        return timeline

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        llm = context.get("llm")
        engram = context.get("engram")

        entries = self.parse_logs(message)

        if not entries:
            if llm:
                prompt = (
                    "Analyze these logs for anomalies, errors, and patterns. "
                    "Identify the root cause and create a timeline.\n\n"
                    f"Logs:\n{message[:4000]}"
                )
                try:
                    return f"[Vigil] {await llm.complete(prompt)}"
                except Exception:
                    pass
            return "[Vigil] Could not parse log format. Supported: ISO timestamps, syslog, [LEVEL] format."

        anomalies = self.detect_anomalies(entries)
        timeline = self.generate_timeline(entries)

        # LLM root cause analysis
        llm_analysis = ""
        if llm and anomalies:
            prompt = (
                "Given these log anomalies, determine the most likely root cause:\n\n"
                + "\n".join(f"- {a.pattern} ({a.count}x)" for a in anomalies[:5])
                + f"\n\nTimeline:\n" + "\n".join(timeline[:10])
                + "\n\nProvide: 1) Root cause 2) Impact 3) Remediation steps"
            )
            try:
                llm_analysis = await llm.complete(prompt)
            except Exception:
                pass

        # Stats
        level_counts = Counter(e.level for e in entries)
        self._analyses.append({"entries": len(entries), "anomalies": len(anomalies)})

        if engram:
            try:
                engram.episodic.store(
                    f"Log analysis: {len(entries)} entries, {len(anomalies)} anomalies, "
                    f"{level_counts.get('ERROR', 0)} errors",
                    source=self.name,
                )
            except Exception:
                pass

        lines = [f"[Vigil] Log Analysis"]
        lines.append(f"  Entries parsed: {len(entries)}")
        for level in ["CRITICAL", "FATAL", "ERROR", "WARNING", "WARN", "INFO", "DEBUG"]:
            if level_counts.get(level, 0) > 0:
                lines.append(f"    {level}: {level_counts[level]}")

        if anomalies:
            lines.append(f"\n  Anomalies Detected ({len(anomalies)}):")
            for a in anomalies:
                marker = "!!!" if a.severity == "critical" else "! " if a.severity == "warning" else "  "
                lines.append(f"    {marker} [{a.severity.upper()}] {a.description}")
                lines.append(f"        Pattern: {a.pattern[:80]}")
                if a.first_seen:
                    lines.append(f"        First seen: {a.first_seen}")

        if timeline:
            lines.append(f"\n  Error Timeline:")
            lines.extend(timeline[:10])

        if llm_analysis:
            lines.append(f"\n  -- Root Cause Analysis --")
            lines.append(f"  {llm_analysis[:1000]}")

        return "\n".join(lines)
