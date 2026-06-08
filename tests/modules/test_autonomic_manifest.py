"""Tests for the Autonomic module's v1 manifest."""
from __future__ import annotations

from nexus.agents.manifest import Manifest
from nexus.modules.autonomic import AutonomicModule


def test_autonomic_manifest_loads():
    m = AutonomicModule.manifest()
    assert isinstance(m, Manifest)
    assert m.slug == "autonomic"
    assert m.system is True


def test_autonomic_declares_automate_intent():
    m = AutonomicModule.manifest()
    names = [i.name for i in m.intents]
    assert "AUTOMATE" in names


def test_autonomic_intent_includes_signature_patterns():
    m = AutonomicModule.manifest()
    intent = next(i for i in m.intents if i.name == "AUTOMATE")
    pattern_text = "\n".join(intent.patterns)
    assert "automat" in pattern_text
    assert "routine" in pattern_text


def test_autonomic_declares_process_spawn_as_notable():
    """Autonomic needs to spawn subprocesses for routines — declared Notable."""
    m = AutonomicModule.manifest()
    assert "process.spawn" in m.capabilities.declared.notable


def test_autonomic_runtime_is_in_process():
    m = AutonomicModule.manifest()
    assert m.runtime.transport == "in_process"
