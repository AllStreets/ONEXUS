"""Tests that Aegis grants persist across instance restarts (sqlite-backed)."""
from __future__ import annotations

import pytest

from nexus.kernel.aegis import Aegis, Verdict
from nexus.agents.manifest import Manifest


def _aider() -> Manifest:
    return Manifest.model_validate({
        "manifest_version": 1, "slug": "aider", "name": "aider",
        "version": "1.0.0", "system": False,
        "publisher": {"type": "org", "handle": "test"}, "category": "test",
        "identity": {"mark": {"kind": "svg", "gradient": ["#fff", "#000"]}},
        "intents": [],
        "capabilities": {"tools": [], "declared": {
            "Routine": [], "Notable": ["fs.write.workspace"],
            "Sensitive": [], "Privileged": [],
        }},
        "runtime": {"transport": "stdio", "command": "x"},
    })


def test_grant_persists_across_aegis_instances(tmp_path):
    db = str(tmp_path / "aegis.db")
    a1 = Aegis(db)
    a1.init_db()
    a1.register_manifest(_aider())
    a1.grant("aider", "fs.write.workspace", workspace_id="ws-1")

    a2 = Aegis(db)
    a2.init_db()
    a2.register_manifest(_aider())
    d = a2.check_capability("aider", "fs.write.workspace", workspace_id="ws-1")
    assert d.verdict is Verdict.ALLOW


def test_revoke_grant_persists(tmp_path):
    db = str(tmp_path / "aegis.db")
    a1 = Aegis(db)
    a1.init_db()
    a1.register_manifest(_aider())
    a1.grant("aider", "fs.write.workspace", workspace_id="ws-1")
    a1.revoke_grant("aider", "fs.write.workspace", workspace_id="ws-1")

    a2 = Aegis(db)
    a2.init_db()
    a2.register_manifest(_aider())
    d = a2.check_capability("aider", "fs.write.workspace", workspace_id="ws-1")
    assert d.verdict is Verdict.PROMPT


def test_trust_collapse_revokes_persisted_grants(tmp_path):
    db = str(tmp_path / "aegis.db")
    a = Aegis(db)
    a.init_db()
    a.register_manifest(_aider())
    a.grant("aider", "fs.write.workspace", workspace_id="ws-1")
    a.set_trust("aider", 0.30)

    a2 = Aegis(db)
    a2.init_db()
    a2.register_manifest(_aider())
    d = a2.check_capability("aider", "fs.write.workspace", workspace_id="ws-1")
    assert d.verdict is Verdict.PROMPT


def test_global_grant_applies_across_workspaces(tmp_path):
    """A grant with workspace_id=None is honored in any workspace."""
    db = str(tmp_path / "aegis.db")
    a = Aegis(db)
    a.init_db()
    a.register_manifest(_aider())
    a.grant("aider", "fs.write.workspace")  # global

    for ws in (None, "ws-1", "ws-2"):
        d = a.check_capability("aider", "fs.write.workspace", workspace_id=ws)
        assert d.verdict is Verdict.ALLOW, f"global grant failed in workspace={ws!r}"
