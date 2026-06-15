"""Tests for the Herald module's v1 manifest."""
from __future__ import annotations

from nexus.agents.manifest import Manifest
from nexus.modules.herald import HeraldModule


def test_herald_manifest_loads():
    m = HeraldModule.manifest()
    assert isinstance(m, Manifest)
    assert m.slug == "herald"
    assert m.system is True


def test_herald_runtime_is_in_process():
    assert HeraldModule.manifest().runtime.transport == "in_process"


def test_herald_declares_negotiate_intent():
    names = [i.name for i in HeraldModule.manifest().intents]
    assert "NEGOTIATE" in names


def test_herald_declares_no_network_capability():
    d = HeraldModule.manifest().capabilities.declared
    assert not any(c.startswith("network.") for c in d.all())


def test_herald_trust_floor_is_advisor():
    t = HeraldModule.manifest().trust
    assert t.floor == 0.30
    assert t.default_tier == "ADVISOR"


def test_herald_in_builtin_registry():
    from nexus.kernel.cortex import default_builtin_registry
    assert "herald" in default_builtin_registry().slugs()
