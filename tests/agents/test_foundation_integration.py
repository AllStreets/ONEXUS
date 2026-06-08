"""End-to-end smoke test for the Phase 1 foundation."""
from __future__ import annotations

import pytest

from nexus.agents.in_process_agent import InProcessAgent
from nexus.agents.manifest import Manifest
from nexus.kernel.aegis import Aegis
from nexus.modules.base import NexusModule


class _FileWriter(NexusModule):
    """A built-in module that writes a file via aegis.fs()."""
    name = "writer"
    description = "writes files"
    version = "0.1.0"

    @classmethod
    def manifest(cls) -> Manifest:
        return Manifest.model_validate({
            "manifest_version": 1,
            "slug": "writer", "name": "writer", "version": "0.1.0",
            "system": True,
            "publisher": {"type": "org", "handle": "nexus"},
            "category": "test",
            "identity": {"mark": {"kind": "builtin:writer", "gradient": ["#fff", "#000"]}},
            "intents": [{"name": "write", "patterns": ["write"], "weight": 1.0}],
            "capabilities": {
                "tools": [{"name": "handle", "class": "Notable",
                           "scope": "fs.write.workspace"}],
                "declared": {
                    "Routine": [],
                    "Notable": ["fs.write.workspace"],
                    "Sensitive": [],
                    "Privileged": [],
                },
            },
            "runtime": {"transport": "in_process"},
        })

    async def handle(self, message: str, context: dict) -> str:
        aegis = context["aegis"]
        ws_root = context["workspace_root"]
        target = ws_root / "out.txt"
        with aegis.fs("writer", target, mode="w",
                      workspace_roots=[ws_root], workspace_id="ws-1") as f:
            f.write(message)
        return f"wrote {target}"


@pytest.mark.asyncio
async def test_capability_gates_tool_call(tmp_path):
    """Without a grant or Executor trust, the tool's fs.write call is denied."""
    aegis = Aegis(str(tmp_path / "aegis.db"))
    aegis.init_db()
    aegis.register_manifest(_FileWriter.manifest())

    agent = InProcessAgent(_FileWriter(), aegis=aegis)
    ws_root = tmp_path / "ws"
    ws_root.mkdir()
    context = {"aegis": aegis, "workspace_root": ws_root}

    # OBSERVER trust + no grant → PROMPT verdict → PermissionDenied at write
    from nexus.kernel.aegis import PermissionDenied
    with pytest.raises(PermissionDenied):
        await agent.call_tool("handle", {"message": "hi", "context": context})


@pytest.mark.asyncio
async def test_executor_trust_enables_write(tmp_path):
    aegis = Aegis(str(tmp_path / "aegis.db"))
    aegis.init_db()
    aegis.register_manifest(_FileWriter.manifest())
    aegis.set_trust("writer", 0.80)  # EXECUTOR

    agent = InProcessAgent(_FileWriter(), aegis=aegis)
    ws_root = tmp_path / "ws"
    ws_root.mkdir()
    context = {"aegis": aegis, "workspace_root": ws_root}

    result = await agent.call_tool("handle", {"message": "ok", "context": context})
    assert "wrote" in result
    assert (ws_root / "out.txt").read_text() == "ok"


@pytest.mark.asyncio
async def test_trust_collapse_revokes_then_denies(tmp_path):
    aegis = Aegis(str(tmp_path / "aegis.db"))
    aegis.init_db()
    aegis.register_manifest(_FileWriter.manifest())

    # User grants explicitly
    aegis.grant("writer", "fs.write.workspace", workspace_id="ws-1")
    # NOTE: 0.60 (MONITOR tier, ≥ 0.50) keeps the grant alive. Using 0.30 here
    # would immediately trigger trust-collapse and revoke the grant before the
    # first call_tool, making the "works while granted" assertion unreachable.
    aegis.set_trust("writer", 0.60)  # MONITOR — grant survives

    agent = InProcessAgent(_FileWriter(), aegis=aegis)
    ws_root = tmp_path / "ws"
    ws_root.mkdir()
    context = {"aegis": aegis, "workspace_root": ws_root}

    # Works while granted
    await agent.call_tool("handle", {"message": "first", "context": context})
    assert (ws_root / "out.txt").read_text() == "first"

    # Trust collapses → grants revoked → next call denies
    aegis.set_trust("writer", 0.20)  # below 0.50 — triggers collapse
    from nexus.kernel.aegis import PermissionDenied
    with pytest.raises(PermissionDenied):
        await agent.call_tool("handle", {"message": "second", "context": context})
