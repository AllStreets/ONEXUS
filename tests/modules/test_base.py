"""Tests for the refactored NexusModule ABC."""
from __future__ import annotations

import pytest

from nexus.modules.base import NexusModule
from nexus.agents.manifest import Manifest, PermissionClass


class _StubModule(NexusModule):
    name = "stub"
    description = "test stub"
    version = "0.0.1"

    @classmethod
    def manifest(cls) -> Manifest:
        return Manifest.model_validate({
            "manifest_version": 1,
            "slug": "stub",
            "name": "stub",
            "tagline": "for tests",
            "version": cls.version,
            "system": True,
            "publisher": {"type": "org", "handle": "nexus"},
            "category": "test",
            "identity": {"mark": {"kind": "builtin:stub", "gradient": ["#ffffff", "#888888"]}},
            "intents": [{"name": "stub", "patterns": ["^stub"], "weight": 1.0}],
            "capabilities": {
                "tools": [{"name": "handle", "class": "Routine"}],
                "declared": {"Routine": ["engram.read.workspace"]},
            },
            "runtime": {"transport": "in_process"},
        })

    async def handle(self, message: str, context: dict) -> str:
        return f"stub: {message}"


def test_module_must_provide_manifest():
    """A concrete NexusModule subclass must define manifest()."""

    class _Bad(NexusModule):
        name = "bad"
        description = "missing manifest"
        version = "0.0.1"

        async def handle(self, message, context):
            return ""

    with pytest.raises(NotImplementedError):
        _Bad.manifest()


def test_module_tools_default_to_handle():
    """If a module doesn't override tools(), it exposes 'handle' as the sole tool."""
    m = _StubModule()
    tools = m.tools()
    assert len(tools) == 1
    assert tools[0]["name"] == "handle"
    assert tools[0]["class"] == "Routine"


def test_module_manifest_is_a_valid_manifest():
    m = _StubModule.manifest()
    assert m.slug == "stub"
    assert m.system is True
    assert m.tool("handle").permission_class is PermissionClass.ROUTINE
