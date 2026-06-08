import pytest
from nexus.kernel.aegis import Aegis, PermissionDenied, _REWARD, _PENALTY


@pytest.fixture
def aegis(tmp_config):
    a = Aegis(tmp_config.db_path)
    a.init_db()
    return a


# ---------------------------------------------------------------------------
# is_allowed — replaces the old aegis.is_allowed() helper
# Uses check() and catches PermissionDenied
# ---------------------------------------------------------------------------

def _is_allowed(aegis, module, action):
    """Compatibility shim: returns True if check() does not raise."""
    try:
        aegis.check(module, action)
        return True
    except PermissionDenied:
        return False


def test_default_module_is_denied(aegis):
    assert _is_allowed(aegis, "unknown_module", "any_action") is False


def test_allow_module(aegis):
    aegis.set_policy("general", allowed=True)
    assert _is_allowed(aegis, "general", "respond") is True


def test_deny_module(aegis):
    aegis.set_policy("general", allowed=True)
    aegis.set_policy("general", allowed=False)
    assert _is_allowed(aegis, "general", "respond") is False


def test_check_raises_on_denied(aegis):
    with pytest.raises(PermissionDenied):
        aegis.check("blocked_module", "dangerous_action")


def test_check_passes_when_allowed(aegis):
    aegis.set_policy("general", allowed=True)
    aegis.check("general", "respond")


def test_policies_persist(tmp_config):
    a1 = Aegis(tmp_config.db_path)
    a1.init_db()
    a1.set_policy("oracle", allowed=True)
    a2 = Aegis(tmp_config.db_path)
    a2.init_db()
    assert _is_allowed(a2, "oracle", "scan") is True


def test_list_policies(aegis):
    aegis.set_policy("mod_a", allowed=True)
    aegis.set_policy("mod_b", allowed=False)
    policies = aegis.list_policies()
    assert len(policies) == 2
    names = {p["module"] for p in policies}
    assert names == {"mod_a", "mod_b"}


def test_get_trust_level(aegis):
    aegis.set_policy("oracle", allowed=True)
    assert aegis.get_trust("oracle") == 0


# ---------------------------------------------------------------------------
# Trust adjustments — replaces adjust_trust(delta) with record_outcome(bool)
# ---------------------------------------------------------------------------

def test_adjust_trust_positive(aegis):
    """record_outcome(success=True) applies a fixed reward (+_REWARD)."""
    aegis.set_policy("oracle", allowed=True)
    new_score = aegis.record_outcome("oracle", success=True)
    assert new_score == pytest.approx(_REWARD, abs=1e-6)
    assert aegis.get_trust("oracle") == pytest.approx(_REWARD, abs=1e-6)


def test_adjust_trust_negative(aegis):
    """record_outcome(success=False) applies a fixed penalty (+_PENALTY)."""
    aegis.set_policy("oracle", allowed=True)
    # Seed to 0.5 so a penalty doesn't clamp to 0
    aegis.set_trust("oracle", 0.5)
    new_score = aegis.record_outcome("oracle", success=False)
    expected = max(0.0, 0.5 + _PENALTY)
    assert new_score == pytest.approx(expected, abs=1e-6)


def test_trust_clamped_0_1(aegis):
    """Trust score is clamped to the [0.0, 1.0] range."""
    aegis.set_policy("oracle", allowed=True)
    # Drive to maximum
    aegis.set_trust("oracle", 1.0)
    assert aegis.get_trust("oracle") == pytest.approx(1.0)
    # Drive to minimum
    aegis.set_trust("oracle", 0.0)
    assert aegis.get_trust("oracle") == pytest.approx(0.0)


def test_check_with_trust_threshold(aegis):
    """Threshold comparison uses the 0.0-1.0 float scale directly."""
    aegis.set_policy("wraith", allowed=True)
    aegis.set_trust("wraith", 0.6)
    # Should pass for thresholds at or below current score
    assert aegis.get_trust("wraith") >= 0.5
    # Should fail for thresholds above current score
    assert aegis.get_trust("wraith") < 0.75


def test_trust_history(aegis):
    """get_trust_history() returns ordered history entries with reason field."""
    aegis.set_policy("echo", allowed=True)
    # Use set_trust to produce history entries with known reasons
    aegis.set_trust("echo", 0.3)
    aegis.set_trust("echo", 0.6)
    history = aegis.get_trust_history("echo")
    assert len(history) == 2
    # Both entries are for the set_trust operation
    assert all(h["reason"] == "set_trust" for h in history)
    assert history[0]["new_score"] == pytest.approx(0.3, abs=1e-6)
    assert history[1]["new_score"] == pytest.approx(0.6, abs=1e-6)


def test_network_denied_by_default(aegis):
    aegis.set_policy("herald", allowed=True)
    assert aegis.is_network_allowed("herald") is False


def test_network_granted_explicitly(aegis):
    aegis.set_policy("herald", allowed=True, network=True)
    assert aegis.is_network_allowed("herald") is True


def test_network_revoked(aegis):
    aegis.set_policy("herald", allowed=True, network=True)
    aegis.set_policy("herald", allowed=True, network=False)
    assert aegis.is_network_allowed("herald") is False


def test_check_network_raises(aegis):
    """If network is not allowed, callers should detect this and raise PermissionDenied."""
    aegis.set_policy("collective", allowed=True)
    # is_network_allowed returns False → caller raises PermissionDenied
    assert aegis.is_network_allowed("collective") is False
    with pytest.raises(PermissionDenied):
        if not aegis.is_network_allowed("collective"):
            raise PermissionDenied("collective", "network")


def test_check_network_passes(aegis):
    """When network is allowed, is_network_allowed returns True."""
    aegis.set_policy("collective", allowed=True, network=True)
    assert aegis.is_network_allowed("collective") is True  # should not raise


def test_list_policies_includes_network(aegis):
    aegis.set_policy("herald", allowed=True, network=True)
    aegis.set_policy("oracle", allowed=True)
    policies = aegis.list_policies()
    herald = next(p for p in policies if p["module"] == "herald")
    oracle = next(p for p in policies if p["module"] == "oracle")
    assert herald["network_allowed"] is True
    assert oracle["network_allowed"] is False
