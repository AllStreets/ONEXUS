"""Tests for the Specter module's v1 manifest."""
from __future__ import annotations

from nexus.agents.manifest import Manifest
from nexus.modules.specter import SpecterModule


def test_specter_manifest_loads():
    m = SpecterModule.manifest()
    assert isinstance(m, Manifest)
    assert m.slug == "specter"
    assert m.system is True


def test_specter_declares_challenge_intent():
    m = SpecterModule.manifest()
    names = [i.name for i in m.intents]
    assert "CHALLENGE" in names


def test_specter_intent_includes_signature_patterns():
    m = SpecterModule.manifest()
    intent = next(i for i in m.intents if i.name == "CHALLENGE")
    pattern_text = "\n".join(intent.patterns)
    assert "red" in pattern_text  # red team
    assert "devil" in pattern_text.lower()


def test_specter_only_declares_routine_capabilities():
    m = SpecterModule.manifest()
    assert m.capabilities.declared.notable == []
    assert m.capabilities.declared.sensitive == []
    assert m.capabilities.declared.privileged == []


def test_specter_runtime_is_in_process():
    m = SpecterModule.manifest()
    assert m.runtime.transport == "in_process"
