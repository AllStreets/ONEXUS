"""Tests for the BuiltinRegistry — discovers and registers built-in agent manifests."""
from __future__ import annotations

import pytest

from nexus.agents.registry import BuiltinRegistry
from nexus.agents.manifest import Manifest
from nexus.modules.base import NexusModule


class _ModA(NexusModule):
    name = "mod-a"
    description = "module A"
    version = "0.1.0"

    @classmethod
    def manifest(cls) -> Manifest:
        return Manifest.model_validate({
            "manifest_version": 1,
            "slug": "mod-a", "name": "mod-a", "version": "0.1.0",
            "system": True,
            "publisher": {"type": "org", "handle": "nexus"},
            "category": "test",
            "identity": {"mark": {"kind": "builtin:mod-a", "gradient": ["#fff", "#000"]}},
            "intents": [{"name": "DO_A", "patterns": [r"\bdo-a\b"],
                         "semantic_signals": ["do a"], "weight": 1.0}],
            "capabilities": {"tools": [{"name": "handle", "class": "Routine"}],
                             "declared": {"Routine": []}},
            "runtime": {"transport": "in_process"},
        })

    async def handle(self, message, context):
        return "a"


class _ModB(NexusModule):
    name = "mod-b"
    description = "module B"
    version = "0.1.0"

    @classmethod
    def manifest(cls) -> Manifest:
        return Manifest.model_validate({
            "manifest_version": 1,
            "slug": "mod-b", "name": "mod-b", "version": "0.1.0",
            "system": True,
            "publisher": {"type": "org", "handle": "nexus"},
            "category": "test",
            "identity": {"mark": {"kind": "builtin:mod-b", "gradient": ["#fff", "#000"]}},
            "intents": [{"name": "DO_B", "patterns": [r"\bdo-b\b"],
                         "semantic_signals": ["do b"], "weight": 1.0}],
            "capabilities": {"tools": [{"name": "handle", "class": "Routine"}],
                             "declared": {"Routine": []}},
            "runtime": {"transport": "in_process"},
        })

    async def handle(self, message, context):
        return "b"


def test_registry_loads_explicit_module_classes():
    """A registry built from explicit module classes exposes each manifest."""
    reg = BuiltinRegistry.from_modules([_ModA, _ModB])
    slugs = sorted(reg.slugs())
    assert slugs == ["mod-a", "mod-b"]


def test_registry_iter_manifests_returns_validated_manifest_objects():
    reg = BuiltinRegistry.from_modules([_ModA])
    manifests = list(reg.manifests())
    assert len(manifests) == 1
    assert isinstance(manifests[0], Manifest)
    assert manifests[0].slug == "mod-a"


def test_registry_iter_module_class_pairs():
    """`pairs()` yields (manifest, module_class) so callers can both register
    the manifest with Aegis and instantiate the module for InProcessAgent."""
    reg = BuiltinRegistry.from_modules([_ModA, _ModB])
    pairs = dict((m.slug, cls) for m, cls in reg.pairs())
    assert pairs == {"mod-a": _ModA, "mod-b": _ModB}


def test_register_into_aegis(tmp_path):
    """Helper that calls aegis.register_manifest() for every built-in."""
    from nexus.kernel.aegis import Aegis
    aegis = Aegis(str(tmp_path / "a.db"))
    aegis.init_db()
    reg = BuiltinRegistry.from_modules([_ModA, _ModB])
    reg.register_all(aegis)
    assert aegis.get_manifest("mod-a") is not None
    assert aegis.get_manifest("mod-b") is not None


def test_module_without_manifest_raises_at_registry_build():
    """A module whose manifest() raises NotImplementedError must surface at build time."""

    class _Broken(NexusModule):
        name = "broken"
        description = "no manifest"
        version = "0.1.0"

        async def handle(self, message, context):
            return ""

    with pytest.raises(NotImplementedError):
        BuiltinRegistry.from_modules([_Broken])
