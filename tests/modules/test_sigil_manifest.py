"""Tests for the Sigil module's v1 manifest."""
from __future__ import annotations

from nexus.agents.manifest import Manifest
from nexus.modules.sigil import SigilModule


def test_sigil_manifest_loads():
    m = SigilModule.manifest()
    assert isinstance(m, Manifest)
    assert m.slug == "sigil"
    assert m.system is True


def test_sigil_runtime_is_in_process():
    assert SigilModule.manifest().runtime.transport == "in_process"


def test_sigil_trust_floor_is_base_030():
    m = SigilModule.manifest()
    assert m.trust.floor == 0.30
    assert m.trust.default_tier.value == "ADVISOR"


def test_sigil_declares_threat_radar_intent():
    m = SigilModule.manifest()
    names = [i.name for i in m.intents]
    assert "THREAT_RADAR" in names


def test_sigil_only_declares_routine_capabilities():
    d = SigilModule.manifest().capabilities.declared
    assert "pulse.subscribe" in d.routine
    assert "chronicle.read.workspace" in d.routine
    assert "pulse.broadcast.emergency" in d.routine
    assert d.notable == [] and d.sensitive == [] and d.privileged == []


def test_sigil_in_builtin_registry():
    from nexus.kernel.cortex import default_builtin_registry
    assert "sigil" in default_builtin_registry().slugs()
