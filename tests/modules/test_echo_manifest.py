"""Tests for the Echo module's v1 manifest."""
from __future__ import annotations

from nexus.agents.manifest import Manifest
from nexus.modules.echo import EchoModule


def test_echo_manifest_loads():
    m = EchoModule.manifest()
    assert isinstance(m, Manifest)
    assert m.slug == "echo"
    assert m.system is True


def test_echo_declares_profile_intent():
    m = EchoModule.manifest()
    assert "PROFILE" in [i.name for i in m.intents]


def test_echo_intent_includes_signature_patterns():
    m = EchoModule.manifest()
    intent = next(i for i in m.intents if i.name == "PROFILE")
    text = "\n".join(intent.patterns)
    assert "fingerprint" in text
    assert "profile" in text


def test_echo_declares_engram_read_global_as_privileged():
    """Echo is the only built-in with a Privileged capability — cross-workspace memory read."""
    m = EchoModule.manifest()
    assert "engram.read.global" in m.capabilities.declared.privileged


def test_echo_runtime_is_in_process():
    m = EchoModule.manifest()
    assert m.runtime.transport == "in_process"
