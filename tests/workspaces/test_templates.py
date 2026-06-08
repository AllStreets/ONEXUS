"""Tests for built-in workspace templates."""
from __future__ import annotations

from pathlib import Path

import pytest

from nexus.workspaces.manager import WorkspaceManager
from nexus.workspaces.templates import TEMPLATES, WorkspaceTemplate, apply_template


# ── helpers ───────────────────────────────────────────────────────────────────


def _manager(tmp_path: Path) -> WorkspaceManager:
    root = tmp_path / "workspaces"
    root.mkdir()
    return WorkspaceManager(root)


# ── catalogue tests ───────────────────────────────────────────────────────────


def test_six_templates_exist():
    assert len(TEMPLATES) == 6


def test_expected_slugs_present():
    expected = {"coding", "design", "research", "writing", "personal", "blank"}
    assert set(TEMPLATES.keys()) == expected


def test_each_template_has_required_fields():
    for slug, tmpl in TEMPLATES.items():
        assert isinstance(tmpl, WorkspaceTemplate)
        assert tmpl.slug == slug
        assert tmpl.label
        assert tmpl.description
        assert tmpl.tone in {"INDIGO", "MAGENTA", "SAGE", "PLUM", "AMBER"}


def test_coding_template_tone_and_roster():
    t = TEMPLATES["coding"]
    assert t.tone == "INDIGO"
    assert "aider" in t.resident_agents
    assert "council" in t.resident_agents


def test_design_template_mood_bias():
    t = TEMPLATES["design"]
    assert t.tone == "MAGENTA"
    assert t.mood_biases.get("Creative", 0) > 0


def test_research_template_routing_pin():
    t = TEMPLATES["research"]
    assert t.tone == "SAGE"
    pins = t.routing_pins
    assert any(p.get("intent") == "DELIBERATE" for p in pins)


def test_writing_template_mood_bias():
    t = TEMPLATES["writing"]
    assert t.tone == "PLUM"
    assert t.mood_biases.get("Reflective", 0) > 0


def test_personal_template():
    t = TEMPLATES["personal"]
    assert t.tone == "AMBER"
    assert "echo" in t.resident_agents


def test_blank_template_is_empty():
    t = TEMPLATES["blank"]
    assert t.resident_agents == []
    assert t.routing_pins == []
    assert t.mood_biases == {}


# ── apply_template tests ──────────────────────────────────────────────────────


def test_apply_template_creates_workspace(tmp_path):
    mgr = _manager(tmp_path)
    ws = apply_template("coding", workspace_id="my-code", name="My Code", manager=mgr)
    assert ws.workspace_id == "my-code"
    assert ws.tone.value == "INDIGO"
    assert "aider" in ws.resident_agents


def test_apply_template_writes_disk(tmp_path):
    mgr = _manager(tmp_path)
    apply_template("research", workspace_id="research-ws", name="Research", manager=mgr)
    config_path = mgr.workspace_dir("research-ws") / "workspace.json"
    assert config_path.exists()


def test_apply_template_tone_override(tmp_path):
    mgr = _manager(tmp_path)
    ws = apply_template(
        "blank", workspace_id="custom-tone", name="Custom", manager=mgr,
        tone_override="PLUM"
    )
    assert ws.tone.value == "PLUM"


def test_apply_unknown_template_raises(tmp_path):
    mgr = _manager(tmp_path)
    with pytest.raises(KeyError):
        apply_template("nonexistent", workspace_id="x", name="X", manager=mgr)


def test_apply_template_duplicate_raises(tmp_path):
    mgr = _manager(tmp_path)
    apply_template("personal", workspace_id="dup", name="Dup", manager=mgr)
    with pytest.raises(FileExistsError):
        apply_template("personal", workspace_id="dup", name="Dup2", manager=mgr)
