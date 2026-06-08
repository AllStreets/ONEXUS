"""
WorkspaceRuntime — lifecycle supervisor for a single workspace's resident agents.

Responsibilities
----------------
- Track which resident agents are registered for a workspace.
- Pause all residents when the workspace is deactivated (SIGSTOP for
  external agents; ``paused=True`` flag for in-process built-ins).
- Wake all residents when the workspace is activated (SIGCONT / clear flag).
- Stop all residents when the workspace is destroyed.
- Expose the live agent count and pause state for Cockpit display.

The runtime keeps a simple ``_residents`` dict keyed by agent slug.
It does not launch new processes itself — that remains the responsibility
of :class:`~nexus.agents.launcher.AgentLauncher`.  Instead the runtime
holds weak references to already-running process handles (or in-process
module instances) and issues POSIX signals or flag mutations.

See docs/superpowers/specs/2026-06-06-nexus-agent-os-design.md §7.4.
"""
from __future__ import annotations

import logging
import os
import signal
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("nexus.workspaces.runtime")


class ResidentState(str, Enum):
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"


@dataclass
class Resident:
    """Tracks a single resident agent within a WorkspaceRuntime."""

    slug: str
    state: ResidentState = ResidentState.RUNNING
    # For external subprocess agents — may be None for in-process built-ins.
    process: subprocess.Popen | None = None
    # For in-process built-in NexusModule instances — may be None.
    module: Any = None  # NexusModule | None

    def is_external(self) -> bool:
        return self.process is not None

    def is_in_process(self) -> bool:
        return self.module is not None


class WorkspaceRuntime:
    """Owns the resident-agent lifecycle for ONE workspace.

    Parameters
    ----------
    workspace_id:
        The workspace this runtime belongs to.
    chronicle:
        Optional Chronicle instance for event logging.  Pass None in
        tests to skip logging.
    """

    def __init__(self, workspace_id: str, chronicle: Any = None) -> None:
        self._workspace_id = workspace_id
        self._chronicle = chronicle
        self._residents: dict[str, Resident] = {}
        self._active: bool = False

    # ── properties ────────────────────────────────────────────────────────

    @property
    def workspace_id(self) -> str:
        return self._workspace_id

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def resident_count(self) -> int:
        return len(self._residents)

    # ── registration ──────────────────────────────────────────────────────

    def register_external(self, slug: str, process: subprocess.Popen) -> Resident:
        """Register an already-running external agent subprocess."""
        resident = Resident(slug=slug, state=ResidentState.RUNNING, process=process)
        self._residents[slug] = resident
        logger.debug("workspace=%s registered external agent %s", self._workspace_id, slug)
        return resident

    def register_module(self, slug: str, module: Any) -> Resident:
        """Register an in-process NexusModule as a resident."""
        resident = Resident(slug=slug, state=ResidentState.RUNNING, module=module)
        self._residents[slug] = resident
        logger.debug("workspace=%s registered in-process module %s", self._workspace_id, slug)
        return resident

    def unregister(self, slug: str) -> None:
        """Remove a resident from tracking (does not stop the process)."""
        self._residents.pop(slug, None)

    def is_resident(self, slug: str) -> bool:
        return slug in self._residents

    def list_residents(self) -> list[Resident]:
        return list(self._residents.values())

    def get_resident(self, slug: str) -> Resident | None:
        return self._residents.get(slug)

    # ── workspace activation ──────────────────────────────────────────────

    def activate(self) -> list[str]:
        """Wake all paused residents.  Returns list of woken slugs."""
        woken: list[str] = []
        for slug, resident in self._residents.items():
            if resident.state == ResidentState.PAUSED:
                self._wake_resident(resident)
                woken.append(slug)
        self._active = True
        self._log("workspace_activated", {"woken": woken})
        return woken

    def deactivate(self) -> list[str]:
        """Pause all running residents.  Returns list of paused slugs."""
        paused: list[str] = []
        for slug, resident in self._residents.items():
            if resident.state == ResidentState.RUNNING:
                self._pause_resident(resident)
                paused.append(slug)
        self._active = False
        self._log("workspace_deactivated", {"paused": paused})
        return paused

    def stop_all(self) -> list[str]:
        """Stop (terminate) all residents.  Returns list of stopped slugs."""
        stopped: list[str] = []
        for slug, resident in list(self._residents.items()):
            self._stop_resident(resident)
            stopped.append(slug)
        self._residents.clear()
        self._active = False
        self._log("workspace_stopped", {"stopped": stopped})
        return stopped

    # ── per-resident operations ───────────────────────────────────────────

    def _pause_resident(self, resident: Resident) -> None:
        if resident.is_external() and resident.process is not None:
            try:
                if resident.process.poll() is None:
                    os.kill(resident.process.pid, signal.SIGSTOP)
            except (ProcessLookupError, OSError):
                pass
        elif resident.is_in_process() and resident.module is not None:
            if hasattr(resident.module, "paused"):
                resident.module.paused = True
        resident.state = ResidentState.PAUSED
        logger.debug("paused resident %s in workspace %s", resident.slug, self._workspace_id)

    def _wake_resident(self, resident: Resident) -> None:
        if resident.is_external() and resident.process is not None:
            try:
                if resident.process.poll() is None:
                    os.kill(resident.process.pid, signal.SIGCONT)
            except (ProcessLookupError, OSError):
                pass
        elif resident.is_in_process() and resident.module is not None:
            if hasattr(resident.module, "paused"):
                resident.module.paused = False
        resident.state = ResidentState.RUNNING
        logger.debug("woke resident %s in workspace %s", resident.slug, self._workspace_id)

    def _stop_resident(self, resident: Resident) -> None:
        if resident.is_external() and resident.process is not None:
            try:
                if resident.process.poll() is None:
                    resident.process.terminate()
                    try:
                        resident.process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        resident.process.kill()
            except (ProcessLookupError, OSError):
                pass
        elif resident.is_in_process() and resident.module is not None:
            if hasattr(resident.module, "paused"):
                resident.module.paused = True
        resident.state = ResidentState.STOPPED
        logger.debug("stopped resident %s in workspace %s", resident.slug, self._workspace_id)

    # ── internal ──────────────────────────────────────────────────────────

    def _log(self, event: str, payload: dict) -> None:
        if self._chronicle is None:
            return
        try:
            self._chronicle.log(
                "workspace_runtime",
                event,
                {"workspace_id": self._workspace_id, **payload},
            )
        except Exception:
            pass  # Chronicle failures must never block workspace operations

    # ── snapshot ──────────────────────────────────────────────────────────

    def snapshot(self) -> dict:
        """Return a dict summary suitable for Cockpit display."""
        return {
            "workspace_id": self._workspace_id,
            "active": self._active,
            "residents": [
                {
                    "slug": r.slug,
                    "state": r.state.value,
                    "kind": "external" if r.is_external() else "in-process",
                }
                for r in self._residents.values()
            ],
        }
