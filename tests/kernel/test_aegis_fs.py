"""Tests for Aegis.fs — the filesystem broker."""
from __future__ import annotations

import pytest

from nexus.kernel.aegis import Aegis, PermissionDenied
from nexus.agents.manifest import Manifest


def _agent_manifest(slug: str, declared_routine: list[str], declared_notable: list[str]) -> Manifest:
    return Manifest.model_validate({
        "manifest_version": 1,
        "slug": slug, "name": slug, "version": "1.0.0", "system": False,
        "publisher": {"type": "org", "handle": "test"},
        "category": "test",
        "identity": {"mark": {"kind": "svg", "gradient": ["#fff", "#000"]}},
        "intents": [],
        "capabilities": {
            "tools": [],
            "declared": {
                "Routine": declared_routine,
                "Notable": declared_notable,
                "Sensitive": [],
                "Privileged": [],
            },
        },
        "runtime": {"transport": "stdio", "command": "x"},
    })


def test_read_inside_workspace_allowed(tmp_path):
    aegis = Aegis(str(tmp_path / "aegis.db"))
    aegis.init_db()
    aegis.register_manifest(_agent_manifest("a", ["fs.read.workspace"], []))

    root = tmp_path / "ws"
    root.mkdir()
    (root / "hello.txt").write_text("hi")

    with aegis.fs("a", root / "hello.txt", mode="r", workspace_roots=[root]) as f:
        assert f.read() == "hi"


def test_read_outside_workspace_denied(tmp_path):
    aegis = Aegis(str(tmp_path / "aegis.db"))
    aegis.init_db()
    aegis.register_manifest(_agent_manifest("a", ["fs.read.workspace"], []))

    root = tmp_path / "ws"
    root.mkdir()
    outside = tmp_path / "elsewhere.txt"
    outside.write_text("nope")

    with pytest.raises(PermissionDenied):
        aegis.fs("a", outside, mode="r", workspace_roots=[root])


def test_write_without_declared_notable_denied(tmp_path):
    aegis = Aegis(str(tmp_path / "aegis.db"))
    aegis.init_db()
    # declares ONLY read
    aegis.register_manifest(_agent_manifest("a", ["fs.read.workspace"], []))

    root = tmp_path / "ws"
    root.mkdir()

    with pytest.raises(PermissionDenied):
        aegis.fs("a", root / "out.txt", mode="w", workspace_roots=[root])


def test_write_with_grant_allowed(tmp_path):
    aegis = Aegis(str(tmp_path / "aegis.db"))
    aegis.init_db()
    aegis.register_manifest(_agent_manifest("a", ["fs.read.workspace"], ["fs.write.workspace"]))
    aegis.grant("a", "fs.write.workspace", workspace_id="ws-1")

    root = tmp_path / "ws"
    root.mkdir()

    with aegis.fs("a", root / "out.txt", mode="w",
                  workspace_roots=[root], workspace_id="ws-1") as f:
        f.write("ok")

    assert (root / "out.txt").read_text() == "ok"


def test_exclusive_create_mode_treated_as_write(tmp_path):
    """`x` (exclusive create) is a write-like mode; agent without write declared must be denied."""
    aegis = Aegis(str(tmp_path / "aegis.db"))
    aegis.init_db()
    aegis.register_manifest(_agent_manifest("a", ["fs.read.workspace"], []))

    root = tmp_path / "ws"
    root.mkdir()

    with pytest.raises(PermissionDenied):
        aegis.fs("a", root / "new.txt", mode="x", workspace_roots=[root])
