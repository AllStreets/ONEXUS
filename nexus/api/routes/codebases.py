"""Workspace codebase roots — register local directories, browse, read files.

A codebase root is an explicit user grant: "this workspace may read this
directory". Everything here is read-only and traversal-proof:

- Registration requires an absolute path (after ~ expansion) that exists
  and is a directory; the resolved path is what gets persisted.
- Tree/file reads resolve the requested relative path and refuse anything
  that lands outside the registered root — including symlinks that point
  out of it. Directory listings skip escaping symlinks entirely.
- File reads are capped at 512 KB and refuse binary content (HTTP 415).

Every registration, listing, and read is logged to Chronicle under the
"codebases" source so the cockpit can audit exactly what the workspace
has touched.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from nexus.workspaces.codebases import CodebaseRegistry, CodebaseRoot
from nexus.workspaces.manager import WorkspaceManager


router = APIRouter(prefix="/api/codebases", tags=["codebases"])

MAX_TREE_ENTRIES = 500
MAX_FILE_BYTES = 512 * 1024  # 512 KB


def _get_registry(request: Request) -> CodebaseRegistry:
    reg = getattr(request.app.state, "codebase_registry", None)
    if reg is not None:
        return reg
    kernel = getattr(request.app.state, "kernel", None)
    if kernel is None:
        raise HTTPException(503, "Kernel not initialised")
    reg = CodebaseRegistry(Path(kernel.config.data_dir))
    request.app.state.codebase_registry = reg
    return reg


def _get_workspace_manager(request: Request) -> WorkspaceManager:
    mgr = getattr(request.app.state, "workspace_manager", None)
    if mgr is not None:
        return mgr
    kernel = getattr(request.app.state, "kernel", None)
    if kernel is None:
        raise HTTPException(503, "Kernel not initialised")
    ws_root = Path(kernel.config.data_dir) / "workspaces"
    ws_root.mkdir(parents=True, exist_ok=True)
    mgr = WorkspaceManager(root=ws_root)
    request.app.state.workspace_manager = mgr
    return mgr


def _chronicle(request: Request, action: str, payload: dict) -> None:
    try:
        request.app.state.kernel.chronicle.log("codebases", action, payload)
    except Exception:
        pass


def _to_dict(r: CodebaseRoot) -> dict:
    return r.model_dump()


def _resolve_root(request: Request, root_id: str) -> tuple[CodebaseRoot, Path]:
    """Look up a registered root and return (record, resolved root Path)."""
    record = _get_registry(request).get(root_id)
    if record is None:
        raise HTTPException(404, f"Codebase {root_id!r} not found")
    root = Path(record.path)
    if not root.is_dir():
        raise HTTPException(410, f"Codebase root no longer exists: {record.path}")
    return record, root


def _resolve_within(root: Path, rel: str) -> Path:
    """Resolve *rel* against *root* and refuse anything that escapes it.

    ``resolve()`` follows symlinks, so a symlink inside the root that points
    outside resolves outside — and gets rejected here. The empty string
    resolves to the root itself.
    """
    if Path(rel).is_absolute():
        raise HTTPException(400, "path must be relative to the codebase root")
    try:
        target = (root / rel).resolve()
    except Exception:
        raise HTTPException(400, f"Unresolvable path: {rel!r}")
    if target != root and root not in target.parents:
        raise HTTPException(400, f"Path escapes the codebase root: {rel!r}")
    return target


# ── endpoints ────────────────────────────────────────────────────────────────


class RegisterBody(BaseModel):
    workspace_id: str
    path: str
    name: str | None = None


@router.post("")
async def register_codebase(request: Request, body: RegisterBody) -> dict:
    """Register a local directory as a codebase root for a workspace."""
    mgr = _get_workspace_manager(request)
    try:
        cfg = mgr.get(body.workspace_id)
    except Exception:
        cfg = None
    if cfg is None:
        raise HTTPException(404, f"Workspace {body.workspace_id!r} not found")

    raw = Path(body.path).expanduser()
    if not raw.is_absolute():
        raise HTTPException(400, f"path must be absolute, got {body.path!r}")
    if not raw.exists():
        raise HTTPException(400, f"path does not exist: {body.path!r}")
    if not raw.is_dir():
        raise HTTPException(400, f"path is not a directory: {body.path!r}")

    record = _get_registry(request).register(
        workspace_id=body.workspace_id,
        path=raw.resolve(),
        name=body.name,
    )
    _chronicle(request, "registered", {
        "workspace_id": body.workspace_id,
        "codebase_id": record.id,
        "path": record.path,
        "name": record.name,
    })
    return _to_dict(record)


@router.get("")
async def list_codebases(
    request: Request,
    workspace_id: str | None = Query(default=None),
) -> dict:
    """List registered codebase roots, optionally scoped to one workspace."""
    roots = _get_registry(request).list(workspace_id=workspace_id)
    return {"codebases": [_to_dict(r) for r in roots]}


@router.get("/{root_id}/tree")
async def codebase_tree(
    request: Request,
    root_id: str,
    path: str = Query(default="", description="Relative path within the root"),
) -> dict:
    """One-level directory listing: directories first, then files, by name."""
    record, root = _resolve_root(request, root_id)
    target = _resolve_within(root, path)
    if not target.exists():
        raise HTTPException(404, f"Directory not found: {path!r}")
    if not target.is_dir():
        raise HTTPException(400, f"Not a directory: {path!r}")

    dirs: list[dict] = []
    files: list[dict] = []
    truncated = False
    for entry in sorted(target.iterdir(), key=lambda p: p.name.lower()):
        if len(dirs) + len(files) >= MAX_TREE_ENTRIES:
            truncated = True
            break
        # Skip symlinks that resolve outside the registered root — they
        # would let a listing advertise paths the read endpoints refuse.
        if entry.is_symlink():
            try:
                resolved = entry.resolve()
            except Exception:
                continue
            if resolved != root and root not in resolved.parents:
                continue
        rel = str(entry.relative_to(target))
        if entry.is_dir():
            dirs.append({"name": rel, "type": "dir"})
        elif entry.is_file():
            try:
                size = entry.stat().st_size
            except OSError:
                size = 0
            files.append({"name": rel, "type": "file", "size": size})

    _chronicle(request, "tree_read", {
        "workspace_id": record.workspace_id,
        "codebase_id": record.id,
        "path": path,
        "entries": len(dirs) + len(files),
    })
    return {
        "codebase_id": record.id,
        "path": path,
        "entries": dirs + files,
        "truncated": truncated,
    }


@router.get("/{root_id}/file")
async def codebase_file(
    request: Request,
    root_id: str,
    path: str = Query(..., description="Relative path within the root"),
) -> dict:
    """Read one text file (UTF-8, 512 KB cap, binary refused with 415)."""
    record, root = _resolve_root(request, root_id)
    target = _resolve_within(root, path)
    if not target.exists() or not target.is_file():
        raise HTTPException(404, f"File not found: {path!r}")

    size = target.stat().st_size
    if size > MAX_FILE_BYTES:
        raise HTTPException(
            413, f"File is {size} bytes; the cap is {MAX_FILE_BYTES} bytes"
        )

    data = target.read_bytes()
    if b"\x00" in data[:8192]:
        raise HTTPException(415, f"Binary file refused: {path!r}")
    try:
        content = data.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(415, f"Not valid UTF-8 text: {path!r}")

    _chronicle(request, "file_read", {
        "workspace_id": record.workspace_id,
        "codebase_id": record.id,
        "path": path,
        "size": size,
    })
    return {
        "codebase_id": record.id,
        "path": path,
        "name": target.name,
        "size": size,
        "content": content,
    }


@router.delete("/{root_id}")
async def unregister_codebase(request: Request, root_id: str) -> dict:
    """Remove a codebase root registration (the directory is untouched)."""
    try:
        record = _get_registry(request).unregister(root_id)
    except KeyError:
        raise HTTPException(404, f"Codebase {root_id!r} not found")
    _chronicle(request, "unregistered", {
        "workspace_id": record.workspace_id,
        "codebase_id": record.id,
        "path": record.path,
    })
    return {"ok": True}
