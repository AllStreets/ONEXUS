"""Tests for the v1 agent manifest model."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from nexus.agents.manifest import Manifest, PermissionClass


def _valid_manifest_dict() -> dict:
    return {
        "manifest_version": 1,
        "slug": "aider",
        "name": "aider",
        "tagline": "Pair-programming in your terminal.",
        "version": "0.74.0",
        "system": False,
        "publisher": {"type": "org", "handle": "Aider-AI", "url": "https://github.com/Aider-AI"},
        "category": "coding",
        "tags": ["coding", "cli"],
        "license": "Apache-2.0",
        "identity": {"mark": {"kind": "svg", "path": "./icon.svg",
                              "gradient": ["#9aa8ff", "#4d5bcf"]}},
        "intents": [{"name": "code", "patterns": ["edit", "fix"],
                     "semantic_signals": ["fix this"], "weight": 1.0}],
        "capabilities": {
            "tools": [{"name": "edit_file", "class": "Notable",
                       "scope": "fs.write.workspace"}],
            "declared": {
                "Routine": ["fs.read.workspace"],
                "Notable": ["fs.write.workspace"],
                "Sensitive": [],
                "Privileged": [],
            },
        },
        "runtime": {"transport": "stdio", "command": "aider-mcp", "args": [],
                    "env_keys": ["OPENAI_API_KEY"]},
        "trust": {"floor": 0.55, "default_tier": "ADVISOR"},
        "compatibility": {"nexus_version": ">=1.0.0"},
    }


def test_valid_manifest_loads():
    m = Manifest.model_validate(_valid_manifest_dict())
    assert m.slug == "aider"
    assert m.system is False
    assert m.capabilities.tools[0].permission_class is PermissionClass.NOTABLE


def test_slug_must_be_kebab_case():
    d = _valid_manifest_dict()
    d["slug"] = "Bad Slug"
    with pytest.raises(ValidationError):
        Manifest.model_validate(d)


def test_manifest_version_must_be_1():
    d = _valid_manifest_dict()
    d["manifest_version"] = 2
    with pytest.raises(ValidationError):
        Manifest.model_validate(d)


def test_tool_scope_must_be_declared():
    """A tool referencing a capability scope must appear in declared[its_class]."""
    d = _valid_manifest_dict()
    d["capabilities"]["tools"][0]["scope"] = "fs.write.workspace"
    d["capabilities"]["declared"]["Notable"] = []  # remove it
    with pytest.raises(ValidationError) as exc:
        Manifest.model_validate(d)
    assert "scope" in str(exc.value).lower()


def test_system_agent_can_declare_privileged():
    d = _valid_manifest_dict()
    d["system"] = True
    d["slug"] = "echo"
    d["capabilities"]["declared"]["Privileged"] = ["engram.read.global"]
    m = Manifest.model_validate(d)
    assert "engram.read.global" in m.capabilities.declared.privileged


def test_runtime_in_process_accepts_empty_command():
    d = _valid_manifest_dict()
    d["runtime"] = {"transport": "in_process", "command": "", "args": [], "env_keys": []}
    m = Manifest.model_validate(d)
    assert m.runtime.transport == "in_process"


def test_trust_floor_bounded():
    d = _valid_manifest_dict()
    d["trust"]["floor"] = 1.5
    with pytest.raises(ValidationError):
        Manifest.model_validate(d)
