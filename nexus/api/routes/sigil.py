"""Sigil detections API -- queryable threat-radar log (N1.1)."""
from __future__ import annotations

from fastapi import APIRouter, Query, Request

router = APIRouter(prefix="/api/sigil", tags=["sigil"])


@router.get("/detections")
async def list_detections(
    request: Request,
    rule: str | None = Query(default=None, description="Filter by detection rule"),
    limit: int = Query(default=50, ge=1, le=500),
) -> dict:
    """Detections are Chronicle records (source=sigil, action=detection) --
    the audit log is the single durable store, per the N1 invariants."""
    kernel = request.app.state.kernel
    rows = kernel.chronicle.query(source="sigil", action="detection", limit=limit)
    detections = []
    for r in rows:
        entry = {"event_id": r["event_id"], "timestamp": r["timestamp"],
                 **(r["payload"] or {})}
        if rule is not None and entry.get("rule") != rule:
            continue
        detections.append(entry)
    return {"detections": detections, "count": len(detections)}
