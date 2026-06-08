"""REST endpoints for the workspace manager (Phase 5 surfaces consume these)."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from nexus.workspaces.config import WorkspaceConfig, WorkspaceTone
from nexus.workspaces.manager import WorkspaceManager
from nexus.config import NexusConfig


router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


def _get_manager(request: Request) -> WorkspaceManager:
    mgr = getattr(request.app.state, "workspace_manager", None)
    if mgr is None:
        # Prefer the kernel config if available (correct data_dir for the app instance)
        kernel = getattr(request.app.state, "kernel", None)
        if kernel is not None:
            data_dir = Path(kernel.config.data_dir)
        else:
            cfg = NexusConfig()
            data_dir = Path(cfg.data_dir)
        ws_root = data_dir / "workspaces"
        ws_root.mkdir(parents=True, exist_ok=True)
        mgr = WorkspaceManager(root=ws_root)
        request.app.state.workspace_manager = mgr
    return mgr


def _to_dict(w: WorkspaceConfig) -> dict:
    return {
        "workspace_id": w.workspace_id,
        "name": w.name,
        "tone": w.tone.value.lower() if hasattr(w.tone, "value") else str(w.tone).lower(),
        "filesystem_roots": list(w.roots),
        "resident_agents": list(w.resident_agents),
        "pins": [p.model_dump() for p in w.routing_pins],
        "mood_biases": w.mood_biases,
        "created_at": w.created_at,
        "last_active_at": w.last_active_at,
    }


class CreateBody(BaseModel):
    workspace_id: str
    name: str
    tone: str = "indigo"
    filesystem_roots: list[str] = []
    resident_agents: list[str] = []
    mood_biases: dict[str, float] = {}


@router.get("")
async def list_workspaces(request: Request) -> dict:
    mgr = _get_manager(request)
    return {
        "active": mgr.active_id(),
        "workspaces": [_to_dict(w) for w in mgr.list()],
    }


@router.post("")
async def create_workspace(request: Request, body: CreateBody) -> dict:
    mgr = _get_manager(request)
    # Accept lowercase tone values; convert to uppercase for the enum
    try:
        tone = WorkspaceTone(body.tone.upper())
    except ValueError:
        raise HTTPException(400, f"invalid tone: {body.tone!r}")
    try:
        cfg = mgr.create(
            name=body.name,
            workspace_id=body.workspace_id,
            tone=tone,
            filesystem_roots=body.filesystem_roots,
            resident_agents=body.resident_agents,
            mood_biases={k: float(v) for k, v in body.mood_biases.items()} if body.mood_biases else None,
        )
    except FileExistsError:
        raise HTTPException(409, f"workspace {body.workspace_id!r} already exists")
    return _to_dict(cfg)


@router.get("/active")
async def get_active(request: Request) -> dict:
    mgr = _get_manager(request)
    slug = mgr.active_id()
    if slug is None:
        return {"active": None}
    cfg = mgr.get(slug)
    return {"active": _to_dict(cfg) if cfg else None}


@router.get("/{workspace_id}")
async def get_workspace(request: Request, workspace_id: str) -> dict:
    mgr = _get_manager(request)
    cfg = mgr.get(workspace_id)
    if cfg is None:
        raise HTTPException(404, f"workspace {workspace_id!r} not found")
    return _to_dict(cfg)


@router.delete("/{workspace_id}")
async def delete_workspace(request: Request, workspace_id: str) -> dict:
    mgr = _get_manager(request)
    try:
        mgr.destroy(workspace_id)
    except (KeyError, FileNotFoundError):
        raise HTTPException(404, f"workspace {workspace_id!r} not found")
    return {"ok": True}


@router.post("/{workspace_id}/switch")
async def switch_workspace(request: Request, workspace_id: str) -> dict:
    mgr = _get_manager(request)
    try:
        mgr.set_active(workspace_id)
    except KeyError:
        raise HTTPException(404, f"workspace {workspace_id!r} not found")
    return {"active": workspace_id}
