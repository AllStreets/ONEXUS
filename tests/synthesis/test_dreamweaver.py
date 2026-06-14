"""N2.2 — Dreamweaver deterministic overnight distillation + kill switch."""
from __future__ import annotations

import pytest

from nexus.config import NexusConfig
from nexus.kernel.chronicle import Chronicle
from nexus.kernel.engram import Engram
from nexus.synthesis.dreamweaver import Dreamweaver, dreamweaver_enabled


def _kernel(tmp_path):
    config = NexusConfig(data_dir=tmp_path)
    engram = Engram(config.db_path)
    engram.init_db()
    chronicle = Chronicle(str(config.db_path))
    chronicle.init_db()
    return config, engram, chronicle


def test_kill_switch_env(tmp_path, monkeypatch):
    config = NexusConfig(data_dir=tmp_path)
    monkeypatch.setenv("NEXUS_DREAMWEAVER", "0")
    assert dreamweaver_enabled(config) is False


def test_kill_switch_file(tmp_path, monkeypatch):
    config = NexusConfig(data_dir=tmp_path)
    monkeypatch.setenv("NEXUS_DREAMWEAVER", "1")
    (tmp_path / "dreamweaver.kill").write_text("")
    assert dreamweaver_enabled(config) is False


def test_default_enabled(tmp_path, monkeypatch):
    config = NexusConfig(data_dir=tmp_path)
    monkeypatch.delenv("NEXUS_DREAMWEAVER", raising=False)
    assert dreamweaver_enabled(config) is True


def test_run_once_distills_recurring_topic_into_atlas(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DREAMWEAVER", "1")
    config, engram, chronicle = _kernel(tmp_path)
    for _ in range(4):
        engram.episodic.store("review acme contract proposal", source="user")
    dw = Dreamweaver(config, engram, chronicle)
    brief = dw.run_once()
    assert brief["skipped"] is None
    assert brief["distilled_facts"] >= 1
    assert "headline" in brief
    beliefs = engram.atlas.beliefs("day")
    objs = {b["object"] for b in beliefs}
    assert "acme" in objs


def test_run_once_writes_morning_brief_to_chronicle(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DREAMWEAVER", "1")
    config, engram, chronicle = _kernel(tmp_path)
    for _ in range(4):
        engram.episodic.store("acme acme acme contract", source="user")
    dw = Dreamweaver(config, engram, chronicle)
    dw.run_once()
    rows = chronicle.query(source="dreamweaver", action="morning_brief")
    assert rows
    assert "headline" in rows[0]["payload"]


def test_killed_run_skips_and_writes_no_brief(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DREAMWEAVER", "0")
    config, engram, chronicle = _kernel(tmp_path)
    dw = Dreamweaver(config, engram, chronicle)
    brief = dw.run_once()
    assert brief["skipped"] == "kill_switch"
    assert chronicle.query(source="dreamweaver", action="morning_brief") == []
