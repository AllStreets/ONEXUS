"""Tests for WorkspaceConfig — the pydantic model for workspace.json."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from nexus.workspaces.config import WorkspaceConfig, WorkspaceTone, RoutingPin


def _valid_config_dict() -> dict:
    return {
        "schema_version": 1,
        "workspace_id": "client-work-7b3a",
        "name": "Client Work",
        "tone": "INDIGO",
        "roots": ["/Users/alice/client-project"],
        "resident_agents": ["aider", "council"],
        "routing_pins": [
            {"intent": "CODE", "agent": "aider"},
        ],
        "mood_biases": {},
        "created_at": "2026-06-07T00:00:00Z",
        "last_active_at": "2026-06-07T00:00:00Z",
    }


def test_valid_config_loads():
    cfg = WorkspaceConfig.model_validate(_valid_config_dict())
    assert cfg.workspace_id == "client-work-7b3a"
    assert cfg.tone is WorkspaceTone.INDIGO
    assert len(cfg.resident_agents) == 2


def test_workspace_id_must_be_kebab_case():
    d = _valid_config_dict()
    d["workspace_id"] = "Bad ID"
    with pytest.raises(ValidationError):
        WorkspaceConfig.model_validate(d)


def test_schema_version_must_be_1():
    d = _valid_config_dict()
    d["schema_version"] = 2
    with pytest.raises(ValidationError):
        WorkspaceConfig.model_validate(d)


def test_routing_pin_requires_exactly_one_of_intent_or_category():
    d = _valid_config_dict()
    # Both set — should fail
    d["routing_pins"] = [{"intent": "CODE", "category": "coding", "agent": "aider"}]
    with pytest.raises(ValidationError):
        WorkspaceConfig.model_validate(d)


def test_routing_pin_with_only_category():
    d = _valid_config_dict()
    d["routing_pins"] = [{"category": "coding", "agent": "council"}]
    cfg = WorkspaceConfig.model_validate(d)
    pin = cfg.routing_pins[0]
    assert pin.category == "coding"
    assert pin.intent is None


def test_resolved_roots_returns_paths(tmp_path):
    d = _valid_config_dict()
    d["roots"] = [str(tmp_path)]
    cfg = WorkspaceConfig.model_validate(d)
    roots = cfg.resolved_roots()
    assert roots[0] == tmp_path.resolve()


def test_pin_for_intent_lookup():
    d = _valid_config_dict()
    d["routing_pins"] = [
        {"intent": "CODE", "agent": "aider"},
        {"category": "research", "agent": "council"},
    ]
    cfg = WorkspaceConfig.model_validate(d)
    assert cfg.pin_for_intent("CODE") == "aider"
    assert cfg.pin_for_intent("MISSING") is None
    assert cfg.pin_for_category("research") == "council"
