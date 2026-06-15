"""N3 kill-switch confirmation for Herald auto-accept (default-safe + observable)."""
from __future__ import annotations

import pytest

from nexus.config import NexusConfig
from nexus.kernel.chronicle import Chronicle
from nexus.modules.herald import HeraldModule, herald_autoaccept_enabled


def test_autoaccept_default_off(tmp_path, monkeypatch):
    monkeypatch.delenv("NEXUS_HERALD_AUTOACCEPT", raising=False)
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    config = NexusConfig()
    assert herald_autoaccept_enabled(config) is False


def test_autoaccept_env_on(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("NEXUS_HERALD_AUTOACCEPT", "1")
    config = NexusConfig()
    assert herald_autoaccept_enabled(config) is True


def test_autoaccept_kill_file_overrides_env(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("NEXUS_HERALD_AUTOACCEPT", "1")
    config = NexusConfig()
    (config.data_dir / "herald-autoaccept.kill").write_text("")
    assert herald_autoaccept_enabled(config) is False


async def test_autoaccept_skip_is_observable_in_chronicle(tmp_path, monkeypatch):
    monkeypatch.delenv("NEXUS_HERALD_AUTOACCEPT", raising=False)
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    config = NexusConfig()
    chronicle = Chronicle(str(tmp_path / "chronicle.db"))
    chronicle.init_db()
    herald = HeraldModule()
    neg = await herald.open_negotiation(
        {"chronicle": chronicle, "config": config},
        initiator="a", responder="b", capability="engram.write.workspace",
        workspace_id="ws1", terms={}, value=0.4)
    nid = neg["negotiation_id"]
    result = await herald.maybe_auto_accept(
        {"chronicle": chronicle, "config": config}, nid, by="b")
    assert result["auto_accepted"] is False
    assert result["reason"] == "kill_switch"
    assert chronicle.query(source="herald", action="autoaccept_skipped")
