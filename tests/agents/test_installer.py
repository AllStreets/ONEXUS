"""Tests for InstallPlan and the install validator."""
from __future__ import annotations

import json

import pytest

from nexus.agents.installer import (
    InstallPlan,
    PlanGroup,
    plan_from_manifest_dict,
    plan_from_manifest_path,
)


def _valid_manifest_dict() -> dict:
    return {
        "manifest_version": 1,
        "slug": "browser-use",
        "name": "browser-use",
        "tagline": "Drives a real browser to do real things.",
        "version": "0.1.0",
        "system": False,
        "publisher": {"type": "org", "handle": "browser-use",
                      "url": "https://github.com/browser-use/browser-use"},
        "category": "browser-automation",
        "license": "Apache-2.0",
        "identity": {"mark": {"kind": "svg", "gradient": ["#fff", "#000"]}},
        "intents": [],
        "capabilities": {
            "tools": [
                {"name": "navigate", "class": "Notable",
                 "scope": "network.outbound.google.com"},
                {"name": "screenshot", "class": "Notable",
                 "scope": "fs.write.workspace"},
                {"name": "open_window", "class": "Sensitive",
                 "scope": "hardware.screen"},
            ],
            "declared": {
                "Routine": ["fs.read.workspace"],
                "Notable": ["network.outbound.google.com", "fs.write.workspace"],
                "Sensitive": ["hardware.screen"],
                "Privileged": [],
            },
        },
        "runtime": {"transport": "stdio", "command": "browser-use-mcp"},
    }


def test_plan_groups_by_class():
    plan = plan_from_manifest_dict(_valid_manifest_dict())
    by_class = {g.permission_class: g for g in plan.groups}
    assert "Routine" in by_class
    assert "Notable" in by_class
    assert "Sensitive" in by_class
    assert "fs.read.workspace" in by_class["Routine"].capabilities
    assert "fs.write.workspace" in by_class["Notable"].capabilities
    assert "hardware.screen" in by_class["Sensitive"].capabilities


def test_plan_skips_privileged_when_third_party():
    """A non-system manifest declaring Privileged must surface a warning."""
    d = _valid_manifest_dict()
    d["capabilities"]["declared"]["Privileged"] = ["engram.read.global"]
    plan = plan_from_manifest_dict(d)
    assert plan.has_privileged is True
    # Privileged caps still appear in the plan, but with the warning flag
    priv = next(g for g in plan.groups if g.permission_class == "Privileged")
    assert "engram.read.global" in priv.capabilities


def test_plan_records_publisher_and_license():
    plan = plan_from_manifest_dict(_valid_manifest_dict())
    assert plan.publisher == "browser-use"
    assert plan.license == "Apache-2.0"


def test_plan_summary_describes_each_class():
    plan = plan_from_manifest_dict(_valid_manifest_dict())
    summary = plan.short_summary()
    assert "Routine" in summary or "routine" in summary.lower()
    assert "Notable" in summary or "notable" in summary.lower()


def test_plan_from_path_round_trip(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(_valid_manifest_dict()))
    plan = plan_from_manifest_path(path)
    assert plan.slug == "browser-use"


def test_plan_rejects_invalid_manifest():
    with pytest.raises(Exception):
        plan_from_manifest_dict({"manifest_version": 1, "slug": "Bad Slug"})
