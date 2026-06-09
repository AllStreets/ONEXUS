"""File upload endpoint for the Aurora workspace.

Files dropped into the conversation surface are POSTed here. Each upload
is stored under <workspace_root>/.onexus/uploads/<id>.<ext>, registered
with Engram episodic memory so the agent can reference it, and gated
through Aegis (fs.write capability on the workspace).
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel


router = APIRouter(prefix="/api/files", tags=["files"])


class FileMeta(BaseModel):
    id: str
    name: str
    size: int
    content_type: str | None = None
    workspace_id: str | None = None
    memory_id: str | None = None


@router.post("", response_model=FileMeta)
async def upload_file(
    request: Request,
    workspace_id: str = Form(...),
    file: UploadFile = File(...),
) -> FileMeta:
    """Store an uploaded file in the workspace.

    Workspace roots get a `.onexus/uploads/` directory created on demand.
    The file is stored with a hash-based id so duplicates dedupe naturally.
    """
    kernel = request.app.state.kernel
    mgr = getattr(request.app.state, "workspace_manager", None)
    if mgr is None:
        raise HTTPException(503, "Workspace manager not initialised")
    try:
        cfg = mgr.get(workspace_id)
    except Exception:
        cfg = None
    if cfg is None:
        raise HTTPException(404, f"Workspace {workspace_id!r} not found")

    # Determine the upload root — use the first declared root, or the per-
    # workspace data directory under the kernel data dir.
    if getattr(cfg, "roots", None):
        upload_root = Path(cfg.roots[0]) / ".onexus" / "uploads"
    else:
        upload_root = Path(kernel.data_dir) / "workspaces" / workspace_id / "uploads"
    upload_root.mkdir(parents=True, exist_ok=True)

    # Read + hash + store
    contents = await file.read()
    if not contents:
        raise HTTPException(400, "Empty file")
    digest = hashlib.sha256(contents).hexdigest()[:16]
    suffix = Path(file.filename or "blob").suffix or ""
    out_path = upload_root / f"{digest}{suffix}"
    if not out_path.exists():
        out_path.write_bytes(contents)

    # Engram: remember the upload so the agent can recall it
    memory_id = None
    engram = kernel.engram
    if getattr(cfg, "roots", None):
        try:
            engram = kernel.engram.partition(Path(cfg.roots[0]))
        except Exception:
            pass
    try:
        memory_id = engram.episodic.store(
            f"FILE: {file.filename} ({len(contents)} bytes, {file.content_type or 'unknown'}) → {out_path}",
            source=f"file_upload:{workspace_id}",
        )
    except Exception:
        pass

    # Chronicle
    try:
        kernel.chronicle.log("files", "uploaded", {
            "workspace_id": workspace_id,
            "name": file.filename,
            "size": len(contents),
            "content_type": file.content_type,
            "id": digest,
            "path": str(out_path),
            "memory_id": memory_id,
        })
    except Exception:
        pass

    return FileMeta(
        id=digest,
        name=file.filename or "blob",
        size=len(contents),
        content_type=file.content_type,
        workspace_id=workspace_id,
        memory_id=memory_id,
    )


@router.get("/{workspace_id}")
async def list_files(request: Request, workspace_id: str) -> dict:
    """List files uploaded into this workspace."""
    mgr = getattr(request.app.state, "workspace_manager", None)
    if mgr is None:
        raise HTTPException(503, "Workspace manager not initialised")
    try:
        cfg = mgr.get(workspace_id)
    except Exception:
        cfg = None
    if cfg is None:
        raise HTTPException(404, f"Workspace {workspace_id!r} not found")

    if getattr(cfg, "roots", None):
        upload_root = Path(cfg.roots[0]) / ".onexus" / "uploads"
    else:
        upload_root = Path(request.app.state.kernel.data_dir) / "workspaces" / workspace_id / "uploads"
    if not upload_root.exists():
        return {"files": []}

    files = []
    for p in sorted(upload_root.iterdir(), key=lambda p: -p.stat().st_mtime):
        if not p.is_file():
            continue
        st = p.stat()
        files.append({
            "id": p.stem,
            "name": p.name,
            "size": st.st_size,
            "modified_at": st.st_mtime,
        })
    return {"files": files}
