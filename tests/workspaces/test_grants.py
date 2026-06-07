"""Tests for GrantsStore — SQLite-backed per-workspace grants."""
from __future__ import annotations

from pathlib import Path

import pytest

from nexus.workspaces.grants import GrantsStore, Grant


def _store(tmp_path: Path) -> GrantsStore:
    gs = GrantsStore(tmp_path / "grants.sqlite")
    gs.init_db()
    return gs


def test_grant_creates_record(tmp_path):
    gs = _store(tmp_path)
    g = gs.grant("aider", "fs.write.workspace")
    assert g.agent_slug == "aider"
    assert g.capability == "fs.write.workspace"
    assert g.grant_id is not None


def test_grant_is_idempotent(tmp_path):
    gs = _store(tmp_path)
    g1 = gs.grant("aider", "fs.write.workspace")
    g2 = gs.grant("aider", "fs.write.workspace")
    assert g1.grant_id == g2.grant_id


def test_has_returns_true_after_grant(tmp_path):
    gs = _store(tmp_path)
    gs.grant("council", "engram.read.global")
    assert gs.has("council", "engram.read.global") is True


def test_has_returns_false_for_missing(tmp_path):
    gs = _store(tmp_path)
    assert gs.has("ghost", "fs.write.workspace") is False


def test_revoke_removes_grant(tmp_path):
    gs = _store(tmp_path)
    gs.grant("aider", "network.outbound.github.com")
    assert gs.revoke("aider", "network.outbound.github.com") is True
    assert gs.has("aider", "network.outbound.github.com") is False


def test_revoke_returns_false_when_absent(tmp_path):
    gs = _store(tmp_path)
    assert gs.revoke("nobody", "nothing") is False


def test_revoke_all_removes_agent_grants(tmp_path):
    gs = _store(tmp_path)
    gs.grant("aider", "fs.write.workspace")
    gs.grant("aider", "network.outbound.api.github.com")
    count = gs.revoke_all("aider")
    assert count == 2
    assert gs.list_for_agent("aider") == []


def test_list_for_agent(tmp_path):
    gs = _store(tmp_path)
    gs.grant("council", "engram.read.global")
    gs.grant("council", "fs.read.workspace")
    gs.grant("aider", "fs.write.workspace")
    grants = gs.list_for_agent("council")
    assert len(grants) == 2
    caps = {g.capability for g in grants}
    assert caps == {"engram.read.global", "fs.read.workspace"}


def test_list_all(tmp_path):
    gs = _store(tmp_path)
    gs.grant("alpha", "cap-a")
    gs.grant("beta", "cap-b")
    all_grants = gs.list_all()
    assert len(all_grants) == 2


def test_scope_differentiates_grants(tmp_path):
    gs = _store(tmp_path)
    g1 = gs.grant("aider", "fs.write", scope="/home/user/proj1")
    g2 = gs.grant("aider", "fs.write", scope="/home/user/proj2")
    assert g1.grant_id != g2.grant_id
    assert len(gs.list_for_agent("aider")) == 2


def test_grants_persist_across_instances(tmp_path):
    db = tmp_path / "grants.sqlite"
    gs1 = GrantsStore(db)
    gs1.init_db()
    gs1.grant("echo", "fs.read.workspace")

    gs2 = GrantsStore(db)
    gs2.init_db()
    assert gs2.has("echo", "fs.read.workspace") is True
