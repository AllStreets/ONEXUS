"""
Federation protocol -- core NEXUS-to-NEXUS peer communication.
Handles handshakes, capability exchange, message routing, and heartbeats.

Phase 6 (T7): accepts an optional ``http_client`` (a ``KernelHttpClient``)
so that all outbound peer HTTP traffic is routed through ``aegis.network()``
with the ``network.federation.*`` capability.
When ``http_client`` is ``None`` the implementation falls back to a direct
``httpx.AsyncClient`` call (preserves existing test mocking).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import httpx

from nexus.federation.models import (
    FederationMessage,
    FederationRequest,
    FederationResponse,
    PeerCapabilities,
    PeerInfo,
)
from nexus.federation.peer import PeerRegistry
from nexus.federation.security import FederationSecurity

if TYPE_CHECKING:
    from nexus.inference.kernel_http_client import KernelHttpClient


class FederationProtocol:
    """Handles NEXUS-to-NEXUS peer communication."""

    # Message types
    HANDSHAKE = "federation.handshake"
    CAPABILITY_EXCHANGE = "federation.capabilities"
    ROUTE_REQUEST = "federation.route"
    ROUTE_RESPONSE = "federation.route_response"
    HEARTBEAT = "federation.heartbeat"
    DISCONNECT = "federation.disconnect"

    def __init__(
        self,
        instance_id: str,
        instance_name: str,
        version: str,
        registry: PeerRegistry,
        security: FederationSecurity,
        cortex: Any,
        chronicle: Any,
        enabled: bool = False,
        http_client: "KernelHttpClient | None" = None,
    ):
        self.instance_id = instance_id
        self.instance_name = instance_name
        self.version = version
        self.registry = registry
        self.security = security
        self.cortex = cortex
        self.chronicle = chronicle
        self.enabled = enabled
        self._http = http_client

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _log_outbound(self, destination: str, summary: str) -> None:
        """Log all outbound federation data to Chronicle."""
        if self.chronicle:
            self.chronicle.log("federation", "outbound_data", {
                "instance_id": self.instance_id,
                "destination": destination,
                "summary": summary[:500],
            })

    async def handshake(self, peer_url: str) -> PeerInfo:
        """Initiate handshake with a peer NEXUS instance.

        Sends this instance's identity to the peer and receives theirs.
        Verifies the peer is a valid NEXUS instance by checking for the
        expected response format. Logs the handshake to Chronicle.
        """
        if not self.enabled:
            raise RuntimeError("Federation is not enabled on this instance")

        handshake_payload = {
            "peer_id": self.instance_id,
            "instance_name": self.instance_name,
            "version": self.version,
            "url": "",  # filled by caller or discovery
        }

        self._log_outbound(peer_url, f"Handshake initiation to {peer_url}")

        if self._http is not None:
            resp = await self._http.post(
                f"{peer_url.rstrip('/')}/api/federation/handshake",
                json=handshake_payload,
            )
            resp.raise_for_status()
            data = resp.json()
        else:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{peer_url.rstrip('/')}/api/federation/handshake",
                    json=handshake_payload,
                )
                resp.raise_for_status()
                data = resp.json()

        # Validate the response contains required fields
        required = {"peer_id", "instance_name", "version"}
        if not required.issubset(data.keys()):
            raise ValueError(f"Invalid handshake response from {peer_url}: missing fields")

        peer = PeerInfo(
            peer_id=data["peer_id"],
            url=peer_url.rstrip("/"),
            version=data["version"],
            instance_name=data["instance_name"],
            first_seen=self._now_iso(),
            last_seen=self._now_iso(),
            status="connected",
            trust_level=data.get("trust_level", 10),
        )

        self.registry.add_peer(peer)
        self.security.log_federation_event("handshake_complete", peer.peer_id, {
            "peer_name": peer.instance_name,
            "peer_version": peer.version,
        })

        return peer

    async def handle_handshake(self, payload: dict) -> dict:
        """Handle an incoming handshake request from a peer.

        Registers the peer and returns this instance's identity.
        """
        if not self.enabled:
            raise RuntimeError("Federation is not enabled on this instance")

        peer_id = payload.get("peer_id", "")
        if not peer_id:
            raise ValueError("Handshake missing peer_id")

        peer = PeerInfo(
            peer_id=peer_id,
            url=payload.get("url", ""),
            version=payload.get("version", "unknown"),
            instance_name=payload.get("instance_name", "unknown"),
            first_seen=self._now_iso(),
            last_seen=self._now_iso(),
            status="connected",
            trust_level=10,
        )

        self.registry.add_peer(peer)
        self.security.log_federation_event("handshake_received", peer_id, {
            "peer_name": peer.instance_name,
        })

        return {
            "peer_id": self.instance_id,
            "instance_name": self.instance_name,
            "version": self.version,
            "trust_level": 10,
        }

    async def exchange_capabilities(self, peer: PeerInfo) -> PeerCapabilities:
        """Exchange module/agent capability listings with a peer.

        Shares what modules/agents are available on the peer.
        Does NOT share memory, trust scores, or audit data.
        """
        if not self.enabled:
            raise RuntimeError("Federation is not enabled on this instance")

        self._log_outbound(peer.url, f"Capability exchange with {peer.instance_name}")

        if self._http is not None:
            resp = await self._http.get(
                f"{peer.url.rstrip('/')}/api/federation/capabilities",
            )
            resp.raise_for_status()
            data = resp.json()
        else:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{peer.url.rstrip('/')}/api/federation/capabilities",
                )
                resp.raise_for_status()
                data = resp.json()

        caps = PeerCapabilities.from_dict({
            "peer_id": peer.peer_id,
            **data,
        })

        self.registry.set_capabilities(caps)
        self.security.log_federation_event("capabilities_exchanged", peer.peer_id, {
            "modules_count": caps.total_modules,
        })

        return caps

    def get_local_capabilities(self) -> dict:
        """Return this instance's capability listing for sharing.

        Only shares module names and counts -- no internal state.
        """
        modules = self.cortex.list_modules() if self.cortex else []
        return {
            "peer_id": self.instance_id,
            "modules": modules,
            "agents": [],
            "categories": [],
            "total_modules": len(modules),
            "version": self.version,
        }

    async def route_to_peer(self, peer_id: str, message: str,
                            target_module: str | None = None) -> str:
        """Route a message to a peer NEXUS instance for processing.

        Logs all outbound data to Chronicle, sends via HTTP, returns response.
        """
        if not self.enabled:
            raise RuntimeError("Federation is not enabled on this instance")

        peer = self.registry.get_peer(peer_id)
        if not peer:
            raise ValueError(f"Unknown peer: {peer_id}")

        if peer.status == "disconnected":
            raise ValueError(f"Peer {peer_id} is disconnected")

        request = FederationRequest(
            request_id=uuid.uuid4().hex[:12],
            source_peer=self.instance_id,
            message=message,
            target_module=target_module,
            timestamp=self._now_iso(),
        )

        # Sign the request
        request.signature = self.security.sign_request(request)

        self._log_outbound(peer.url, f"Route request to {peer.instance_name}: {message[:100]}")

        if self._http is not None:
            resp = await self._http.post(
                f"{peer.url.rstrip('/')}/api/federation/route",
                json=request.to_dict(),
            )
            resp.raise_for_status()
            data = resp.json()
        else:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{peer.url.rstrip('/')}/api/federation/route",
                    json=request.to_dict(),
                )
                resp.raise_for_status()
                data = resp.json()

        fed_response = FederationResponse.from_dict(data)

        self.security.log_federation_event("route_response_received", peer_id, {
            "request_id": request.request_id,
            "handled_by": fed_response.handled_by,
            "success": fed_response.success,
        })

        return fed_response.response

    async def handle_incoming(self, request: FederationRequest) -> FederationResponse:
        """Handle an incoming federation request from a peer.

        Verifies peer is known and trusted, checks rate limits,
        routes through local Cortex, logs to Chronicle, returns response.
        """
        if not self.enabled:
            return FederationResponse(
                request_id=request.request_id,
                source_peer=self.instance_id,
                response="Federation is not enabled on this instance",
                handled_by="federation",
                success=False,
            )

        peer = self.registry.get_peer(request.source_peer)
        if not peer:
            self.security.log_federation_event("unknown_peer_request", request.source_peer, {
                "request_id": request.request_id,
            })
            return FederationResponse(
                request_id=request.request_id,
                source_peer=self.instance_id,
                response="Unknown peer -- handshake required",
                handled_by="federation",
                success=False,
            )

        # Rate limit check
        if not self.security.check_rate_limit(request.source_peer):
            return FederationResponse(
                request_id=request.request_id,
                source_peer=self.instance_id,
                response="Rate limit exceeded",
                handled_by="federation",
                success=False,
            )

        # Verify signature if present
        if request.signature:
            if not self.security.verify_request(request, request.signature, peer):
                self.security.log_federation_event("signature_invalid", request.source_peer, {
                    "request_id": request.request_id,
                })
                return FederationResponse(
                    request_id=request.request_id,
                    source_peer=self.instance_id,
                    response="Invalid signature",
                    handled_by="federation",
                    success=False,
                )

        # Log the inbound request
        self.security.log_federation_event("inbound_request", request.source_peer, {
            "request_id": request.request_id,
            "message_preview": request.message[:100],
            "target_module": request.target_module,
        })

        # Route through local Cortex
        try:
            response_text = await self.cortex.process(request.message)
            handled_by = self.cortex._select_module(request.message) if self.cortex else "unknown"
        except Exception as exc:
            self.security.log_federation_event("route_error", request.source_peer, {
                "request_id": request.request_id,
                "error": str(exc),
            })
            return FederationResponse(
                request_id=request.request_id,
                source_peer=self.instance_id,
                response=f"Error processing request: {str(exc)}",
                handled_by="federation",
                success=False,
            )

        # Log the response
        self.security.log_federation_event("inbound_response", request.source_peer, {
            "request_id": request.request_id,
            "handled_by": handled_by,
            "response_preview": response_text[:200],
        })

        # Update peer heartbeat
        self.registry.update_heartbeat(request.source_peer)

        return FederationResponse(
            request_id=request.request_id,
            source_peer=self.instance_id,
            response=response_text,
            handled_by=handled_by,
            success=True,
        )

    async def send_heartbeat(self, peer_id: str) -> bool:
        """Send heartbeat to a specific peer. Returns True if peer responds."""
        if not self.enabled:
            return False

        peer = self.registry.get_peer(peer_id)
        if not peer:
            return False

        self._log_outbound(peer.url, f"Heartbeat to {peer.instance_name}")

        try:
            hb_payload = {"peer_id": self.instance_id, "timestamp": self._now_iso()}
            if self._http is not None:
                resp = await self._http.post(
                    f"{peer.url.rstrip('/')}/api/federation/heartbeat",
                    json=hb_payload,
                )
                resp.raise_for_status()
            else:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.post(
                        f"{peer.url.rstrip('/')}/api/federation/heartbeat",
                        json=hb_payload,
                    )
                    resp.raise_for_status()
            self.registry.update_heartbeat(peer_id)
            return True
        except Exception:
            self.registry.mark_stale(peer_id)
            return False

    async def handle_heartbeat(self, payload: dict) -> dict:
        """Handle an incoming heartbeat or disconnect from a peer."""
        peer_id = payload.get("peer_id", "")
        msg_type = payload.get("type", "heartbeat")

        if not peer_id or peer_id not in self.registry.peers:
            return {"status": "unknown_peer", "peer_id": self.instance_id}

        if msg_type == "disconnect":
            self.registry.mark_disconnected(peer_id)
            self.security.log_federation_event("peer_disconnected", peer_id, {})
            return {"status": "disconnected", "peer_id": self.instance_id}

        self.registry.update_heartbeat(peer_id)
        return {"status": "ok", "peer_id": self.instance_id}

    async def disconnect_peer(self, peer_id: str) -> None:
        """Gracefully disconnect from a peer."""
        peer = self.registry.get_peer(peer_id)
        if not peer:
            return

        if self.enabled and peer.url:
            self._log_outbound(peer.url, f"Disconnect from {peer.instance_name}")
            try:
                disc_payload = {"peer_id": self.instance_id, "type": "disconnect"}
                if self._http is not None:
                    await self._http.post(
                        f"{peer.url.rstrip('/')}/api/federation/heartbeat",
                        json=disc_payload,
                    )
                else:
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        await client.post(
                            f"{peer.url.rstrip('/')}/api/federation/heartbeat",
                            json=disc_payload,
                        )
            except Exception:
                pass

        self.registry.mark_disconnected(peer_id)
        self.security.log_federation_event("disconnect", peer_id, {})
