from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, HTTPException, Query, Request

from nexus.api.models import (
    ChronicleEntry,
    ChronicleQueryResponse,
    ChronicleStatsResponse,
)

router = APIRouter(prefix="/api/chronicle", tags=["chronicle"])


def _get_kernel(request: Request):
    return request.app.state.kernel


@router.get("", response_model=ChronicleQueryResponse)
async def query_chronicle(
    request: Request,
    source: str | None = Query(default=None, description="Filter by source"),
    event_type: str | None = Query(default=None, description="Filter by action/event type"),
    since: str | None = Query(default=None, description="ISO timestamp lower bound"),
    until: str | None = Query(default=None, description="ISO timestamp upper bound"),
    limit: int = Query(default=50, ge=1, le=1000),
) -> ChronicleQueryResponse:
    """Query audit entries with optional filters."""
    kernel = _get_kernel(request)
    try:
        rows = kernel.chronicle.query(
            source=source,
            action=event_type,
            since=since,
            until=until,
            limit=limit,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Chronicle query failed: {exc}")

    entries = [ChronicleEntry(**row) for row in rows]
    return ChronicleQueryResponse(entries=entries, count=len(entries))


@router.get("/stats", response_model=ChronicleStatsResponse)
async def chronicle_stats(request: Request) -> ChronicleStatsResponse:
    """Aggregate stats: events by action, by source."""
    kernel = _get_kernel(request)
    try:
        # Fetch a large batch for aggregation
        rows = kernel.chronicle.query(limit=10000)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Chronicle stats failed: {exc}")

    action_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    for row in rows:
        action_counts[row["action"]] += 1
        source_counts[row["source"]] += 1

    return ChronicleStatsResponse(
        total_events=len(rows),
        by_action=dict(action_counts),
        by_source=dict(source_counts),
    )
