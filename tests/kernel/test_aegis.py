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
