"""Tests for Engram.partition() — workspace-namespaced memory."""
from __future__ import annotations

from pathlib import Path

import pytest

from nexus.kernel.engram import Engram


def test_partition_creates_engram_dir(tmp_path):
    """partition() must create <workspace_root>/engram/ on disk."""
    ws_root = tmp_path / "my-workspace"
    ws_root.mkdir()
    global_engram = Engram(tmp_path / "global.sqlite")
    global_engram.init_db()

    child = global_engram.partition(ws_root)

    engram_dir = ws_root / "engram"
    assert engram_dir.is_dir()


def test_partition_creates_sqlite_file(tmp_path):
    """partition() must write an episodic.sqlite inside the engram dir."""
    ws_root = tmp_path / "ws1"
    ws_root.mkdir()
    global_engram = Engram(tmp_path / "global.sqlite")
    global_engram.init_db()

    child = global_engram.partition(ws_root)

    assert (ws_root / "engram" / "episodic.sqlite").exists()


def test_partition_returns_functional_engram(tmp_path):
    """The returned child Engram must store and recall episodic memories."""
    ws_root = tmp_path / "ws2"
    ws_root.mkdir()
    global_engram = Engram(tmp_path / "global.sqlite")
    global_engram.init_db()

    child = global_engram.partition(ws_root)
    child.episodic.store("workspace-scoped fact", source="test")
    results = child.episodic.recall_recent(limit=10)
    assert any("workspace-scoped fact" in r["content"] for r in results)


def test_partition_is_isolated_from_global(tmp_path):
    """Memories stored in a partition must NOT appear in the global store."""
    ws_root = tmp_path / "ws3"
    ws_root.mkdir()
    db = tmp_path / "global.sqlite"
    global_engram = Engram(db)
    global_engram.init_db()

    child = global_engram.partition(ws_root)
    child.episodic.store("only-in-workspace", source="test")

    global_results = global_engram.episodic.recall_recent(limit=50)
    assert all("only-in-workspace" not in r["content"] for r in global_results)


def test_partition_is_isolated_between_workspaces(tmp_path):
    """Two workspace partitions must not share episodic memory."""
    ws_a = tmp_path / "ws-a"
    ws_b = tmp_path / "ws-b"
    ws_a.mkdir()
    ws_b.mkdir()
    global_engram = Engram(tmp_path / "global.sqlite")
    global_engram.init_db()

    child_a = global_engram.partition(ws_a)
    child_b = global_engram.partition(ws_b)

    child_a.episodic.store("secret-alpha", source="test")

    results_b = child_b.episodic.recall_recent(limit=50)
    assert all("secret-alpha" not in r["content"] for r in results_b)


def test_partition_idempotent(tmp_path):
    """Calling partition() twice on the same root returns a usable Engram."""
    ws_root = tmp_path / "ws4"
    ws_root.mkdir()
    global_engram = Engram(tmp_path / "global.sqlite")
    global_engram.init_db()

    child1 = global_engram.partition(ws_root)
    child2 = global_engram.partition(ws_root)

    child1.episodic.store("hello", source="test")
    results = child2.episodic.recall_recent(limit=10)
    assert any("hello" in r["content"] for r in results)
