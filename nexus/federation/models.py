"""
Federation data models -- structured representations for peer communication.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class PeerInfo:
    """Represents a known NEXUS peer instance."""
    peer_id: str
    url: str
    version: str
    instance_name: str
    first_seen: str = field(default_factory=_now_iso)
    last_seen: str = field(default_factory=_now_iso)
    status: str = "connected"  # "connected", "stale", "disconnected"
    trust_level: int = 10      # 0-100, peers start low and earn trust

    def to_dict(self) -> dict:
        return {
            "peer_id": self.peer_id,
            "url": self.url,
            "version": self.version,
            "instance_name": self.instance_name,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "status": self.status,
            "trust_level": self.trust_level,
        }

    @classmethod
    def from_dict(cls, data: dict) -> PeerInfo:
        return cls(
            peer_id=data["peer_id"],
            url=data["url"],
            version=data["version"],
            instance_name=data["instance_name"],
            first_seen=data.get("first_seen", _now_iso()),
            last_seen=data.get("last_seen", _now_iso()),
            status=data.get("status", "connected"),
            trust_level=data.get("trust_level", 10),
        )


@dataclass
class PeerCapabilities:
    """Capability listing from a peer -- what modules/agents it offers."""
    peer_id: str
    modules: list[str] = field(default_factory=list)
    agents: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    total_modules: int = 0
    version: str = ""

    def to_dict(self) -> dict:
        return {
            "peer_id": self.peer_id,
            "modules": self.modules,
            "agents": self.agents,
            "categories": self.categories,
            "total_modules": self.total_modules,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: dict) -> PeerCapabilities:
        return cls(
            peer_id=data["peer_id"],
            modules=data.get("modules", []),
            agents=data.get("agents", []),
            categories=data.get("categories", []),
            total_modules=data.get("total_modules", 0),
            version=data.get("version", ""),
        )


@dataclass
class FederationRequest:
    """An inbound or outbound federation request."""
    request_id: str
    source_peer: str
    message: str
    target_module: str | None = None
    timestamp: str = field(default_factory=_now_iso)
    signature: str = ""

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "source_peer": self.source_peer,
            "message": self.message,
            "target_module": self.target_module,
            "timestamp": self.timestamp,
            "signature": self.signature,
        }

    @classmethod
    def from_dict(cls, data: dict) -> FederationRequest:
        return cls(
            request_id=data["request_id"],
            source_peer=data["source_peer"],
            message=data["message"],
            target_module=data.get("target_module"),
            timestamp=data.get("timestamp", _now_iso()),
            signature=data.get("signature", ""),
        )


@dataclass
class FederationResponse:
    """Response to a federation request."""
    request_id: str
    source_peer: str
    response: str
    handled_by: str
    success: bool
    timestamp: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "source_peer": self.source_peer,
            "response": self.response,
            "handled_by": self.handled_by,
            "success": self.success,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict) -> FederationResponse:
        return cls(
            request_id=data["request_id"],
            source_peer=data["source_peer"],
            response=data["response"],
            handled_by=data["handled_by"],
            success=data["success"],
            timestamp=data.get("timestamp", _now_iso()),
        )


@dataclass
class FederationMessage:
    """Generic federation message envelope."""
    type: str
    peer_id: str
    payload: dict = field(default_factory=dict)
    timestamp: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "peer_id": self.peer_id,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict) -> FederationMessage:
        return cls(
            type=data["type"],
            peer_id=data["peer_id"],
            payload=data.get("payload", {}),
            timestamp=data.get("timestamp", _now_iso()),
        )
