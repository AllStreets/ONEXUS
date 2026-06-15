"""
CodebaseRegistry — on-disk registry of workspace codebase roots.

A codebase root is a local directory the user has explicitly granted a
workspace read access to (browse + attach files into the conversation).
Registrations persist the same way workspaces do: pretty-printed JSON
under the kernel data dir (``<data_dir>/codebases.json``), so they
survive restarts alongside ``workspaces/<id>/workspace.json``.

Path safety (traversal / symlink-escape checks) lives in the API route —
the registry only stores already-validated absolute resolved paths.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, ConfigDict


def _now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string (seconds precision)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class CodebaseRoot(BaseModel):
    """One registered codebase root (a row in codebases.json)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    workspace_id: str
    path: str            # absolute, resolved
    name: str
    registered_at: str = ""


class CodebaseRegistry:
    """Owns ``codebases.json`` under *data_dir*.

    The id is a content hash of (workspace_id, resolved path) so
    re-registering the same directory in the same workspace is a no-op
    that returns the existing record instead of accumulating duplicates.
    """

    _FILE = "codebases.json"

    def __init__(self, data_dir: Path | str) -> None:
        self._path = Path(data_dir) / self._FILE

    # ── public API ─────────────────────────────────────────────────────────

    def register(self, *, workspace_id: str, path: Path, name: str | None = None) -> CodebaseRoot:
        """Persist a new root (or return the existing record for this path)."""
        resolved = str(path)
        root_id = hashlib.sha256(f"{workspace_id}:{resolved}".encode()).hexdigest()[:16]
        roots = self._load()
        for r in roots:
            if r.id == root_id:
                return r
        record = CodebaseRoot(
            id=root_id,
            workspace_id=workspace_id,
            path=resolved,
            name=name or Path(resolved).name or resolved,
            registered_at=_now_iso(),
        )
        roots.append(record)
        self._save(roots)
        return record

    def get(self, root_id: str) -> CodebaseRoot | None:
        """Return the record for *root_id*, or ``None``."""
        for r in self._load():
            if r.id == root_id:
                return r
        return None

    def list(self, workspace_id: str | None = None) -> list[CodebaseRoot]:
        """All registered roots, optionally scoped to one workspace."""
        roots = self._load()
        if workspace_id is not None:
            roots = [r for r in roots if r.workspace_id == workspace_id]
        return roots

    def unregister(self, root_id: str) -> CodebaseRoot:
        """Remove a root. Raises ``KeyError`` if unknown."""
        roots = self._load()
        for r in roots:
            if r.id == root_id:
                self._save([x for x in roots if x.id != root_id])
                return r
        raise KeyError(f"Codebase root {root_id!r} not found")

    # ── private helpers ────────────────────────────────────────────────────

    def _load(self) -> list[CodebaseRoot]:
        if not self._path.exists():
            return []
        try:
            raw = json.loads(self._path.read_text())
        except Exception:
            return []
        out: list[CodebaseRoot] = []
        for item in raw if isinstance(raw, list) else []:
            try:
                out.append(CodebaseRoot.model_validate(item))
            except Exception:
                continue
        return out

    def _save(self, roots: list[CodebaseRoot]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps([r.model_dump() for r in roots], indent=2)
        )
