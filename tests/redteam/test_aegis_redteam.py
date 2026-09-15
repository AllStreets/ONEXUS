"""Adversarial tests against Aegis — written to break it, not to confirm it works.

The existing suite under tests/kernel/ checks that Aegis does what it intends. This file
asks the opposite question: given the guarantees the README makes to a user, which ones
actually hold when someone is trying to get around them?

Every test here encodes REAL current behaviour, so the suite passes. Tests marked
FINDING document a gap between what the product promises and what the code enforces;
tests marked HOLDS document a defence that survived the attack. Both matter — a
red-team writeup that only lists wins is marketing.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from nexus.kernel.aegis import Aegis, TrustTier, Verdict, _is_within, _REWARD
from nexus.agents.manifest import Manifest


def _manifest(slug: str, *, notable=(), sensitive=(), privileged=(), routine=()) -> Manifest:
    return Manifest.model_validate({
        "manifest_version": 1,
        "slug": slug, "name": slug, "version": "1.0.0", "system": False,
        "publisher": {"type": "org", "handle": "redteam"},
        "category": "test",
        "identity": {"mark": {"kind": "svg", "gradient": ["#fff", "#000"]}},
        "intents": [],
        "capabilities": {
            "tools": [],
            "declared": {
                "Routine": list(routine),
                "Sensitive": list(sensitive),
                "Privileged": list(privileged),
                "Notable": list(notable),
            },
        },
        "runtime": {"transport": "stdio", "command": "x"},
    })


@pytest.fixture
def aegis(tmp_path):
    a = Aegis(str(tmp_path / "aegis.db"))
    a.init_db()
    return a


# ─────────────────────────────────────────────────────────────────────────────
# A1. Does "revoke" actually stop an agent?
# ─────────────────────────────────────────────────────────────────────────────

def test_FIXED_F1_revoke_now_stops_an_agent_holding_an_explicit_grant(aegis):
    """F1, fixed. revoke() used to zero trust while leaving grants intact, and the
    arbiter checks grants BEFORE it reads trust — so a revoked agent at trust 0.0 in
    tier OBSERVER kept working. The attack was one line: hold any grant, get revoked.

    revoke() now collapses grants as well as trust. Regression test for the kill switch.
    """
    aegis.register_manifest(_manifest("mole", notable=["net.fetch"]))
    aegis.grant("mole", "net.fetch")
    assert aegis.check_capability("mole", "net.fetch").verdict is Verdict.ALLOW

    aegis.revoke("mole")

    assert aegis.get_trust("mole") == 0.0
    assert aegis.get_tier("mole") == TrustTier.OBSERVER
    assert aegis.check_capability("mole", "net.fetch").verdict is not Verdict.ALLOW


def test_the_documented_workaround_does_stop_it(aegis):
    """HOLDS — set_trust(0.0) performs the grant cleanup that revoke() skips.
    The fix for A1 is to make revoke() call this path; the capability already exists.
    """
    aegis.register_manifest(_manifest("mole", notable=["net.fetch"]))
    aegis.grant("mole", "net.fetch")

    aegis.set_trust("mole", 0.0)

    assert aegis.check_capability("mole", "net.fetch").verdict is not Verdict.ALLOW


# ─────────────────────────────────────────────────────────────────────────────
# A2. Is trust collapse reachable by the path an agent actually takes?
# ─────────────────────────────────────────────────────────────────────────────

def test_FIXED_F2_trust_collapse_now_fires_on_every_path_that_lowers_trust(aegis):
    """F2, fixed. The collapse used to live inline in set_trust(), so containment
    depended on which function moved the score rather than on the score itself.

    Two agents reach the same sub-0.50 score by opposite routes. Both must end up
    contained.
    """
    for slug in ("by-admin", "by-failure"):
        aegis.register_manifest(_manifest(slug, notable=["net.fetch"]))
        aegis.grant(slug, "net.fetch")
        aegis.set_trust(slug, 0.90)

    # Path 1: an operator drags the score down.
    aegis.set_trust("by-admin", 0.46)

    # Path 2: the agent fails its way down to the same neighbourhood.
    while aegis.get_trust("by-failure") >= 0.50:
        aegis.record_outcome("by-failure", success=False)

    assert aegis.get_trust("by-admin") < 0.50
    assert aegis.get_trust("by-failure") < 0.50

    # Same score, same outcome — which is the point.
    assert aegis.check_capability("by-admin", "net.fetch").verdict is not Verdict.ALLOW
    assert aegis.check_capability("by-failure", "net.fetch").verdict is not Verdict.ALLOW


# ─────────────────────────────────────────────────────────────────────────────
# A3. Can an agent buy autonomy with cheap work?
# ─────────────────────────────────────────────────────────────────────────────

def test_FINDING_seven_trivial_successes_buy_executor_tier_and_auto_grant(aegis):
    """FINDING — trust is scored per OUTCOME, never per RISK. Every success is worth
    +0.12 whether it read a temp file or moved money, and nothing rate-limits how fast
    outcomes can be recorded.

    From a cold start (trust 0.0), seven successes cross the 0.75 EXECUTOR threshold,
    at which point every Notable capability in the manifest auto-grants with no prompt.
    """
    aegis.register_manifest(_manifest("grinder", notable=["net.fetch", "fs.write.home"]))

    # Cold start: Notable is gated behind a prompt.
    assert aegis.check_capability("grinder", "net.fetch").verdict is Verdict.PROMPT

    needed = 0
    while aegis.get_trust("grinder") < 0.75:
        aegis.record_outcome("grinder", success=True)
        needed += 1

    assert needed == 7, f"expected 7 cheap successes, took {needed}"
    assert aegis.get_tier("grinder") == TrustTier.EXECUTOR

    # Nothing was granted by a human. Both Notable capabilities are now live.
    for cap in ("net.fetch", "fs.write.home"):
        d = aegis.check_capability("grinder", cap)
        assert d.verdict is Verdict.ALLOW
        assert "auto-grant" in d.reason


def test_HOLDS_privileged_never_auto_grants_no_matter_how_high_trust_climbs(aegis):
    """HOLDS — the ladder has a ceiling. Privileged capabilities refuse to auto-grant
    even at trust 1.0, which is the single most important property in the file.
    """
    aegis.register_manifest(_manifest("grinder", privileged=["system.exec"]))
    aegis.set_trust("grinder", 1.0)
    assert aegis.get_tier("grinder") == TrustTier.AUTONOMOUS

    assert aegis.check_capability("grinder", "system.exec").verdict is Verdict.PROMPT


# ─────────────────────────────────────────────────────────────────────────────
# A4. Manifest boundary
# ─────────────────────────────────────────────────────────────────────────────

def test_HOLDS_undeclared_capability_is_denied_even_at_full_trust(aegis):
    """HOLDS — the manifest is a real boundary, not a hint. Full trust does not
    conjure a capability the agent never declared.
    """
    aegis.register_manifest(_manifest("liar", notable=["net.fetch"]))
    aegis.set_trust("liar", 1.0)

    d = aegis.check_capability("liar", "fs.write.home")
    assert d.verdict is Verdict.DENY
    assert "undeclared" in d.reason


def test_HOLDS_an_unregistered_agent_is_denied_outright(aegis):
    d = aegis.check_capability("ghost", "net.fetch")
    assert d.verdict is Verdict.DENY
    assert "no manifest" in d.reason


# ─────────────────────────────────────────────────────────────────────────────
# A5. Grant scoping
# ─────────────────────────────────────────────────────────────────────────────

def test_HOLDS_a_workspace_scoped_grant_does_not_leak_to_another_workspace(aegis):
    aegis.register_manifest(_manifest("scoped", notable=["net.fetch"]))
    aegis.grant("scoped", "net.fetch", workspace_id="ws-a")

    assert aegis.check_capability("scoped", "net.fetch", "ws-a").verdict is Verdict.ALLOW
    assert aegis.check_capability("scoped", "net.fetch", "ws-b").verdict is not Verdict.ALLOW


def test_a_global_grant_deliberately_covers_every_workspace(aegis):
    """HOLDS (by design) — a grant with no workspace is global. Documented so the
    blast radius of clicking "always allow" is explicit rather than discovered.
    """
    aegis.register_manifest(_manifest("global", notable=["net.fetch"]))
    aegis.grant("global", "net.fetch")

    for ws in ("ws-a", "ws-b", None):
        assert aegis.check_capability("global", "net.fetch", ws).verdict is Verdict.ALLOW


# ─────────────────────────────────────────────────────────────────────────────
# A6. Path containment
# ─────────────────────────────────────────────────────────────────────────────

def test_HOLDS_path_containment_rejects_traversal_and_sibling_prefixes(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    (root / "inside.txt").touch()

    # A sibling directory that merely shares a prefix must not count as inside.
    sibling = tmp_path / "workspace-evil"
    sibling.mkdir()
    (sibling / "secret.txt").touch()

    assert _is_within(root / "inside.txt", root) is True
    assert _is_within(sibling / "secret.txt", root) is False
    assert _is_within(root / ".." / "workspace-evil" / "secret.txt", root) is False


@pytest.mark.skipif(os.name == "nt", reason="symlink semantics differ on Windows")
def test_HOLDS_a_symlink_out_of_the_workspace_is_resolved_and_refused(tmp_path):
    """HOLDS — _is_within resolves before comparing, so planting a symlink inside an
    allowed root does not smuggle a path outside it.
    """
    root = tmp_path / "workspace"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("x")

    escape = root / "escape.txt"
    escape.symlink_to(outside / "secret.txt")

    assert escape.exists()            # the link is usable...
    assert _is_within(escape, root) is False   # ...and still refused


# ─────────────────────────────────────────────────────────────────────────────
# A7. Audit integrity
# ─────────────────────────────────────────────────────────────────────────────

def test_HOLDS_every_trust_movement_lands_in_history_including_the_revocation(aegis):
    aegis.register_manifest(_manifest("watched", notable=["net.fetch"]))
    aegis.record_outcome("watched", success=True)
    aegis.record_outcome("watched", success=False)
    aegis.revoke("watched")

    reasons = [h["reason"] for h in aegis.get_trust_history("watched")]
    assert "positive_outcome" in reasons
    assert "negative_outcome" in reasons
    assert "revoked" in reasons


def test_FIXED_F4_the_ledger_and_the_world_now_agree_about_a_revocation(aegis):
    """F4, fixed. The audit consequence of F1: the log used to show a clean `revoked`
    event while the grant stayed live, so an auditor reconstructing the incident would
    confidently conclude the agent was contained when it wasn't.

    A log that faithfully records an action which had no effect is worse than no log.
    """
    aegis.register_manifest(_manifest("mole", notable=["net.fetch"]))
    aegis.grant("mole", "net.fetch")
    aegis.revoke("mole")

    assert any(h["reason"] == "revoked" for h in aegis.get_trust_history("mole"))
    assert aegis.check_capability("mole", "net.fetch").verdict is not Verdict.ALLOW
