"""Tests for the agent CLI subcommands."""
from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from nexus.cli import main


def _manifest_dict() -> dict:
    return {
        "manifest_version": 1,
        "slug": "test-agent",
        "name": "test-agent",
        "version": "0.1.0",
        "system": False,
        "publisher": {"type": "org", "handle": "test"},
        "category": "test",
        "identity": {"mark": {"kind": "svg", "gradient": ["#fff", "#000"]}},
        "intents": [],
        "capabilities": {
            "tools": [{"name": "handle", "class": "Routine"}],
            "declared": {"Routine": ["engram.read.workspace"]},
        },
        "runtime": {"transport": "stdio", "command": "test-agent-mcp"},
    }


def test_agent_install_persists_manifest(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    manifest_file = tmp_path / "manifest.json"
    manifest_file.write_text(json.dumps(_manifest_dict()))

    runner = CliRunner()
    result = runner.invoke(main, ["agent", "install", str(manifest_file), "--yes"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "agents" / "test-agent" / "manifest.json").exists()


def test_agent_install_with_dry_run_shows_plan(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    manifest_file = tmp_path / "manifest.json"
    manifest_file.write_text(json.dumps(_manifest_dict()))

    runner = CliRunner()
    result = runner.invoke(main, ["agent", "install", str(manifest_file), "--dry-run"])
    assert result.exit_code == 0
    assert "test-agent" in result.output
    assert "Routine" in result.output or "routine" in result.output.lower()
    # Dry run must not write
    assert not (tmp_path / "agents" / "test-agent").exists()


def test_agent_uninstall_removes(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    manifest_file = tmp_path / "manifest.json"
    manifest_file.write_text(json.dumps(_manifest_dict()))
    runner = CliRunner()
    runner.invoke(main, ["agent", "install", str(manifest_file), "--yes"])
    result = runner.invoke(main, ["agent", "uninstall", "test-agent", "--yes"])
    assert result.exit_code == 0
    assert not (tmp_path / "agents" / "test-agent").exists()


def test_agent_list_shows_installed(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    manifest_file = tmp_path / "manifest.json"
    manifest_file.write_text(json.dumps(_manifest_dict()))
    runner = CliRunner()
    runner.invoke(main, ["agent", "install", str(manifest_file), "--yes"])
    result = runner.invoke(main, ["agent", "list"])
    assert "test-agent" in result.output
