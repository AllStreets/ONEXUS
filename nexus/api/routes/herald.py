"""Herald negotiation API (N3.1).

Agent-to-agent negotiation surface: offer -> counter -> accept/reject ->
commit. Every commit is gated by aegis.check_capability() against the
initiator's manifest, and the full transcript is recorded in Chronicle.
Observable in Aurora via the herald.* Pulse stream.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from nexus.modules.herald import HeraldModule
from nexus.society.herald import IllegalTransition

router = APIRouter(prefix="/api/herald", tags=["herald"])


class OfferBody(BaseModel):
    initiator: str
    responder: str
    capability: str
    workspace_id: str | None = None
    terms: dict[str, Any] = {}
    value: float = 0.5


class CounterBody(BaseModel):
    by: str
    terms: dict[str, Any] = {}
    value: float = 0.5


class RespondBody(BaseModel):
    action: str
    by: str
    reason: str = ""


class CommitBody(BaseModel):
    by: str


def _herald(request: Request) -> HeraldModule:
    mod = getattr(request.app.state, "herald_module", None)
    if mod is None:
        mod = HeraldModule()
        request.app.state.herald_module = mod
    return mod


def _ctx(request: Request) -> dict[str, Any]:
    kernel = request.app.state.kernel
    return {"aegis": kernel.aegis, "chronicle": kernel.chronicle,
            "pulse": kernel.pulse, "llm": None}


@router.post("/offer")
async def offer(body: OfferBody, request: Request) -> dict:
    herald = _herald(request)
    try:
        return await herald.open_negotiation(
            _ctx(request), initiator=body.initiator, responder=body.responder,
            capability=body.capability, workspace_id=body.workspace_id,
            terms=body.terms, value=body.value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{negotiation_id}/counter")
async def counter(negotiation_id: str, body: CounterBody, request: Request) -> dict:
    herald = _herald(request)
    try:
        return await herald.counter(_ctx(request), negotiation_id,
                                    by=body.by, terms=body.terms, value=body.value)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown negotiation")
    except IllegalTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{negotiation_id}/respond")
async def respond(negotiation_id: str, body: RespondBody, request: Request) -> dict:
    herald = _herald(request)
    try:
        return await herald.respond(_ctx(request), negotiation_id,
                                    action=body.action, by=body.by, reason=body.reason)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown negotiation")
    except IllegalTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{negotiation_id}/commit")
async def commit(negotiation_id: str, body: CommitBody, request: Request) -> dict:
    herald = _herald(request)
    try:
        return await herald.commit(_ctx(request), negotiation_id, by=body.by)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown negotiation")
    except IllegalTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.get("/{negotiation_id}")
async def get_one(negotiation_id: str, request: Request) -> dict:
    herald = _herald(request)
    neg = herald.get(negotiation_id)
    if neg is None:
        raise HTTPException(status_code=404, detail="unknown negotiation")
    return neg


@router.get("")
async def list_open(request: Request) -> dict:
    herald = _herald(request)
    return {"negotiations": herald.list_open()}
