"""Tests for the Oracle module's v1 manifest."""
from __future__ import annotations

from nexus.agents.manifest import Manifest
from nexus.modules.oracle import OracleModule


def test_oracle_manifest_loads():
    m = OracleModule.manifest()
    assert isinstance(m, Manifest)
    assert m.slug == "oracle"
    assert m.system is True


def test_oracle_declares_anticipate_intent():
    m = OracleModule.manifest()
    names = [i.name for i in m.intents]
    assert "ANTICIPATE" in names


def test_oracle_intent_includes_signature_patterns():
    m = OracleModule.manifest()
    intent = next(i for i in m.intents if i.name == "ANTICIPATE")
    pattern_text = "\n".join(intent.patterns)
    assert "predict" in pattern_text
    assert "anticipat" in pattern_text


def test_oracle_only_declares_routine_capabilities():
    m = OracleModule.manifest()
    assert m.capabilities.declared.notable == []
    assert m.capabilities.declared.sensitive == []
    assert m.capabilities.declared.privileged == []


def test_oracle_runtime_is_in_process():
    m = OracleModule.manifest()
    assert m.runtime.transport == "in_process"
