"""Tests for the Council module's v1 manifest."""
from __future__ import annotations

from nexus.agents.manifest import Manifest, PermissionClass
from nexus.modules.council import CouncilModule


def test_council_manifest_loads():
    m = CouncilModule.manifest()
    assert isinstance(m, Manifest)
    assert m.slug == "council"
    assert m.system is True


def test_council_declares_deliberate_intent():
    m = CouncilModule.manifest()
    names = [i.name for i in m.intents]
    assert "DELIBERATE" in names


def test_council_intent_includes_signature_patterns():
    """The deliberate intent must keep the patterns Cortex currently uses."""
    m = CouncilModule.manifest()
    deliberate = next(i for i in m.intents if i.name == "DELIBERATE")
    pattern_text = "\n".join(deliberate.patterns)
    # A few signature patterns from the existing _INTENT_DEFS
    assert "should\\s+i" in pattern_text
    assert "decid" in pattern_text or "decision" in pattern_text
    assert "ethic" in pattern_text


def test_council_only_declares_routine_capabilities():
    """Council does no fs/network/process — purely cognitive."""
    m = CouncilModule.manifest()
    assert m.capabilities.declared.notable == []
    assert m.capabilities.declared.sensitive == []
    assert m.capabilities.declared.privileged == []


def test_council_runtime_is_in_process():
    m = CouncilModule.manifest()
    assert m.runtime.transport == "in_process"
