"""REST endpoints for the PermissionInbox."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from nexus.kernel.aegis import PermissionInbox, PermissionDecision


router = APIRouter(prefix="/api/permissions", tags=["permissions"])


def _get_inbox(request: Request) -> PermissionInbox:
    inbox = getattr(request.app.state, "permission_inbox", None)
    if inbox is None:
        # Lazy-init when surfaces haven't attached one yet
        inbox = PermissionInbox()
        request.app.state.permission_inbox = inbox
    return inbox


class PendingView(BaseModel):
    id: str
    agent_slug: str
    capability: str
    permission_class: str
    workspace_id: str | None
    preview: str = ""
    target: str | None = None


class DecideRequest(BaseModel):
    ticket_id: str
    decision: str  # "allow_once" | "allow_always_in_workspace" | "allow_always_everywhere" | "deny"


@router.get("/pending")
async def pending(request: Request) -> dict:
    inbox = _get_inbox(request)
    return {
        "pending": [
            PendingView(
                id=p.id,
                agent_slug=p.request.agent_slug,
                capability=p.request.capability,
                permission_class=p.request.permission_class,
                workspace_id=p.request.workspace_id,
                preview=p.request.preview,
                target=p.request.target,
            ).model_dump()
            for p in inbox.pending()
        ],
    }


@router.post("/decide")
async def decide(request: Request, body: DecideRequest) -> dict:
    inbox = _get_inbox(request)
    try:
        decision = PermissionDecision(body.decision)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"invalid decision: {body.decision!r}")
    try:
        inbox.answer(body.ticket_id, decision)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"ticket not found: {body.ticket_id!r}")
    return {"ok": True}
