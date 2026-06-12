"""Tests for the Atlas module's v1 manifest."""
from __future__ import annotations

from nexus.agents.manifest import Manifest
from nexus.modules.atlas import AtlasModule


def test_atlas_manifest_loads():
    m = AtlasModule.manifest()
    assert isinstance(m, Manifest)
    assert m.slug == "atlas"
    assert m.system is True


def test_atlas_runtime_is_in_process():
    assert AtlasModule.manifest().runtime.transport == "in_process"


def test_atlas_declares_world_model_intent():
    names = [i.name for i in AtlasModule.manifest().intents]
    assert "WORLD_MODEL" in names


def test_atlas_declares_engram_capabilities_as_routine():
    d = AtlasModule.manifest().capabilities.declared
    assert "engram.read.workspace" in d.routine
    assert "engram.write.workspace" in d.routine
    assert d.privileged == []


def test_atlas_in_builtin_registry():
    from nexus.kernel.cortex import default_builtin_registry
    assert "atlas" in default_builtin_registry().slugs()
