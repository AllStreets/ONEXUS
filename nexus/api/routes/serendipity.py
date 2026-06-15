"""Serendipity anti-optimization discovery API (N3.3) — Aegis-gated read.

Surfaces low-relevance / high-novelty Atlas facts on a budget. The read is
gated by engram.read.workspace (a Routine for the serendipity manifest, so
it ALLOWs once registered); when ungated it returns {gated: True, items: []}
rather than reading. Every discovery is logged to Chronicle.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Query, Request

from nexus.config import NexusConfig
from nexus.kernel.engram import Engram
from nexus.modules.serendipity import SerendipityModule
from nexus.workspaces.manager import WorkspaceManager

router = APIRouter(prefix="/api/serendipity", tags=["serendipity"])


def _data_dir(request: Request) -> Path:
    kernel = getattr(request.app.state, "kernel", None)
    return Path(kernel.config.data_dir) if kernel else Path(NexusConfig().data_dir)


def _engram_for(request: Request, workspace_id: str | None) -> Engram:
    """Resolve the workspace-scoped Engram. Falls back to the kernel Engram
    when no workspace_id is supplied."""
    kernel = request.app.state.kernel
    if not workspace_id:
        return kernel.engram
    ws_root = _data_dir(request) / "workspaces"
    ws_root.mkdir(parents=True, exist_ok=True)
    mgr = WorkspaceManager(root=ws_root)
    try:
        ws_dir = mgr.workspace_dir(workspace_id)
    except Exception:
        ws_dir = ws_root / workspace_id
    db = ws_dir / "engram" / "episodic.sqlite"
    if not db.exists():
        return kernel.engram
    return Engram(db)


@router.get("/discover")
async def discover(request: Request,
                   q: str = Query(default=""),
                   budget: int = Query(default=5, ge=1, le=50),
                   workspace_id: str | None = Query(default=None)) -> dict:
    kernel = request.app.state.kernel
    eng = _engram_for(request, workspace_id)
    mod = SerendipityModule()
    ctx = {"engram": eng, "aegis": kernel.aegis, "chronicle": kernel.chronicle,
           "workspace_id": workspace_id, "llm": None}
    return mod.discover(ctx, q, budget=budget)
