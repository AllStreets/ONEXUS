"""Tests for `onexus workspace` CLI sub-commands."""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from click.testing import CliRunner

from nexus.cli import main


@pytest.fixture()
def runner(tmp_path, monkeypatch):
    """Click test runner with NEXUS_DATA_DIR pointed at tmp_path."""
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    return CliRunner()


# ── workspace list ────────────────────────────────────────────────────────────


def test_list_empty(runner):
    result = runner.invoke(main, ["workspace", "list"])
    assert result.exit_code == 0
    assert "No workspaces" in result.output


def test_list_shows_created_workspace(runner):
    runner.invoke(main, ["workspace", "create", "--name", "My Work"])
    result = runner.invoke(main, ["workspace", "list"])
    assert result.exit_code == 0
    assert "my-work" in result.output


# ── workspace create ──────────────────────────────────────────────────────────


def test_create_basic(runner):
    result = runner.invoke(main, ["workspace", "create", "--name", "Alpha"])
    assert result.exit_code == 0
    assert "alpha" in result.output.lower()


def test_create_with_explicit_id(runner):
    result = runner.invoke(main, ["workspace", "create", "--name", "Beta", "--id", "beta-ws"])
    assert result.exit_code == 0
    assert "beta-ws" in result.output


def test_create_with_tone(runner):
    result = runner.invoke(main, ["workspace", "create", "--name", "Sage", "--tone", "SAGE"])
    assert result.exit_code == 0
    assert "SAGE" in result.output


def test_create_with_template(runner):
    result = runner.invoke(main, [
        "workspace", "create", "--name", "My Code", "--id", "my-code", "--template", "coding"
    ])
    assert result.exit_code == 0
    assert "my-code" in result.output


def test_create_duplicate_fails(runner):
    runner.invoke(main, ["workspace", "create", "--name", "Dup", "--id", "dup-ws"])
    result = runner.invoke(main, ["workspace", "create", "--name", "Dup2", "--id", "dup-ws"])
    assert result.exit_code != 0
    assert "already exists" in result.output


# ── workspace switch ──────────────────────────────────────────────────────────


def test_switch_sets_active(runner):
    runner.invoke(main, ["workspace", "create", "--name", "Focus", "--id", "focus-ws"])
    result = runner.invoke(main, ["workspace", "switch", "focus-ws"])
    assert result.exit_code == 0
    assert "focus-ws" in result.output

    list_result = runner.invoke(main, ["workspace", "list"])
    assert "*" in list_result.output


def test_switch_unknown_workspace_fails(runner):
    result = runner.invoke(main, ["workspace", "switch", "ghost"])
    assert result.exit_code != 0
    assert "not found" in result.output


# ── workspace destroy ─────────────────────────────────────────────────────────


def test_destroy_removes_workspace(runner):
    runner.invoke(main, ["workspace", "create", "--name", "Temp", "--id", "temp-ws"])
    result = runner.invoke(main, ["workspace", "destroy", "temp-ws", "--yes"])
    assert result.exit_code == 0
    assert "destroyed" in result.output

    list_result = runner.invoke(main, ["workspace", "list"])
    assert "temp-ws" not in list_result.output


def test_destroy_unknown_fails(runner):
    result = runner.invoke(main, ["workspace", "destroy", "ghost", "--yes"])
    assert result.exit_code != 0
    assert "not found" in result.output
