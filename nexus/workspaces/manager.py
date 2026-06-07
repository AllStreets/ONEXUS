"""
WorkspaceManager — on-disk CRUD for workspaces + active-pointer.

Storage layout (all under ``root``)::

    <root>/
    ├── .active                  # plain-text file: active workspace_id
    └── <workspace-id>/
        └── workspace.json       # WorkspaceConfig serialised as pretty JSON

See docs/superpowers/specs/2026-06-06-nexus-agent-os-design.md §7.2.
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from nexus.workspaces.config import WorkspaceConfig, WorkspaceTone


# ── helpers ──────────────────────────────────────────────────────────────────


def _now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string (seconds precision)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── manager ───────────────────────────────────────────────────────────────────


class WorkspaceManager:
    """Owns the on-disk layout for all workspaces under *root*.

    Parameters
    ----------
    root:
        The directory that contains the per-workspace sub-directories
        and the ``.active`` pointer file.  Must already exist.
    """

    _ACTIVE_FILE = ".active"
    _CONFIG_FILE = "workspace.json"

    def __init__(self, root: Path | str) -> None:
        self._root = Path(root)

    # ── public API ────────────────────────────────────────────────────────────

    def create(
        self,
        *,
        name: str,
        workspace_id: str,
        tone: str = "INDIGO",
        filesystem_roots: Sequence[str] | None = None,
        resident_agents: Sequence[str] | None = None,
        pins: list[dict] | None = None,
        mood_biases: dict[str, float] | None = None,
    ) -> WorkspaceConfig:
        """Create a new workspace and persist it to disk.

        Raises
        ------
        FileExistsError
            If a workspace with *workspace_id* already exists.
        """
        ws_dir = self.workspace_dir(workspace_id)
        if ws_dir.exists():
            raise FileExistsError(
                f"Workspace {workspace_id!r} already exists at {ws_dir}"
            )

        ws_dir.mkdir(parents=True, exist_ok=False)

        now = _now_iso()
        config = WorkspaceConfig(
            schema_version=1,
            workspace_id=workspace_id,
            name=name,
            tone=WorkspaceTone(tone),
            roots=list(filesystem_roots) if filesystem_roots else [],
            resident_agents=list(resident_agents) if resident_agents else [],
            routing_pins=pins or [],
            mood_biases=mood_biases or {},
            created_at=now,
            last_active_at=now,
        )

        self._write_config(ws_dir, config)
        return config

    def destroy(self, workspace_id: str) -> None:
        """Remove a workspace from disk.

        Raises
        ------
        KeyError
            If no workspace with *workspace_id* exists.
        """
        ws_dir = self.workspace_dir(workspace_id)
        if not ws_dir.exists():
            raise KeyError(f"Workspace {workspace_id!r} not found")

        # Clear the active pointer if we are deleting the active workspace
        if self.active_id() == workspace_id:
            active_file = self._root / self._ACTIVE_FILE
            active_file.unlink(missing_ok=True)

        shutil.rmtree(ws_dir)

    def get(self, workspace_id: str) -> WorkspaceConfig | None:
        """Return the WorkspaceConfig for *workspace_id*, or ``None``."""
        config_path = self.workspace_dir(workspace_id) / self._CONFIG_FILE
        if not config_path.exists():
            return None
        return WorkspaceConfig.model_validate_json(config_path.read_text())

    def list(self) -> list[WorkspaceConfig]:
        """Return all workspaces, sorted by workspace_id."""
        configs: list[WorkspaceConfig] = []
        for entry in sorted(self._root.iterdir()):
            if entry.is_dir():
                config_path = entry / self._CONFIG_FILE
                if config_path.exists():
                    configs.append(
                        WorkspaceConfig.model_validate_json(config_path.read_text())
                    )
        return configs

    def workspace_dir(self, workspace_id: str) -> Path:
        """Return the directory for *workspace_id* (may not exist yet)."""
        return self._root / workspace_id

    def active_id(self) -> str | None:
        """Return the active workspace_id from the ``.active`` file, or ``None``."""
        active_file = self._root / self._ACTIVE_FILE
        if not active_file.exists():
            return None
        content = active_file.read_text().strip()
        return content if content else None

    def set_active(self, workspace_id: str) -> None:
        """Set *workspace_id* as the active workspace.

        Raises
        ------
        KeyError
            If no workspace with *workspace_id* exists.
        """
        if self.get(workspace_id) is None:
            raise KeyError(f"Workspace {workspace_id!r} not found")

        # Update last_active_at on the config
        ws_dir = self.workspace_dir(workspace_id)
        config = WorkspaceConfig.model_validate_json(
            (ws_dir / self._CONFIG_FILE).read_text()
        )
        updated = config.model_copy(update={"last_active_at": _now_iso()})
        self._write_config(ws_dir, updated)

        # Write the pointer
        active_file = self._root / self._ACTIVE_FILE
        active_file.write_text(workspace_id)

    # ── private helpers ───────────────────────────────────────────────────────

    def _write_config(self, ws_dir: Path, config: WorkspaceConfig) -> None:
        """Serialise *config* as pretty-printed JSON and write to disk."""
        raw_json = config.model_dump_json()
        pretty = json.dumps(json.loads(raw_json), indent=2)
        (ws_dir / self._CONFIG_FILE).write_text(pretty)
