"""Tests for the Wraith module's v1 manifest."""
from __future__ import annotations

from nexus.agents.manifest import Manifest
from nexus.modules.wraith import WraithModule


def test_wraith_manifest_loads():
    m = WraithModule.manifest()
    assert isinstance(m, Manifest)
    assert m.slug == "wraith"
    assert m.system is True


def test_wraith_declares_spawn_intent():
    m = WraithModule.manifest()
    assert "SPAWN" in [i.name for i in m.intents]


def test_wraith_intent_includes_spawn_patterns():
    m = WraithModule.manifest()
    intent = next(i for i in m.intents if i.name == "SPAWN")
    text = "\n".join(intent.patterns)
    assert "spawn" in text
    assert "sub-?agent" in text or "subagent" in text


def test_wraith_declares_process_spawn_notable():
    m = WraithModule.manifest()
    assert "process.spawn" in m.capabilities.declared.notable


def test_wraith_runtime_is_in_process():
    m = WraithModule.manifest()
    assert m.runtime.transport == "in_process"
