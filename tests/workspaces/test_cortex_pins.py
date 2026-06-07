"""Tests for Cortex workspace pin resolution."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from nexus.kernel.cortex import Cortex, IntentClassifier, Intent, ScoredIntent
from nexus.workspaces.config import WorkspaceConfig, RoutingPin


# ── fixtures ──────────────────────────────────────────────────────────────────


def _make_cortex() -> Cortex:
    engram = MagicMock()
    chronicle = MagicMock()
    chronicle.log = MagicMock()
    aegis = MagicMock()
    aegis.get_trust.return_value = 0.8
    aegis.get_tier.return_value = "EXECUTOR"
    aegis.is_network_allowed.return_value = True
    pulse = MagicMock()
    pulse.publish = AsyncMock()
    config = MagicMock()
    return Cortex(engram=engram, chronicle=chronicle, aegis=aegis, pulse=pulse, config=config)


def _make_workspace_config(pins: list[dict]) -> WorkspaceConfig:
    return WorkspaceConfig.model_validate({
        "schema_version": 1,
        "workspace_id": "test-ws",
        "name": "Test",
        "tone": "INDIGO",
        "routing_pins": pins,
        "created_at": "2026-06-07T00:00:00Z",
        "last_active_at": "2026-06-07T00:00:00Z",
    })


def _dummy_module(name: str) -> MagicMock:
    mod = MagicMock()
    mod.name = name
    mod.requires_network = False
    mod.handle = AsyncMock(return_value=f"[{name} response]")
    return mod


# ── set_workspace_config ──────────────────────────────────────────────────────


def test_set_workspace_config_none_clears_pins():
    cortex = _make_cortex()
    ws = _make_workspace_config([{"intent": "CODE", "agent": "aider"}])
    cortex.set_workspace_config(ws)
    assert len(cortex._workspace_pins) == 1
    cortex.set_workspace_config(None)
    assert len(cortex._workspace_pins) == 0


def test_set_workspace_config_loads_intent_pin():
    cortex = _make_cortex()
    ws = _make_workspace_config([{"intent": "DELIBERATE", "agent": "council"}])
    cortex.set_workspace_config(ws)
    intent_pin, cat_pin, agent = cortex._workspace_pins[0]
    assert intent_pin == "DELIBERATE"
    assert cat_pin is None
    assert agent == "council"


def test_set_workspace_config_loads_category_pin():
    cortex = _make_cortex()
    ws = _make_workspace_config([{"category": "coding", "agent": "aider"}])
    cortex.set_workspace_config(ws)
    intent_pin, cat_pin, agent = cortex._workspace_pins[0]
    assert intent_pin is None
    assert cat_pin == "coding"
    assert agent == "aider"


# ── pin overrides scoring ─────────────────────────────────────────────────────


def test_pin_routes_to_pinned_agent():
    """When top intent matches a pin, the pinned agent is chosen."""
    cortex = _make_cortex()

    # Register two modules
    aider = _dummy_module("aider")
    council = _dummy_module("council")
    cortex.register_module(aider)
    cortex.register_module(council)

    # Create a workspace config that pins DELIBERATE → council
    ws = _make_workspace_config([{"intent": "DELIBERATE", "agent": "council"}])
    cortex.set_workspace_config(ws)

    # Override the classifier to return DELIBERATE as top intent
    mock_classifier = MagicMock()
    mock_classifier.classify.return_value = [
        ScoredIntent(name="DELIBERATE", module="council", score=0.7),
    ]
    cortex._classifier = mock_classifier

    target, scored = cortex._select_module("should I do A or B?")
    assert target == "council"


def test_no_pin_falls_through_to_normal_scoring():
    """Without pins, scoring proceeds normally."""
    cortex = _make_cortex()
    council = _dummy_module("council")
    cortex.register_module(council)

    # No workspace config set
    mock_classifier = MagicMock()
    mock_classifier.classify.return_value = [
        ScoredIntent(name="DELIBERATE", module="council", score=0.7),
    ]
    cortex._classifier = mock_classifier

    target, scored = cortex._select_module("should I do A or B?")
    assert target == "council"


def test_pin_only_fires_when_agent_is_loaded():
    """A pin pointing to an unloaded module does not crash; falls through."""
    cortex = _make_cortex()
    council = _dummy_module("council")
    cortex.register_module(council)

    # Pin points to "aider" which is NOT loaded
    ws = _make_workspace_config([{"intent": "DELIBERATE", "agent": "aider"}])
    cortex.set_workspace_config(ws)

    mock_classifier = MagicMock()
    mock_classifier.classify.return_value = [
        ScoredIntent(name="DELIBERATE", module="council", score=0.7),
    ]
    cortex._classifier = mock_classifier

    target, scored = cortex._select_module("should I do A or B?")
    # Fell through to normal scoring — council was selected
    assert target == "council"


def test_clearing_pins_restores_normal_routing():
    cortex = _make_cortex()
    council = _dummy_module("council")
    specter = _dummy_module("specter")
    cortex.register_module(council)
    cortex.register_module(specter)

    ws = _make_workspace_config([{"intent": "DELIBERATE", "agent": "specter"}])
    cortex.set_workspace_config(ws)
    cortex.set_workspace_config(None)  # clear pins

    mock_classifier = MagicMock()
    mock_classifier.classify.return_value = [
        ScoredIntent(name="DELIBERATE", module="council", score=0.7),
    ]
    cortex._classifier = mock_classifier

    target, _ = cortex._select_module("help me decide")
    # No pin active → normal scoring picks council
    assert target == "council"
