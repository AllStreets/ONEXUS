"""Dreamweaver morning-brief API (N2.2) -- brief + on-demand run."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/dreamweaver", tags=["dreamweaver"])


def _dreamweaver(request: Request):
    """Resolve (or lazily build) the per-app Dreamweaver instance.

    The lifespan attaches app.state.dreamweaver on startup; this fallback
    keeps the routes usable in contexts where the loop hasn't run yet.
    """
    dw = getattr(request.app.state, "dreamweaver", None)
    if dw is None:
        from nexus.synthesis.dreamweaver import Dreamweaver
        kernel = request.app.state.kernel
        dw = Dreamweaver(kernel.config, kernel.engram, kernel.chronicle)
        request.app.state.dreamweaver = dw
    return dw


def _empty_brief() -> dict:
    return {"headline": "No morning brief yet.", "date": None, "topics": [],
            "distilled_facts": 0, "generated_at": None, "skipped": None}


@router.get("/brief")
async def get_brief(request: Request) -> dict:
    dw = _dreamweaver(request)
    return dw.latest_brief() or _empty_brief()


@router.post("/run")
async def run_now(request: Request) -> dict:
    dw = _dreamweaver(request)
    brief = await asyncio.to_thread(dw.run_once)
    if brief.get("skipped") is None:
        from nexus.kernel.pulse import Message
        kernel = request.app.state.kernel
        await kernel.pulse.publish(Message(
            topic="dreamweaver.brief", source="dreamweaver", payload=brief,
        ))
    return brief
