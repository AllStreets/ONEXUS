"""Tests for the Consciousness module's v1 manifest."""
from __future__ import annotations

from nexus.agents.manifest import Manifest
from nexus.modules.consciousness import ConsciousnessModule


def test_consciousness_manifest_loads():
    m = ConsciousnessModule.manifest()
    assert isinstance(m, Manifest)
    assert m.slug == "consciousness"
    assert m.system is True


def test_consciousness_declares_reflect_intent():
    m = ConsciousnessModule.manifest()
    assert "REFLECT" in [i.name for i in m.intents]


def test_consciousness_intent_includes_signature_patterns():
    m = ConsciousnessModule.manifest()
    intent = next(i for i in m.intents if i.name == "REFLECT")
    text = "\n".join(intent.patterns)
    assert "journal" in text
    assert "reflect" in text or "introspect" in text


def test_consciousness_only_declares_routine_capabilities():
    m = ConsciousnessModule.manifest()
    assert m.capabilities.declared.notable == []
    assert m.capabilities.declared.privileged == []


def test_consciousness_runtime_is_in_process():
    m = ConsciousnessModule.manifest()
    assert m.runtime.transport == "in_process"
