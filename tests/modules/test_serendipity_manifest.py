"""Tests for the Serendipity module's v1 manifest."""
from __future__ import annotations

from nexus.agents.manifest import Manifest
from nexus.modules.serendipity import SerendipityModule


def test_serendipity_manifest_loads():
    m = SerendipityModule.manifest()
    assert isinstance(m, Manifest)
    assert m.slug == "serendipity"
    assert m.system is True


def test_serendipity_runtime_is_in_process():
    assert SerendipityModule.manifest().runtime.transport == "in_process"


def test_serendipity_declares_serendipity_intent():
    names = [i.name for i in SerendipityModule.manifest().intents]
    assert "SERENDIPITY" in names


def test_serendipity_declares_engram_read_as_routine():
    d = SerendipityModule.manifest().capabilities.declared
    assert "engram.read.workspace" in d.routine
    assert not any(c.startswith("network.") for c in d.all())


def test_serendipity_trust_floor_is_advisor():
    t = SerendipityModule.manifest().trust
    assert t.floor == 0.30
    assert t.default_tier == "ADVISOR"


def test_serendipity_in_builtin_registry():
    from nexus.kernel.cortex import default_builtin_registry
    assert "serendipity" in default_builtin_registry().slugs()
