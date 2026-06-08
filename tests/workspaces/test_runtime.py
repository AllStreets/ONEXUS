"""Tests for WorkspaceRuntime — resident-agent process supervisor."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from nexus.workspaces.runtime import ResidentState, WorkspaceRuntime


# ── helpers ───────────────────────────────────────────────────────────────────


def _mock_module(slug: str) -> MagicMock:
    m = MagicMock()
    m.name = slug
    m.paused = False
    return m


def _mock_process(alive: bool = True) -> MagicMock:
    p = MagicMock()
    p.pid = 12345
    p.poll.return_value = None if alive else 0
    return p


# ── registration ──────────────────────────────────────────────────────────────


def test_register_module():
    rt = WorkspaceRuntime("ws-test")
    mod = _mock_module("council")
    rt.register_module("council", mod)
    assert rt.is_resident("council")
    assert rt.resident_count == 1


def test_register_external():
    rt = WorkspaceRuntime("ws-test")
    proc = _mock_process()
    rt.register_external("aider", proc)
    assert rt.is_resident("aider")


def test_unregister():
    rt = WorkspaceRuntime("ws-test")
    rt.register_module("echo", _mock_module("echo"))
    rt.unregister("echo")
    assert not rt.is_resident("echo")


def test_list_residents():
    rt = WorkspaceRuntime("ws-test")
    rt.register_module("echo", _mock_module("echo"))
    rt.register_module("sentry", _mock_module("sentry"))
    slugs = {r.slug for r in rt.list_residents()}
    assert slugs == {"echo", "sentry"}


# ── in-process pause / wake ───────────────────────────────────────────────────


def test_deactivate_sets_module_paused():
    rt = WorkspaceRuntime("ws-test")
    mod = _mock_module("council")
    rt.register_module("council", mod)
    rt.deactivate()
    assert mod.paused is True


def test_activate_clears_module_paused():
    rt = WorkspaceRuntime("ws-test")
    mod = _mock_module("council")
    rt.register_module("council", mod)
    rt.deactivate()
    rt.activate()
    assert mod.paused is False


def test_deactivate_returns_paused_slugs():
    rt = WorkspaceRuntime("ws-test")
    rt.register_module("council", _mock_module("council"))
    rt.register_module("echo", _mock_module("echo"))
    paused = rt.deactivate()
    assert set(paused) == {"council", "echo"}


def test_activate_returns_woken_slugs():
    rt = WorkspaceRuntime("ws-test")
    rt.register_module("council", _mock_module("council"))
    rt.deactivate()
    woken = rt.activate()
    assert "council" in woken


# ── external process SIGSTOP / SIGCONT ───────────────────────────────────────


def test_deactivate_sends_sigstop_to_external():
    rt = WorkspaceRuntime("ws-test")
    proc = _mock_process(alive=True)
    rt.register_external("aider", proc)

    with patch("os.kill") as mock_kill:
        rt.deactivate()
        import signal
        mock_kill.assert_called_once_with(proc.pid, signal.SIGSTOP)


def test_activate_sends_sigcont_to_external():
    rt = WorkspaceRuntime("ws-test")
    proc = _mock_process(alive=True)
    rt.register_external("aider", proc)
    # force paused state
    rt._residents["aider"].state = ResidentState.PAUSED

    with patch("os.kill") as mock_kill:
        rt.activate()
        import signal
        mock_kill.assert_called_once_with(proc.pid, signal.SIGCONT)


# ── stop_all ──────────────────────────────────────────────────────────────────


def test_stop_all_clears_residents():
    rt = WorkspaceRuntime("ws-test")
    rt.register_module("council", _mock_module("council"))
    rt.register_module("echo", _mock_module("echo"))
    stopped = rt.stop_all()
    assert set(stopped) == {"council", "echo"}
    assert rt.resident_count == 0


def test_stop_all_terminates_external_process():
    rt = WorkspaceRuntime("ws-test")
    proc = _mock_process(alive=True)
    rt.register_external("aider", proc)
    rt.stop_all()
    proc.terminate.assert_called_once()


# ── active flag ───────────────────────────────────────────────────────────────


def test_is_active_after_activate():
    rt = WorkspaceRuntime("ws-test")
    assert not rt.is_active
    rt.activate()
    assert rt.is_active


def test_not_active_after_deactivate():
    rt = WorkspaceRuntime("ws-test")
    rt.activate()
    rt.deactivate()
    assert not rt.is_active


# ── snapshot ──────────────────────────────────────────────────────────────────


def test_snapshot_structure():
    rt = WorkspaceRuntime("ws-snap")
    rt.register_module("echo", _mock_module("echo"))
    snap = rt.snapshot()
    assert snap["workspace_id"] == "ws-snap"
    assert isinstance(snap["residents"], list)
    assert snap["residents"][0]["slug"] == "echo"
    assert snap["residents"][0]["kind"] == "in-process"
