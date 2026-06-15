"""Tests for the Prism module's v1 manifest."""
from __future__ import annotations

from nexus.agents.manifest import Manifest
from nexus.modules.prism import PrismModule


def test_prism_manifest_loads():
    m = PrismModule.manifest()
    assert isinstance(m, Manifest)
    assert m.slug == "prism"
    assert m.system is True


def test_prism_runtime_is_in_process():
    assert PrismModule.manifest().runtime.transport == "in_process"


def test_prism_declares_cross_domain_intent():
    names = [i.name for i in PrismModule.manifest().intents]
    assert "CROSS_DOMAIN_SYNTHESIS" in names


def test_prism_declares_global_read_as_sensitive():
    d = PrismModule.manifest().capabilities.declared
    assert "engram.read.global" in d.sensitive
    assert "engram.read.workspace" in d.routine
    assert d.privileged == []


def test_prism_trust_floor_is_advisor():
    t = PrismModule.manifest().trust
    assert t.floor == 0.30
    assert t.default_tier == "ADVISOR"


def test_prism_in_builtin_registry():
    from nexus.kernel.cortex import default_builtin_registry
    assert "prism" in default_builtin_registry().slugs()
