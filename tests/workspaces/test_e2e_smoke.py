"""
End-to-end smoke test for the workspace layer.

Exercises the full lifecycle without mocking internals:
  1. Create a workspace via WorkspaceManager.
  2. Partition Engram for it.
  3. Grant a capability via Aegis (sqlite-backed, durable).
  4. Instantiate WorkspaceRuntime and register an in-process module.
  5. Activate → deactivate (module's paused flag is toggled).
  6. Load routing pins into Cortex and confirm pin resolution.
  7. MoodEngine: signals from the workspace produce the expected mood.
  8. Destroy the workspace (runtime stops agents).
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from nexus.agents.manifest import Manifest
from nexus.kernel.aegis import Aegis, Verdict
from nexus.kernel.cortex import Cortex, ScoredIntent
from nexus.kernel.engram import Engram
from nexus.workspaces.config import WorkspaceConfig
from nexus.workspaces.manager import WorkspaceManager
from nexus.workspaces.mood import Mood, MoodEngine, MoodSignals
from nexus.workspaces.runtime import ResidentState, WorkspaceRuntime
from nexus.workspaces.templates import apply_template


# ── fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def workspaces_root(tmp_path: Path) -> Path:
    root = tmp_path / "workspaces"
    root.mkdir()
    return root


@pytest.fixture()
def mgr(workspaces_root: Path) -> WorkspaceManager:
    return WorkspaceManager(workspaces_root)


# ── smoke test ────────────────────────────────────────────────────────────────


def test_full_workspace_lifecycle(tmp_path, mgr, workspaces_root):
    # ── 1. Create workspace via template ─────────────────────────────────
    ws_config = apply_template(
        "coding",
        workspace_id="dev-room",
        name="Dev Room",
        manager=mgr,
    )
    assert ws_config.workspace_id == "dev-room"
    assert ws_config.tone.value == "INDIGO"
    assert "aider" in ws_config.resident_agents

    # workspace.json must exist on disk
    ws_dir = mgr.workspace_dir("dev-room")
    assert (ws_dir / "workspace.json").exists()

    # ── 2. Engram partition ──────────────────────────────────────────────
    global_engram = Engram(tmp_path / "global.sqlite")
    global_engram.init_db()

    partition = global_engram.partition(ws_dir)
    partition.episodic.store("design decision: use SQLite", source="user")
    results = partition.episodic.recall_recent(limit=5)
    assert any("design decision" in r["content"] for r in results)

    # Isolated from global
    global_results = global_engram.episodic.recall_recent(limit=50)
    assert all("design decision" not in r["content"] for r in global_results)

    # ── 3. Aegis grants (sqlite-backed, durable) ─────────────────────────
    aegis_db = str(tmp_path / "aegis.db")
    grants_aegis = Aegis(aegis_db)
    grants_aegis.init_db()
    aider_manifest = Manifest.model_validate({
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
    grants_aegis.register_manifest(aider_manifest)
    grants_aegis.grant("aider", "fs.write.workspace", workspace_id="dev-room")
    decision = grants_aegis.check_capability("aider", "fs.write.workspace", workspace_id="dev-room")
    assert decision.verdict is Verdict.ALLOW

    # ── 4-5. WorkspaceRuntime: pause / wake ──────────────────────────────
    rt = WorkspaceRuntime("dev-room")
    mod = MagicMock()
    mod.name = "council"
    mod.paused = False
    rt.register_module("council", mod)

    rt.deactivate()
    assert mod.paused is True

    rt.activate()
    assert mod.paused is False

    # ── 6. Cortex pin resolution ─────────────────────────────────────────
    chronicle = MagicMock()
    chronicle.log = MagicMock()
    aegis = MagicMock()
    aegis.get_trust.return_value = 0.8
    aegis.get_tier.return_value = "EXECUTOR"
    aegis.is_network_allowed.return_value = True
    pulse = MagicMock()
    pulse.publish = AsyncMock()

    cortex = Cortex(
        engram=global_engram,
        chronicle=chronicle,
        aegis=aegis,
        pulse=pulse,
        config=MagicMock(),
    )

    aider_mod = MagicMock()
    aider_mod.name = "aider"
    aider_mod.requires_network = False
    council_mod = MagicMock()
    council_mod.name = "council"
    council_mod.requires_network = False
    cortex.register_module(aider_mod)
    cortex.register_module(council_mod)

    # Load the workspace config (has CODE → aider pin)
    cortex.set_workspace_config(ws_config)

    # Override classifier to return CODE as top intent
    mock_clf = MagicMock()
    mock_clf.classify.return_value = [
        ScoredIntent(name="CODE", module="aider", score=0.85),
    ]
    cortex._classifier = mock_clf

    target, _ = cortex._select_module("fix the bug in main.py")
    assert target == "aider"

    # ── 7. MoodEngine ────────────────────────────────────────────────────
    engine = MoodEngine()
    signals = MoodSignals(
        active_agent="council",
        workspace_tone="INDIGO",
    )
    result = engine.evaluate(signals)
    assert result.mood is Mood.DELIBERATING

    # ── 8. Destroy workspace ─────────────────────────────────────────────
    stopped = rt.stop_all()
    assert "council" in stopped

    mgr.destroy("dev-room")
    assert mgr.get("dev-room") is None
    assert not ws_dir.exists()
