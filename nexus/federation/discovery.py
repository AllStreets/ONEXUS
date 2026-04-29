"""
Peer discovery -- find other NEXUS instances on the network.
"""
from __future__ import annotations

from typing import Any

import httpx

from nexus.federation.models import PeerInfo
from nexus.federation.peer import PeerRegistry
from nexus.federation.security import FederationSecurity


class PeerDiscovery:
    """Discovers other NEXUS instances on the network."""

    def __init__(
        self,
        registry: PeerRegistry,
        security: FederationSecurity,
        chronicle: Any,
        instance_id: str,
    ):
        self.registry = registry
        self.security = security
        self.chronicle = chronicle
        self.instance_id = instance_id

    def _log_outbound(self, destination: str, summary: str) -> None:
        """Log outbound discovery traffic to Chronicle."""
        if self.chronicle:
            self.chronicle.log("federation.discovery", "outbound_data", {
                "instance_id": self.instance_id,
                "destination": destination,
                "summary": summary[:500],
            })

    async def discover_manual(self, url: str) -> PeerInfo | None:
        """Manually add a peer by URL.

        Hits the peer's /api/system/status endpoint to verify it
        is a NEXUS instance. Returns PeerInfo if valid, None otherwise.
        """
        url = url.rstrip("/")
        self._log_outbound(url, f"Manual discovery probe to {url}")

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{url}/api/system/status")
                resp.raise_for_status()
                data = resp.json()
        except Exception:
            return None

        # Verify it looks like a NEXUS instance
        if "version" not in data:
            return None

        # Generate a peer_id from the URL if not provided
        peer_id = data.get("peer_id", f"nexus-{abs(hash(url)) % (10**12):012x}")

        peer = PeerInfo(
            peer_id=peer_id,
            url=url,
            version=data.get("version", "unknown"),
            instance_name=data.get("instance_name", url),
        )

        # Don't add ourselves
        if peer.peer_id == self.instance_id:
            return None

        self.registry.add_peer(peer)
        self.security.log_federation_event("peer_discovered", peer.peer_id, {
            "method": "manual",
            "url": url,
        })

        return peer

    async def discover_local(self, port_range: tuple[int, int] = (8380, 8400)) -> list[PeerInfo]:
        """Scan local network for NEXUS instances.

        Checks localhost ports in the given range, hitting
        /api/system/status on each. Adds discovered instances to registry.
        """
        discovered: list[PeerInfo] = []
        start_port, end_port = port_range

        for port in range(start_port, end_port + 1):
            url = f"http://localhost:{port}"
            self._log_outbound(url, f"Local discovery scan on port {port}")

            try:
                async with httpx.AsyncClient(timeout=2.0) as client:
                    resp = await client.get(f"{url}/api/system/status")
                    if resp.status_code != 200:
                        continue
                    data = resp.json()
            except Exception:
                continue

            # Verify it's a NEXUS instance
            if "version" not in data:
                continue

            peer_id = data.get("peer_id", f"nexus-local-{port}")

            # Don't add ourselves
            if peer_id == self.instance_id:
                continue

            peer = PeerInfo(
                peer_id=peer_id,
                url=url,
                version=data.get("version", "unknown"),
                instance_name=data.get("instance_name", f"nexus-{port}"),
            )

            self.registry.add_peer(peer)
            discovered.append(peer)

            self.security.log_federation_event("peer_discovered", peer.peer_id, {
                "method": "local_scan",
                "port": port,
            })

        return discovered

    async def heartbeat_all(self) -> dict[str, bool]:
        """Send heartbeat to all known peers, return status per peer."""
        results: dict[str, bool] = {}

        for peer in self.registry.list_peers():
            if peer.status == "disconnected":
                results[peer.peer_id] = False
                continue

            self._log_outbound(peer.url, f"Heartbeat to {peer.instance_name}")

            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.post(
                        f"{peer.url.rstrip('/')}/api/federation/heartbeat",
                        json={
                            "peer_id": self.instance_id,
                        },
                    )
                    if resp.status_code == 200:
                        self.registry.update_heartbeat(peer.peer_id)
                        results[peer.peer_id] = True
                    else:
                        self.registry.mark_stale(peer.peer_id)
                        results[peer.peer_id] = False
            except Exception:
                self.registry.mark_stale(peer.peer_id)
                results[peer.peer_id] = False

        return results

    async def cleanup_stale(self, timeout: int = 300) -> list[str]:
        """Remove peers that haven't responded to heartbeats.

        Returns list of removed peer IDs.
        """
        stale = self.registry.get_stale_peers(timeout_seconds=timeout)
        removed: list[str] = []

        for peer in stale:
            self.security.log_federation_event("peer_stale_removed", peer.peer_id, {
                "last_seen": peer.last_seen,
            })
            self.registry.mark_disconnected(peer.peer_id)
            removed.append(peer.peer_id)

        return removed
