"""Tests for the Chronos module's v1 manifest."""
from __future__ import annotations

from nexus.agents.manifest import Manifest
from nexus.modules.chronos import ChronosModule


def test_chronos_manifest_loads():
    m = ChronosModule.manifest()
    assert isinstance(m, Manifest)
    assert m.slug == "chronos"
    assert m.system is True


def test_chronos_runtime_is_in_process():
    assert ChronosModule.manifest().runtime.transport == "in_process"


def test_chronos_declares_counterfactual_intent():
    names = [i.name for i in ChronosModule.manifest().intents]
    assert "COUNTERFACTUAL" in names


def test_chronos_declares_chronicle_read_as_routine():
    d = ChronosModule.manifest().capabilities.declared
    assert "chronicle.read.workspace" in d.routine
    assert d.sensitive == []
    assert d.privileged == []


def test_chronos_trust_floor_is_advisor():
    t = ChronosModule.manifest().trust
    assert t.floor == 0.30
    assert t.default_tier == "ADVISOR"


def test_chronos_in_builtin_registry():
    from nexus.kernel.cortex import default_builtin_registry
    assert "chronos" in default_builtin_registry().slugs()
