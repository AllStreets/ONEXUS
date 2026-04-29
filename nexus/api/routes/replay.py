from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, Request

from nexus.replay.engine import ReplayEngine
from nexus.replay.models import (
    TimelineEvent,
    TrustEvent,
    RoutingTrace,
    SystemSnapshot,
    SnapshotDiff,
    SessionReplay,
)

router = APIRouter(prefix="/api/replay", tags=["replay"])


def _get_kernel(request: Request):
    return request.app.state.kernel


def _engine(request: Request) -> ReplayEngine:
    kernel = _get_kernel(request)
    return ReplayEngine(
        chronicle=kernel.chronicle,
        aegis=kernel.aegis,
        engram=kernel.engram,
    )


def _serialize(obj: Any) -> Any:
    """Convert dataclass instances to dicts recursively."""
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    if isinstance(obj, list):
        return [_serialize(item) for item in obj]
    return obj


@router.get("/timeline")
async def replay_timeline(
    request: Request,
    start: Optional[str] = Query(default=None, description="ISO timestamp lower bound"),
    end: Optional[str] = Query(default=None, description="ISO timestamp upper bound"),
    source: Optional[str] = Query(default=None, description="Filter by source"),
    limit: int = Query(default=100, ge=1, le=10000),
) -> Dict[str, Any]:
    """Get a timeline of events, optionally filtered."""
    engine = _engine(request)
    try:
        events = await engine.get_timeline(start=start, end=end, source=source, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Timeline query failed: {exc}")
    return {"events": _serialize(events), "count": len(events)}


@router.get("/snapshot/{timestamp:path}")
async def replay_snapshot(
    request: Request,
    timestamp: str,
) -> Dict[str, Any]:
    """Reconstruct system state at a specific point in time."""
    engine = _engine(request)
    try:
        snapshot = await engine.get_snapshot(timestamp)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Snapshot failed: {exc}")
    return _serialize(snapshot)


@router.get("/diff")
async def replay_diff(
    request: Request,
    from_ts: str = Query(..., alias="from", description="Start timestamp (ISO)"),
    to_ts: str = Query(..., alias="to", description="End timestamp (ISO)"),
) -> Dict[str, Any]:
    """Compare system state between two points in time."""
    engine = _engine(request)
    try:
        diff = await engine.diff_snapshots(from_ts, to_ts)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Diff failed: {exc}")
    return _serialize(diff)


@router.get("/trust/{module}")
async def replay_trust_history(
    request: Request,
    module: str,
    limit: int = Query(default=50, ge=1, le=10000),
) -> Dict[str, Any]:
    """Get trust score history for a specific module."""
    engine = _engine(request)
    try:
        events = await engine.get_trust_history(module, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Trust history failed: {exc}")
    return {"module": module, "events": _serialize(events), "count": len(events)}


@router.get("/routing")
async def replay_routing(
    request: Request,
    message_id: Optional[str] = Query(default=None, description="Filter by message ID"),
    limit: int = Query(default=20, ge=1, le=1000),
) -> Dict[str, Any]:
    """Get routing traces showing how messages were routed."""
    engine = _engine(request)
    try:
        traces = await engine.get_routing_trace(message_id=message_id, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Routing trace failed: {exc}")
    return {"traces": _serialize(traces), "count": len(traces)}


@router.get("/session")
async def replay_session(
    request: Request,
    id: Optional[str] = Query(default=None, description="Session ID (omit for most recent)"),
) -> Dict[str, Any]:
    """Replay a full conversation session."""
    engine = _engine(request)
    try:
        session = await engine.get_session(session_id=id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Session replay failed: {exc}")
    return _serialize(session)
