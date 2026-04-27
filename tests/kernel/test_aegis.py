import pytest
from nexus.kernel.aegis import Aegis, PermissionDenied


@pytest.fixture
def aegis(tmp_config):
    a = Aegis(tmp_config.db_path)
    a.init_db()
    return a


def test_default_module_is_denied(aegis):
    assert aegis.is_allowed("unknown_module", "any_action") is False


def test_allow_module(aegis):
    aegis.set_policy("general", allowed=True)
    assert aegis.is_allowed("general", "respond") is True


def test_deny_module(aegis):
    aegis.set_policy("general", allowed=True)
    aegis.set_policy("general", allowed=False)
    assert aegis.is_allowed("general", "respond") is False


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
    assert a2.is_allowed("oracle", "scan") is True


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


def test_adjust_trust_positive(aegis):
    aegis.set_policy("oracle", allowed=True)
    aegis.adjust_trust("oracle", delta=10, reason="successful prediction")
    assert aegis.get_trust("oracle") == 10


def test_adjust_trust_negative(aegis):
    aegis.set_policy("oracle", allowed=True)
    aegis.adjust_trust("oracle", delta=30, reason="setup")
    aegis.adjust_trust("oracle", delta=-15, reason="bad prediction")
    assert aegis.get_trust("oracle") == 15


def test_trust_clamped_0_100(aegis):
    aegis.set_policy("oracle", allowed=True)
    aegis.adjust_trust("oracle", delta=200, reason="overflow test")
    assert aegis.get_trust("oracle") == 100
    aegis.adjust_trust("oracle", delta=-300, reason="underflow test")
    assert aegis.get_trust("oracle") == 0


def test_check_with_trust_threshold(aegis):
    aegis.set_policy("wraith", allowed=True)
    aegis.adjust_trust("wraith", delta=25, reason="earned")
    # Should pass if required trust <= current trust
    assert aegis.check_trust("wraith", required_trust=20) is True
    assert aegis.check_trust("wraith", required_trust=50) is False


def test_trust_history(aegis):
    aegis.set_policy("echo", allowed=True)
    aegis.adjust_trust("echo", delta=10, reason="good draft")
    aegis.adjust_trust("echo", delta=5, reason="style match")
    history = aegis.trust_history("echo")
    assert len(history) == 2
    assert history[0]["reason"] == "good draft"
