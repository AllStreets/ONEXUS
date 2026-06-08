"""Tests for the Legacy module's v1 manifest."""
from __future__ import annotations

from nexus.agents.manifest import Manifest
from nexus.modules.legacy import LegacyModule


def test_legacy_manifest_loads():
    m = LegacyModule.manifest()
    assert isinstance(m, Manifest)
    assert m.slug == "legacy"
    assert m.system is True


def test_legacy_declares_crystallize_intent():
    m = LegacyModule.manifest()
    assert "CRYSTALLIZE" in [i.name for i in m.intents]


def test_legacy_intent_includes_signature_patterns():
    m = LegacyModule.manifest()
    intent = next(i for i in m.intents if i.name == "CRYSTALLIZE")
    text = "\n".join(intent.patterns)
    assert "crystallize" in text
    assert "playbook" in text


def test_legacy_only_declares_routine_capabilities():
    m = LegacyModule.manifest()
    assert m.capabilities.declared.notable == []
    assert m.capabilities.declared.privileged == []


def test_legacy_runtime_is_in_process():
    m = LegacyModule.manifest()
    assert m.runtime.transport == "in_process"
