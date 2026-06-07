"""Tests for WorkspaceManager — on-disk CRUD + active-pointer."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from nexus.workspaces.manager import WorkspaceManager


# ── helpers ──────────────────────────────────────────────────────────────────


def _make_manager(tmp_path: Path) -> WorkspaceManager:
    root = tmp_path / "workspaces"
    root.mkdir()
    return WorkspaceManager(root)


# ── tests ─────────────────────────────────────────────────────────────────────


def test_create_workspace_writes_disk(tmp_path):
    mgr = _make_manager(tmp_path)
    ws = mgr.create(name="My Project", workspace_id="my-project", tone="INDIGO")
    ws_file = mgr.workspace_dir("my-project") / "workspace.json"
    assert ws_file.exists()
    data = json.loads(ws_file.read_text())
    assert data["workspace_id"] == "my-project"
    assert data["name"] == "My Project"
    assert data["tone"] == "INDIGO"
    assert data["schema_version"] == 1


def test_list_returns_all_workspaces(tmp_path):
    mgr = _make_manager(tmp_path)
    mgr.create(name="Alpha", workspace_id="alpha", tone="SAGE")
    mgr.create(name="Beta", workspace_id="beta", tone="AMBER")
    workspaces = mgr.list()
    assert len(workspaces) == 2
    ids = [ws.workspace_id for ws in workspaces]
    assert "alpha" in ids
    assert "beta" in ids


def test_get_returns_workspace_by_id(tmp_path):
    mgr = _make_manager(tmp_path)
    mgr.create(name="Gamma", workspace_id="gamma", tone="PLUM")
    ws = mgr.get("gamma")
    assert ws is not None
    assert ws.workspace_id == "gamma"
    assert ws.name == "Gamma"


def test_get_unknown_returns_none(tmp_path):
    mgr = _make_manager(tmp_path)
    assert mgr.get("no-such-workspace") is None


def test_destroy_removes_workspace_dir(tmp_path):
    mgr = _make_manager(tmp_path)
    mgr.create(name="Doomed", workspace_id="doomed", tone="MAGENTA")
    ws_dir = mgr.workspace_dir("doomed")
    assert ws_dir.exists()
    mgr.destroy("doomed")
    assert not ws_dir.exists()
    assert mgr.get("doomed") is None


def test_active_pointer_persists(tmp_path):
    mgr = _make_manager(tmp_path)
    mgr.create(name="Focus", workspace_id="focus", tone="INDIGO")
    assert mgr.active_id() is None
    mgr.set_active("focus")
    assert mgr.active_id() == "focus"
    # Re-creating the manager from the same root should still read the pointer
    mgr2 = WorkspaceManager(tmp_path / "workspaces")
    assert mgr2.active_id() == "focus"


def test_set_active_unknown_raises(tmp_path):
    mgr = _make_manager(tmp_path)
    with pytest.raises(KeyError):
        mgr.set_active("ghost")


def test_create_duplicate_raises(tmp_path):
    mgr = _make_manager(tmp_path)
    mgr.create(name="Solo", workspace_id="solo", tone="AMBER")
    with pytest.raises(FileExistsError):
        mgr.create(name="Solo Again", workspace_id="solo", tone="SAGE")
