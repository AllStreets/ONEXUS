"""
Peer registry -- manages known NEXUS peers with persistence.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nexus.federation.models import PeerInfo, PeerCapabilities


class PeerRegistry:
    """Manages known NEXUS peers."""

    def __init__(self, data_path: Path):
        self.peers: dict[str, PeerInfo] = {}
        self.capabilities: dict[str, PeerCapabilities] = {}
        self.data_path = Path(data_path)
        self.data_path.mkdir(parents=True, exist_ok=True)
        self._peers_file = self.data_path / "federation_peers.json"
        self._caps_file = self.data_path / "federation_capabilities.json"

    def add_peer(self, peer: PeerInfo) -> None:
        """Register a discovered peer."""
        self.peers[peer.peer_id] = peer
        self.save()

    def remove_peer(self, peer_id: str) -> None:
        """Remove a peer."""
        self.peers.pop(peer_id, None)
        self.capabilities.pop(peer_id, None)
        self.save()

    def get_peer(self, peer_id: str) -> PeerInfo | None:
        """Look up a peer."""
        return self.peers.get(peer_id)

    def list_peers(self) -> list[PeerInfo]:
        """List all known peers."""
        return list(self.peers.values())

    def set_capabilities(self, caps: PeerCapabilities) -> None:
        """Store capability listing for a peer."""
        self.capabilities[caps.peer_id] = caps
        self.save()

    def get_capabilities(self, peer_id: str) -> PeerCapabilities | None:
        """Get capability listing for a peer."""
        return self.capabilities.get(peer_id)

    def find_capability(self, module_name: str) -> list[PeerInfo]:
        """Find peers that have a specific module/agent."""
        results = []
        for peer_id, caps in self.capabilities.items():
            if module_name in caps.modules or module_name in caps.agents:
                peer = self.peers.get(peer_id)
                if peer and peer.status != "disconnected":
                    results.append(peer)
        return results

    def update_heartbeat(self, peer_id: str) -> None:
        """Update last-seen timestamp for a peer."""
        peer = self.peers.get(peer_id)
        if peer:
            peer.last_seen = datetime.now(timezone.utc).isoformat()
            peer.status = "connected"
            self.save()

    def get_stale_peers(self, timeout_seconds: int = 300) -> list[PeerInfo]:
        """Find peers that haven't sent a heartbeat recently."""
        now = datetime.now(timezone.utc)
        stale = []
        for peer in self.peers.values():
            if peer.status == "disconnected":
                continue
            try:
                last = datetime.fromisoformat(peer.last_seen)
                if (now - last).total_seconds() > timeout_seconds:
                    stale.append(peer)
            except (ValueError, TypeError):
                stale.append(peer)
        return stale

    def mark_stale(self, peer_id: str) -> None:
        """Mark a peer as stale."""
        peer = self.peers.get(peer_id)
        if peer:
            peer.status = "stale"
            self.save()

    def mark_disconnected(self, peer_id: str) -> None:
        """Mark a peer as disconnected."""
        peer = self.peers.get(peer_id)
        if peer:
            peer.status = "disconnected"
            self.save()

    def save(self) -> None:
        """Persist peer registry to disk."""
        peers_data = {pid: p.to_dict() for pid, p in self.peers.items()}
        self._peers_file.write_text(json.dumps(peers_data, indent=2))

        caps_data = {pid: c.to_dict() for pid, c in self.capabilities.items()}
        self._caps_file.write_text(json.dumps(caps_data, indent=2))

    def load(self) -> None:
        """Load peer registry from disk."""
        if self._peers_file.exists():
            try:
                data = json.loads(self._peers_file.read_text())
                self.peers = {pid: PeerInfo.from_dict(p) for pid, p in data.items()}
            except (json.JSONDecodeError, KeyError):
                self.peers = {}

        if self._caps_file.exists():
            try:
                data = json.loads(self._caps_file.read_text())
                self.capabilities = {
                    pid: PeerCapabilities.from_dict(c) for pid, c in data.items()
                }
            except (json.JSONDecodeError, KeyError):
                self.capabilities = {}
