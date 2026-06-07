from __future__ import annotations

import time
from collections import defaultdict
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/cockpit", tags=["cockpit"])


def _kernel(request: Request):
    return getattr(request.app.state, "kernel", None)


@router.get("/pulse-rate")
async def pulse_rate(request: Request, window_seconds: int = 60) -> dict:
    """Count chronicle events per topic over the window; returns 12 points (1 every 5s)."""
    kernel = _kernel(request)
    if kernel is None:
        return {"points": []}
    try:
        events = kernel.chronicle.query(limit=2000)
    except Exception:
        return {"points": []}
    buckets: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    bucket_size = max(1, window_seconds // 12)
    now = time.time()
    for ev in events:
        ts_str = ev.get("timestamp")
        if not ts_str:
            continue
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00")).timestamp()
        except Exception:
            continue
        age = now - ts
        if age < 0 or age > window_seconds:
            continue
        bucket = int(age // bucket_size)
        source = ev.get("source", "")
        action = ev.get("action", "")
        key = f"{source}.{action}" if source else action
        buckets[bucket][key] += 1
    points = []
    for i in range(12):
        b = buckets.get(i, {})
        points.append({
            "ts_offset": i * bucket_size,
            "cortex_route": b.get("cortex.route", 0),
            "aegis_check": b.get("aegis.check", 0) + b.get("aegis.trust_change", 0),
            "chronicle": sum(b.values()),
        })
    return {"points": list(reversed(points))}


@router.get("/snapshot")
async def snapshot(request: Request) -> dict:
    """One-shot bundle for all 6 Cockpit panels."""
    kernel = _kernel(request)
    out: dict[str, Any] = {
        "pulse": [],
        "residents": [],
        "trust_gradient": [],
        "last_route": None,
        "chronicle_tail": [],
        "network": [],
        "engram_stats": {},
    }
    if kernel is None:
        return out
    try:
        events = kernel.chronicle.query(limit=20)
        out["chronicle_tail"] = events
        out["last_route"] = next(
            (e for e in events if e.get("action") == "route"), None
        )
    except Exception:
        pass
    try:
        out["trust_gradient"] = kernel.aegis.list_policies()
    except Exception:
        pass
    try:
        out["residents"] = kernel.cortex.list_modules()
    except Exception:
        pass
    return out
