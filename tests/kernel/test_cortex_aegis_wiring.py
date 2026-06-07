"""Tests that built-in manifests get registered with Aegis at Cortex construction."""
from __future__ import annotations

import pytest

from nexus.kernel.aegis import Aegis
from nexus.kernel.cortex import Cortex
from nexus.kernel.engram import Engram
from nexus.kernel.chronicle import Chronicle
from nexus.kernel.pulse import Pulse
from nexus.config import NexusConfig


@pytest.fixture
def aegis_with_builtins(tmp_path):
    config = NexusConfig(data_dir=tmp_path)
    engram = Engram(str(tmp_path / "engram.db"))
    engram.init_db()
    chronicle = Chronicle(str(tmp_path / "chronicle.db"))
    chronicle.init_db()
    aegis = Aegis(str(tmp_path / "aegis.db"), chronicle=chronicle)
    aegis.init_db()
    pulse = Pulse()
    cortex = Cortex(engram, chronicle, aegis, pulse, config)
    cortex.register_builtin_manifests()
    return aegis


def test_council_manifest_is_registered_with_aegis(aegis_with_builtins):
    assert aegis_with_builtins.get_manifest("council") is not None


def test_all_ten_builtins_register(aegis_with_builtins):
    expected = ["council", "specter", "autonomic", "oracle", "wraith",
                "legacy", "consciousness", "sentry", "echo", "agents"]
    for slug in expected:
        assert aegis_with_builtins.get_manifest(slug) is not None, f"{slug} not registered"


def test_idempotent_registration(aegis_with_builtins):
    """Calling register_builtin_manifests twice is safe — second call is a no-op."""
    from nexus.kernel.cortex import default_builtin_registry
    default_builtin_registry().register_all(aegis_with_builtins)
    assert aegis_with_builtins.get_manifest("council") is not None
