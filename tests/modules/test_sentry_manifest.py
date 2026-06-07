"""Tests for the Sentry module's v1 manifest."""
from __future__ import annotations

from nexus.agents.manifest import Manifest
from nexus.modules.sentry import SentryModule


def test_sentry_manifest_loads():
    m = SentryModule.manifest()
    assert isinstance(m, Manifest)
    assert m.slug == "sentry"
    assert m.system is True


def test_sentry_declares_regulate_intent():
    m = SentryModule.manifest()
    assert "REGULATE" in [i.name for i in m.intents]


def test_sentry_intent_includes_signature_patterns():
    m = SentryModule.manifest()
    intent = next(i for i in m.intents if i.name == "REGULATE")
    text = "\n".join(intent.patterns)
    assert "focus" in text or "fatigue" in text
    assert "cognitive" in text or "flow" in text


def test_sentry_only_declares_routine_capabilities():
    m = SentryModule.manifest()
    assert m.capabilities.declared.notable == []
    assert m.capabilities.declared.privileged == []


def test_sentry_runtime_is_in_process():
    m = SentryModule.manifest()
    assert m.runtime.transport == "in_process"
