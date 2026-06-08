"""Tests for the AgentDispatcher module's v1 manifest."""
from __future__ import annotations

from nexus.agents.manifest import Manifest
from nexus.modules.agent_dispatcher import AgentDispatcherModule


def test_dispatcher_manifest_loads():
    m = AgentDispatcherModule.manifest()
    assert isinstance(m, Manifest)
    assert m.slug == "agents"
    assert m.system is True


def test_dispatcher_declares_summon_intent():
    m = AgentDispatcherModule.manifest()
    assert "SUMMON" in [i.name for i in m.intents]


def test_dispatcher_intent_includes_signature_patterns():
    m = AgentDispatcherModule.manifest()
    intent = next(i for i in m.intents if i.name == "SUMMON")
    text = "\n".join(intent.patterns)
    assert "summon" in text
    assert "launch" in text or "list" in text or "agent" in text


def test_dispatcher_declares_inter_agent_call_capability():
    """Dispatcher launches catalog agents — needs inter-agent dispatch capability."""
    m = AgentDispatcherModule.manifest()
    assert (
        "inter_agent.call.*" in m.capabilities.declared.notable
        or "inter_agent.list" in m.capabilities.declared.routine
    )


def test_dispatcher_runtime_is_in_process():
    m = AgentDispatcherModule.manifest()
    assert m.runtime.transport == "in_process"
