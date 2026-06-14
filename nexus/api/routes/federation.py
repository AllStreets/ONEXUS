"""
Federation API routes -- NEXUS-to-NEXUS peer communication endpoints.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from nexus.federation.models import FederationRequest


router = APIRouter(prefix="/api/federation", tags=["federation"])


# ── Request/Response models ────────────────────────────────────────────────

class HandshakeRequest(BaseModel):
    peer_id: str
    instance_name: str = ""
    version: str = ""
    url: str = ""


class RouteRequest(BaseModel):
    request_id: str
    source_peer: str
    message: str
    target_module: str | None = None
    timestamp: str = ""
    signature: str = ""


class HeartbeatRequest(BaseModel):
    peer_id: str
    timestamp: str = ""
    type: str = "heartbeat"


class DiscoverRequest(BaseModel):
    url: str = Field(..., min_length=1, description="URL of the peer to discover")


class DiscoverLocalRequest(BaseModel):
    port_start: int = Field(default=8380, ge=1024, le=65535)
    port_end: int = Field(default=8400, ge=1024, le=65535)


class PeerResponse(BaseModel):
    peer_id: str
    url: str
    version: str
    instance_name: str
    status: str
    trust_level: int
    first_seen: str
    last_seen: str


class PeerListResponse(BaseModel):
    peers: list[PeerResponse]
    count: int


# ── Helpers ────────────────────────────────────────────────────────────────

def _get_kernel(request: Request):
    return request.app.state.kernel


def _get_protocol(request: Request):
    kernel = _get_kernel(request)
    protocol = getattr(kernel, "federation_protocol", None)
    if protocol is None:
        raise HTTPException(
            status_code=503,
            detail="Federation is not enabled on this instance",
        )
    return protocol


def _get_discovery(request: Request):
    kernel = _get_kernel(request)
    discovery = getattr(kernel, "federation_discovery", None)
    if discovery is None:
        raise HTTPException(
            status_code=503,
            detail="Federation is not enabled on this instance",
        )
    return discovery


def _get_sync(request: Request):
    kernel = _get_kernel(request)
    engine = getattr(kernel, "federation_sync_engine", None)
    if engine is None:
        raise HTTPException(
            status_code=503,
            detail="Federation sync is not enabled on this instance",
        )
    return engine


def _get_allowlist(request: Request):
    kernel = _get_kernel(request)
    allowlist = getattr(kernel, "federation_allowlist", None)
    if allowlist is None:
        raise HTTPException(
            status_code=503,
            detail="Federation sync is not enabled on this instance",
        )
    return allowlist


# ── Sync request models ────────────────────────────────────────────────────

class AllowBody(BaseModel):
    peer_id: str
    workspace_id: str


class InboundAtlasBody(BaseModel):
    workspace_id: str
    facts: list[dict] = Field(default_factory=list)


class PushBody(BaseModel):
    peer_id: str
    workspace_id: str


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.post("/handshake")
async def accept_handshake(body: HandshakeRequest, request: Request) -> dict:
    """Accept a handshake from a peer NEXUS instance."""
    protocol = _get_protocol(request)
    try:
        result = await protocol.handle_handshake(body.model_dump())
        return result
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/route")
async def accept_route(body: RouteRequest, request: Request) -> dict:
    """Accept a routed message from a peer for local processing."""
    protocol = _get_protocol(request)

    fed_request = FederationRequest(
        request_id=body.request_id,
        source_peer=body.source_peer,
        message=body.message,
        target_module=body.target_module,
        timestamp=body.timestamp,
        signature=body.signature,
    )

    response = await protocol.handle_incoming(fed_request)
    return response.to_dict()


@router.get("/capabilities")
async def share_capabilities(request: Request) -> dict:
    """Share this instance's capability listing with a peer."""
    protocol = _get_protocol(request)
    return protocol.get_local_capabilities()


@router.post("/heartbeat")
async def accept_heartbeat(body: HeartbeatRequest, request: Request) -> dict:
    """Accept a heartbeat from a peer."""
    protocol = _get_protocol(request)

    if body.type == "disconnect":
        await protocol.disconnect_peer(body.peer_id)
        return {"status": "disconnected", "peer_id": protocol.instance_id}

    result = await protocol.handle_heartbeat(body.model_dump())
    return result


@router.get("/peers", response_model=PeerListResponse)
async def list_peers(request: Request) -> PeerListResponse:
    """List all known peers (local admin only)."""
    protocol = _get_protocol(request)
    peers = protocol.registry.list_peers()
    return PeerListResponse(
        peers=[
            PeerResponse(
                peer_id=p.peer_id,
                url=p.url,
                version=p.version,
                instance_name=p.instance_name,
                status=p.status,
                trust_level=p.trust_level,
                first_seen=p.first_seen,
                last_seen=p.last_seen,
            )
            for p in peers
        ],
        count=len(peers),
    )


@router.post("/discover")
async def discover_manual(body: DiscoverRequest, request: Request) -> dict:
    """Manually discover and add a peer by URL."""
    discovery = _get_discovery(request)
    peer = await discovery.discover_manual(body.url)
    if peer is None:
        raise HTTPException(
            status_code=404,
            detail=f"No NEXUS instance found at {body.url}",
        )
    return peer.to_dict()


@router.post("/discover/local")
async def discover_local(body: DiscoverLocalRequest, request: Request) -> dict:
    """Scan local network for NEXUS instances."""
    discovery = _get_discovery(request)
    peers = await discovery.discover_local(
        port_range=(body.port_start, body.port_end),
    )
    return {
        "discovered": [p.to_dict() for p in peers],
        "count": len(peers),
    }


@router.delete("/peers/{peer_id}")
async def remove_peer(peer_id: str, request: Request) -> dict:
    """Remove a known peer."""
    protocol = _get_protocol(request)
    peer = protocol.registry.get_peer(peer_id)
    if not peer:
        raise HTTPException(status_code=404, detail=f"Peer {peer_id} not found")

    await protocol.disconnect_peer(peer_id)
    protocol.registry.remove_peer(peer_id)
    return {"status": "removed", "peer_id": peer_id}


# ── Workspace sync (N3.2) ──────────────────────────────────────────────────

@router.post("/sync/allow")
async def sync_allow(body: AllowBody, request: Request) -> dict:
    """Allowlist a peer to sync a specific workspace (workspace-scoped)."""
    allowlist = _get_allowlist(request)
    allowlist.allow(body.peer_id, body.workspace_id)
    return {"status": "allowed", "peer_id": body.peer_id,
            "workspace_id": body.workspace_id}


@router.delete("/sync/allow/{peer_id}/{workspace_id}")
async def sync_revoke(peer_id: str, workspace_id: str, request: Request) -> dict:
    """Revoke a peer's sync access for a workspace."""
    allowlist = _get_allowlist(request)
    allowlist.revoke(peer_id, workspace_id)
    return {"status": "revoked", "peer_id": peer_id, "workspace_id": workspace_id}


@router.get("/sync/allowlist")
async def sync_allowlist(request: Request) -> dict:
    """List all (peer, workspace) sync grants."""
    allowlist = _get_allowlist(request)
    return {"allowlist": allowlist.entries()}


@router.post("/sync/atlas")
async def sync_inbound_atlas(body: InboundAtlasBody, request: Request) -> dict:
    """Inbound: merge Atlas facts pushed by a peer into the local workspace."""
    engine = _get_sync(request)
    return await engine.handle_inbound_atlas(body.workspace_id, body.facts)


@router.post("/sync/push")
async def sync_push(body: PushBody, request: Request) -> dict:
    """Outbound: push the local workspace's Atlas facts to an allowlisted peer.

    The engine itself never touches the network — it exports facts and gates
    via Aegis, then hands the push to a transport. The real-network transport
    routes peer HTTP through FederationProtocol._http (KernelHttpClient ->
    aegis.network()), preserving the kernel-import invariant.
    """
    engine = _get_sync(request)
    protocol = _get_protocol(request)
    peer = protocol.registry.get_peer(body.peer_id)

    class _ProtocolPushClient:
        async def push_atlas(self, workspace_id, facts):
            if peer is None or not peer.url:
                return {"delivered": False, "reason": "peer_unknown_or_no_url"}
            from nexus.context import as_agent
            async with as_agent("federation"):
                resp = await protocol._http.post(
                    f"{peer.url.rstrip('/')}/api/federation/sync/atlas",
                    json={"workspace_id": workspace_id, "facts": facts},
                )
            resp.raise_for_status()
            return resp.json()

    return await engine.push_workspace(body.peer_id, body.workspace_id,
                                       _ProtocolPushClient())
