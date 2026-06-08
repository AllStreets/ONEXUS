"""REST endpoints for the PermissionInbox."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from nexus.kernel.aegis import PermissionInbox, PermissionDecision, PermissionRequest


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


@router.websocket("/ws")
async def permissions_ws(websocket: WebSocket):
    """WebSocket push stream: pending permission tickets, refreshed every 2s."""
    await websocket.accept()
    try:
        while True:
            inbox = _get_inbox(websocket)
            pending = inbox.pending()
            await websocket.send_json({
                "pending": [
                    {
                        "id": p.id,
                        "agent_slug": p.request.agent_slug,
                        "capability": p.request.capability,
                        "permission_class": p.request.permission_class,
                        "workspace_id": p.request.workspace_id,
                        "preview": p.request.preview,
                    }
                    for p in pending
                ],
            })
            await asyncio.sleep(2.0)
    except WebSocketDisconnect:
        return


@router.post("/decide")
async def decide(request: Request, body: DecideRequest) -> dict:
    inbox = _get_inbox(request)
    try:
        decision = PermissionDecision(body.decision)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"invalid decision: {body.decision!r}")
    # Capture ticket details before answering (the inbox cleans up after answer)
    ticket = inbox._tickets.get(body.ticket_id)
    ticket_data = None
    if ticket is not None:
        ticket_data = {
            "agent_slug": ticket.request.agent_slug,
            "capability": ticket.request.capability,
            "permission_class": ticket.request.permission_class,
            "workspace_id": ticket.request.workspace_id,
            "target": ticket.request.target,
        }
    try:
        inbox.answer(body.ticket_id, decision)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"ticket not found: {body.ticket_id!r}")
    # Log the user's decision to chronicle so the cockpit log retains it.
    if ticket_data is not None:
        kernel = getattr(request.app.state, "kernel", None)
        if kernel is not None:
            action = "permission_granted" if decision != PermissionDecision.DENY else "permission_revoked"
            try:
                kernel.chronicle.log("aegis", action, {
                    **ticket_data,
                    "decision": decision.value,
                })
            except Exception:
                pass
    return {"ok": True}


# ─── Recent decision feed for the Aurora cockpit log ────────────────────────

_PERMISSION_ACTIONS = {
    # explicit grant/revoke decisions
    "permission_granted":   ("allowed", "notable"),
    "permission_revoked":   ("denied", "notable"),
    "trust_collapse":       ("denied", "privileged"),
    # filesystem broker
    "fs_access_denied":     ("denied", "sensitive"),
    "fs_access_allowed":    ("auto", "routine"),
    "fs_read":              ("auto", "routine"),
    "fs_write":             ("allowed", "sensitive"),
    # network broker
    "net_request_allowed":  ("allowed", "notable"),
    "net_request_denied":   ("denied", "privileged"),
    # trust shifts
    "aegis.trust_change":   ("auto", "notable"),
}


@router.get("/recent")
async def recent(request: Request, limit: int = 20) -> dict:
    """Return recent permission-shaped events from the chronicle, formatted
    for the Aurora cockpit log. Each row carries a permission_class color tag
    and a coarse status (auto / allowed / pending / denied)."""
    kernel = getattr(request.app.state, "kernel", None)
    inbox = _get_inbox(request)
    rows: list[dict] = []

    # Surface every still-pending ticket first
    for p in inbox.pending():
        rows.append({
            "capability": p.request.capability,
            "target": p.request.target,
            "status": "pending",
            "permission_class": (p.request.permission_class or "sensitive").lower(),
            "time": None,
            "agent_slug": p.request.agent_slug,
        })

    # Then recent decided events from chronicle
    if kernel is not None:
        try:
            entries = kernel.chronicle.query(source="aegis", limit=max(limit * 4, 80))
        except Exception:
            entries = []
        for e in entries:
            action = e.get("action", "")
            shape = _PERMISSION_ACTIONS.get(action)
            if shape is None:
                # Pick up anything containing a permission-y verb
                if not any(k in action for k in ("permission", "grant", "fs_", "net_", "trust")):
                    continue
                shape = ("auto", "routine")
            status, klass = shape
            payload = e.get("payload") or {}
            rows.append({
                "capability": payload.get("capability") or action,
                "target": (
                    payload.get("path")
                    or payload.get("url")
                    or payload.get("target")
                    or payload.get("module")
                    or ""
                ),
                "status": status,
                "permission_class": (payload.get("permission_class") or klass).lower(),
                "time": e.get("timestamp"),
                "agent_slug": payload.get("agent") or payload.get("agent_slug") or "",
            })
            if len(rows) >= limit:
                break

    return {"events": rows[:limit]}


class SeedRequest(BaseModel):
    agent_slug: str = "oracle"
    capability: str = "fs.write"
    permission_class: str = "Sensitive"
    workspace_id: str | None = None
    target: str | None = "src/kernel/cortex.py"
    preview: str = ""


@router.post("/seed")
async def seed(request: Request, body: SeedRequest) -> dict:
    """Seed a demo permission ticket for the Aurora inline prompt to display.

    The ticket auto-cleans once the user answers, just like a real one. Useful
    for demoing the safety model without having to invoke a real gated agent."""
    inbox = _get_inbox(request)
    ticket_id = inbox.seed(PermissionRequest(
        agent_slug=body.agent_slug,
        capability=body.capability,
        permission_class=body.permission_class,
        workspace_id=body.workspace_id,
        preview=body.preview,
        target=body.target,
    ))
    return {"ticket_id": ticket_id}
