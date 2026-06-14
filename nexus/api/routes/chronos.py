"""Chronos timeline + counterfactual API (N2.2).

Read-only history analysis over Chronicle's recorded decisions: a
deterministic decision-DAG reconstruction (timeline with branch points)
and counterfactual flips that prune the actions that depended on a node.
The kernel is never re-run.
"""
from __future__ import annotations

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

from nexus.synthesis.chronos import Chronos

router = APIRouter(prefix="/api/chronos", tags=["chronos"])


class CounterfactualBody(BaseModel):
    event_id: str | None = None
    module: str | None = None
    action: str | None = None


@router.get("/timeline")
async def timeline(request: Request,
                   limit: int = Query(default=200, ge=1, le=2000)) -> dict:
    kernel = request.app.state.kernel
    rows = Chronos(kernel.chronicle).timeline(limit=limit)
    return {"timeline": rows, "count": len(rows)}


@router.post("/counterfactual")
async def counterfactual(request: Request, body: CounterfactualBody) -> dict:
    kernel = request.app.state.kernel
    chronos = Chronos(kernel.chronicle)
    if body.module and body.action:
        return chronos.counterfactual_by(module=body.module, action=body.action)
    return chronos.counterfactual(body.event_id or "")
