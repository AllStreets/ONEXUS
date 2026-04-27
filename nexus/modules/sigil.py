"""
Sigil — ambient threat radar.
Registers, prioritizes, and tracks threats across categories:
security, reputation, financial, competitive, relationship.
Critical threats bypass normal Pulse priority.
"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import IntEnum
from typing import Any
from nexus.modules.base import NexusModule


class ThreatSeverity(IntEnum):
    CRITICAL = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3
    INFO = 4


@dataclass
class Threat:
    id: str
    category: str
    description: str
    severity: ThreatSeverity
    source: str
    timestamp: str
    acknowledged: bool = False


class SigilModule(NexusModule):
    name = "sigil"
    description = "Ambient threat radar — severity-prioritized early warning system"
    version = "0.1.0"

    def __init__(self):
        self._threats: dict[str, Threat] = {}

    def register_threat(
        self,
        category: str,
        description: str,
        severity: ThreatSeverity,
        source: str,
    ) -> Threat:
        threat_id = uuid.uuid4().hex[:8]
        ts = datetime.now(timezone.utc).isoformat()
        threat = Threat(
            id=threat_id,
            category=category,
            description=description,
            severity=severity,
            source=source,
            timestamp=ts,
        )
        self._threats[threat_id] = threat
        return threat

    def get_threat(self, threat_id: str) -> Threat | None:
        return self._threats.get(threat_id)

    def acknowledge(self, threat_id: str) -> None:
        threat = self._threats.get(threat_id)
        if threat:
            threat.acknowledged = True

    def list_threats(
        self,
        min_severity: ThreatSeverity | None = None,
        unacknowledged_only: bool = False,
    ) -> list[Threat]:
        threats = list(self._threats.values())
        if min_severity is not None:
            threats = [t for t in threats if t.severity <= min_severity]
        if unacknowledged_only:
            threats = [t for t in threats if not t.acknowledged]
        threats.sort(key=lambda t: t.severity)
        return threats

    async def handle(self, message: str, context: dict[str, Any]) -> str:
        threats = self.list_threats(unacknowledged_only=True)
        if not threats:
            return "[Sigil] No active threats. Radar clear."
        lines = [f"[Sigil] {len(threats)} active threat(s):"]
        for t in threats:
            sev_name = t.severity.name
            lines.append(f"  [{sev_name}] {t.category}: {t.description}")
            lines.append(f"    Source: {t.source} | {t.timestamp}")
        return "\n".join(lines)
