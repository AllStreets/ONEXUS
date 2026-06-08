"""Tests for Cortex loading intents from a manifest registry instead of hardcoded defs."""
from __future__ import annotations

import pytest

from nexus.agents.manifest import Manifest
from nexus.agents.registry import BuiltinRegistry
from nexus.kernel.cortex import IntentClassifier
from nexus.modules.base import NexusModule


class _Stub(NexusModule):
    name = "stub"
    description = "stub"
    version = "0.1.0"

    @classmethod
    def manifest(cls):
        return Manifest.model_validate({
            "manifest_version": 1,
            "slug": "stub", "name": "stub", "version": "0.1.0",
            "system": True, "publisher": {"type": "org", "handle": "t"},
            "category": "test",
            "identity": {"mark": {"kind": "builtin:stub", "gradient": ["#fff", "#000"]}},
            "intents": [{"name": "FROBBLE",
                         "patterns": [r"\bfrobble\b", r"\bspecial-frob\b"],
                         "semantic_signals": ["please frobble"],
                         "weight": 1.0}],
            "capabilities": {"tools": [{"name": "handle", "class": "Routine"}],
                             "declared": {"Routine": []}},
            "runtime": {"transport": "in_process"},
        })

    async def handle(self, message, context):
        return ""


def test_classifier_loads_from_registry():
    """A classifier built from a registry sees the registry's intents."""
    reg = BuiltinRegistry.from_modules([_Stub])
    classifier = IntentClassifier.from_registry(reg)
    scored = classifier.classify("please frobble this for me")
    assert len(scored) >= 1
    assert scored[0].module == "stub"
    assert scored[0].name == "FROBBLE"


def test_classifier_from_registry_matches_default_behavior_for_council():
    """A classifier built from the default builtin registry routes 'should i...'
    to council, exactly like the hardcoded _INTENT_DEFS did."""
    from nexus.kernel.cortex import default_builtin_registry
    reg = default_builtin_registry()
    classifier = IntentClassifier.from_registry(reg)
    scored = classifier.classify("should i refactor the auth module?")
    assert scored[0].module == "council"
    assert scored[0].name == "DELIBERATE"


def test_classifier_from_registry_routes_specter():
    from nexus.kernel.cortex import default_builtin_registry
    classifier = IntentClassifier.from_registry(default_builtin_registry())
    scored = classifier.classify("stress test this design")
    assert scored[0].module == "specter"
    assert scored[0].name == "CHALLENGE"


def test_classifier_from_registry_routes_oracle():
    from nexus.kernel.cortex import default_builtin_registry
    classifier = IntentClassifier.from_registry(default_builtin_registry())
    scored = classifier.classify("monitor for threat patterns")
    assert scored[0].module == "oracle"


def test_classifier_default_constructor_still_works():
    """The no-arg constructor preserves backward compatibility by loading the default registry."""
    classifier = IntentClassifier()
    # The default classifier should know about council
    scored = classifier.classify("should i decide between these options?")
    modules = [s.module for s in scored]
    assert "council" in modules
