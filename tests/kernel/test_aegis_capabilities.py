"""Tests for Aegis.check_capability — the capability arbiter."""
from __future__ import annotations

import pytest

from nexus.kernel.aegis import Aegis, CapabilityDecision, Verdict
from nexus.agents.manifest import Manifest, PermissionClass


def _aider_manifest() -> Manifest:
    return Manifest.model_validate({
        "manifest_version": 1,
        "slug": "aider",
        "name": "aider",
        "version": "1.0.0",
        "system": False,
        "publisher": {"type": "org", "handle": "Aider-AI"},
        "category": "coding",
        "identity": {"mark": {"kind": "svg", "gradient": ["#fff", "#000"]}},
        "intents": [],
        "capabilities": {
            "tools": [
                {"name": "edit_file", "class": "Notable", "scope": "fs.write.workspace"},
                {"name": "search_repo", "class": "Routine"},
            ],
            "declared": {
                "Routine": ["fs.read.workspace"],
                "Notable": ["fs.write.workspace"],
                "Sensitive": ["process.shell"],
                "Privileged": [],
            },
        },
        "runtime": {"transport": "stdio", "command": "aider-mcp"},
        "trust": {"floor": 0.55, "default_tier": "ADVISOR"},
    })


@pytest.fixture
def aegis(tmp_path):
    db = tmp_path / "aegis.sqlite"
    a = Aegis(str(db))
    a.init_db()
    a.register_manifest(_aider_manifest())
    return a


def test_routine_capability_always_allowed(aegis):
    d = aegis.check_capability("aider", "fs.read.workspace")
    assert d.verdict is Verdict.ALLOW


def test_undeclared_capability_denied(aegis):
    d = aegis.check_capability("aider", "fs.write.home")
    assert d.verdict is Verdict.DENY
    assert "undeclared" in d.reason.lower()


def test_notable_at_observer_tier_prompts(aegis):
    # set_trust(slug, 0.0) — explicitly observer
    aegis.set_trust("aider", 0.0)
    d = aegis.check_capability("aider", "fs.write.workspace")
    assert d.verdict is Verdict.PROMPT
    assert d.permission_class is PermissionClass.NOTABLE


def test_notable_at_executor_tier_auto_grants(aegis):
    # bump trust to Executor (0.75+)
    aegis.set_trust("aider", 0.80)
    d = aegis.check_capability("aider", "fs.write.workspace")
    assert d.verdict is Verdict.ALLOW
    assert "executor" in d.reason.lower() or "auto" in d.reason.lower()


def test_sensitive_at_executor_still_prompts(aegis):
    aegis.set_trust("aider", 0.80)
    d = aegis.check_capability("aider", "process.shell")
    assert d.verdict is Verdict.PROMPT
    assert d.permission_class is PermissionClass.SENSITIVE


def test_workspace_grant_overrides_prompt(aegis):
    aegis.grant("aider", "fs.write.workspace", workspace_id="client-work")
    d = aegis.check_capability("aider", "fs.write.workspace", workspace_id="client-work")
    assert d.verdict is Verdict.ALLOW


def test_grant_does_not_leak_across_workspaces(aegis):
    aegis.grant("aider", "fs.write.workspace", workspace_id="client-work")
    d = aegis.check_capability("aider", "fs.write.workspace", workspace_id="other")
    assert d.verdict is Verdict.PROMPT


def test_trust_collapse_revokes_grants(aegis):
    aegis.set_trust("aider", 0.80)
    aegis.grant("aider", "fs.write.workspace", workspace_id="client-work")
    aegis.set_trust("aider", 0.40)  # collapse below 0.50
    d = aegis.check_capability("aider", "fs.write.workspace", workspace_id="client-work")
    assert d.verdict is Verdict.PROMPT


def test_revoke_grant_flips_decision_back_to_prompt(aegis):
    """Granting then revoking returns the decision to PROMPT."""
    aegis.grant("aider", "fs.write.workspace", workspace_id="client-work")
    d1 = aegis.check_capability("aider", "fs.write.workspace", workspace_id="client-work")
    assert d1.verdict is Verdict.ALLOW

    aegis.revoke_grant("aider", "fs.write.workspace", workspace_id="client-work")
    d2 = aegis.check_capability("aider", "fs.write.workspace", workspace_id="client-work")
    assert d2.verdict is Verdict.PROMPT


def test_global_grant_applies_in_any_workspace(aegis):
    """A grant with workspace_id=None is honored across all workspaces."""
    aegis.grant("aider", "fs.write.workspace")  # global
    for ws in (None, "client-work", "design-rnd", "research"):
        d = aegis.check_capability("aider", "fs.write.workspace", workspace_id=ws)
        assert d.verdict is Verdict.ALLOW, f"global grant failed in workspace={ws!r}"


def test_collapse_on_agent_without_grants_is_a_noop(aegis):
    """A trust collapse on an agent with no grants must not crash or fire spurious events."""
    # aider has zero grants here; setting trust low should not raise
    aegis.set_trust("aider", 0.20)
    # Subsequent decisions still work normally
    d = aegis.check_capability("aider", "fs.read.workspace")
    assert d.verdict is Verdict.ALLOW  # Routine — unaffected by trust
