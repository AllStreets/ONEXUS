"""Chat history aggregation — Settings → Chat history.

This route is purely read-only. It aggregates over the kernel's chronicle
(every `messages.exchange` event is logged there) and resolves full
transcripts on demand from Engram's per-workspace episodic store.

Endpoints:

  GET /api/chat-history/workspaces
      → list of workspaces that have had any exchange, with counts +
        last-active timestamp

  GET /api/chat-history/workspaces/{ws}/agents
      → list of agents (cortex modules) the user has talked to inside
        that workspace, with counts + last-active timestamp

  GET /api/chat-history/workspaces/{ws}/agents/{module}/chats
        ?offset=0&limit=50
      → page of chats with that agent in that workspace, each row
        including the full transcript (user message + agent response)
        resolved from Engram. The newest-first sort matches the rest of
        the cockpit.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request


router = APIRouter(prefix="/api/chat-history", tags=["chat-history"])


# Pull at most this many chronicle events into memory for aggregation.
# Aurora's chronicle is per-instance + local; 50k covers years of normal use.
_FETCH_CAP = 50000


def _get_kernel(request: Request):
    return request.app.state.kernel


def _get_workspace_manager(request: Request):
    mgr = getattr(request.app.state, "workspace_manager", None)
    if mgr is not None:
        return mgr
    # Lazy-init via the workspaces route's helper, so the same singleton is
    # shared. Importing here avoids a module-level cycle.
    try:
        from nexus.api.routes.workspaces import _get_manager  # type: ignore
        return _get_manager(request)
    except Exception:
        return None


def _exchanges(request: Request) -> list[dict[str, Any]]:
    """All messages.exchange events ever logged, newest-first.

    Cached read of the chronicle. Limited to _FETCH_CAP rows — past that the
    aggregation queries below would be expensive to keep doing on every UI
    refresh anyway, and the user can use Engram search for older history.
    """
    kernel = _get_kernel(request)
    try:
        return kernel.chronicle.query(source="messages", action="exchange", limit=_FETCH_CAP)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Chronicle query failed: {exc}")


def _workspace_name(mgr, ws_id: str) -> str:
    if not ws_id:
        return "(unscoped)"
    if mgr is None:
        return ws_id
    try:
        cfg = mgr.get(ws_id)
    except Exception:
        cfg = None
    if cfg is None:
        return ws_id
    return getattr(cfg, "name", ws_id) or ws_id


def _workspace_tone(mgr, ws_id: str) -> str:
    if not ws_id or mgr is None:
        return "indigo"
    try:
        cfg = mgr.get(ws_id)
    except Exception:
        return "indigo"
    if cfg is None:
        return "indigo"
    tone = getattr(cfg, "tone", None)
    if hasattr(tone, "value"):
        return tone.value.lower()
    return str(tone or "indigo").lower()


@router.get("/workspaces")
async def list_workspaces_with_history(request: Request) -> dict:
    """Workspaces that have any logged chat activity."""
    mgr = _get_workspace_manager(request)
    rows = _exchanges(request)

    bucket: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"count": 0, "last_at": None, "agents": set()}
    )
    for row in rows:
        payload = row.get("payload") or {}
        ws_id = payload.get("workspace_id") or ""
        b = bucket[ws_id]
        b["count"] += 1
        if b["last_at"] is None or row["timestamp"] > b["last_at"]:
            b["last_at"] = row["timestamp"]
        mod = payload.get("module")
        if mod:
            b["agents"].add(mod)

    workspaces = [
        {
            "workspace_id": ws_id or None,
            "name": _workspace_name(mgr, ws_id),
            "tone": _workspace_tone(mgr, ws_id),
            "chat_count": b["count"],
            "agent_count": len(b["agents"]),
            "last_active_at": b["last_at"],
        }
        for ws_id, b in bucket.items()
    ]
    # Newest first by last activity. None timestamps sort to the bottom.
    workspaces.sort(key=lambda w: w["last_active_at"] or "", reverse=True)
    return {"workspaces": workspaces, "total": len(workspaces)}


@router.get("/workspaces/{workspace_id}/agents")
async def list_agents_in_workspace(workspace_id: str, request: Request) -> dict:
    """Agents the user has exchanged messages with inside a single workspace."""
    rows = _exchanges(request)
    target = workspace_id if workspace_id != "_unscoped" else ""

    bucket: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"count": 0, "last_at": None, "last_preview": None}
    )
    for row in rows:
        payload = row.get("payload") or {}
        ws = payload.get("workspace_id") or ""
        if ws != target:
            continue
        module = payload.get("module") or "unknown"
        b = bucket[module]
        b["count"] += 1
        if b["last_at"] is None or row["timestamp"] > b["last_at"]:
            b["last_at"] = row["timestamp"]
            b["last_preview"] = payload.get("message_preview")

    agents = [
        {
            "module": module,
            "chat_count": b["count"],
            "last_active_at": b["last_at"],
            "last_preview": b["last_preview"],
        }
        for module, b in bucket.items()
    ]
    agents.sort(key=lambda a: a["last_active_at"] or "", reverse=True)
    return {"workspace_id": workspace_id, "agents": agents, "total": len(agents)}


@router.get("/workspaces/{workspace_id}/agents/{module}/chats")
async def list_chats_for_agent(
    workspace_id: str,
    module: str,
    request: Request,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict:
    """Page of chats with one agent in one workspace, transcripts inline."""
    rows = _exchanges(request)
    target_ws = workspace_id if workspace_id != "_unscoped" else ""

    matching = [
        row for row in rows
        if (row.get("payload") or {}).get("workspace_id", "") == target_ws
        and (row.get("payload") or {}).get("module") == module
    ]
    total = len(matching)
    page = matching[offset : offset + limit]

    # Resolve the workspace-partitioned engram once per page so we can fetch
    # transcripts cheaply. The kernel's global engram is the fallback when
    # the workspace has no filesystem roots — messages.py uses that same
    # fallback when persisting.
    kernel = _get_kernel(request)
    mgr = _get_workspace_manager(request)
    engram = kernel.engram
    if target_ws and mgr is not None:
        try:
            cfg = mgr.get(target_ws)
            if cfg is not None and getattr(cfg, "roots", None):
                engram = kernel.engram.partition(Path(cfg.roots[0]))
        except Exception:
            pass

    chats: list[dict[str, Any]] = []
    for row in page:
        payload = row.get("payload") or {}
        memory_id = payload.get("memory_id")
        transcript: dict[str, Any] | None = None
        if memory_id:
            try:
                entry = engram.episodic.get(memory_id)
            except Exception:
                entry = None
            # Fallback to global engram for legacy unscoped writes.
            if entry is None and engram is not kernel.engram:
                try:
                    entry = kernel.engram.episodic.get(memory_id)
                except Exception:
                    entry = None
            if entry is not None:
                content = entry.get("content") or ""
                transcript = _split_transcript(content, module)

        # Even with no engram entry we still surface what chronicle has:
        # message_preview + response_length. Better than blank rows.
        if transcript is None:
            transcript = {
                "user": payload.get("message_preview") or "",
                "agent": "",
                "truncated": True,
                "agent_response_chars": payload.get("response_length") or 0,
            }

        chats.append({
            "event_id": row["event_id"],
            "timestamp": row["timestamp"],
            "memory_id": memory_id,
            "transcript": transcript,
        })

    return {
        "workspace_id": workspace_id,
        "module": module,
        "chats": chats,
        "offset": offset,
        "limit": limit,
        "total": total,
        "has_more": (offset + limit) < total,
    }


def _split_transcript(content: str, module: str) -> dict[str, Any]:
    """Split the canonical 'USER: ...\\nAGENT[X]: ...' blob from Engram.

    The format is set by messages.py at write time. If we can't find the
    expected markers we return the whole content as the agent half — the
    user can still read it, just unstructured.
    """
    user_marker = "USER: "
    agent_marker = f"AGENT[{module}]: "

    if content.startswith(user_marker):
        rest = content[len(user_marker):]
        agent_idx = rest.find("\n" + agent_marker)
        if agent_idx >= 0:
            return {
                "user": rest[:agent_idx].strip(),
                "agent": rest[agent_idx + 1 + len(agent_marker):].strip(),
                "truncated": False,
            }
    # Try a looser split — any AGENT[ marker
    if user_marker in content:
        rest = content.split(user_marker, 1)[1]
        nl = rest.find("\nAGENT[")
        if nl >= 0:
            colon = rest.find(": ", nl)
            if colon >= 0:
                return {
                    "user": rest[:nl].strip(),
                    "agent": rest[colon + 2 :].strip(),
                    "truncated": False,
                }
    return {"user": "", "agent": content.strip(), "truncated": False}
