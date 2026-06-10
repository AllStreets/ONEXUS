"""Tests for the AgentLauncher command allowlist (supply-chain guard).

A catalog adapter manifest is refreshed nightly from an upstream repo; an
entry with runnable: true and an arbitrary command must not reach exec.
"""

from __future__ import annotations

import pytest

from nexus.agents.catalog import AdapterDescriptor
from nexus.agents.launcher import (
    AgentLaunchError,
    AgentLauncher,
    _command_allowlist,
    _command_basename,
)


class _Entry:
    def __init__(self, slug: str) -> None:
        self.slug = slug
        self.name = slug
        self.category = "coding"
        self.runnable = True


class _FakeCatalog:
    def __init__(self, command: str) -> None:
        self._command = command

    def get_agent(self, slug: str):
        return _Entry(slug)

    def load_adapter(self, entry):
        return AdapterDescriptor(
            name=entry.slug,
            transport="stdio",
            command=self._command,
            args=[],
            env={},
            capabilities={},
            trust_floor=0.0,
            default_tier="OBSERVER",
        )


class _FakeKernel:
    provider_router = None


def _launcher(command: str) -> AgentLauncher:
    return AgentLauncher(catalog=_FakeCatalog(command), kernel=_FakeKernel())


def test_basename_helpers():
    assert _command_basename("/usr/bin/python3") == "python3"
    assert _command_basename("python") == "python"
    assert "python" in _command_allowlist()


@pytest.mark.parametrize("bad", ["rm", "/tmp/evil", "curl", "sh"])
def test_offlist_command_is_rejected(bad):
    with pytest.raises(AgentLaunchError) as exc:
        _launcher(bad).launch("x")
    assert exc.value.status == 400


@pytest.mark.parametrize("evil", ["python; rm -rf /", "python $(id)", "py`whoami`"])
def test_shell_metacharacters_rejected(evil):
    with pytest.raises(AgentLaunchError) as exc:
        _launcher(evil).launch("x")
    assert exc.value.status == 400


def test_empty_command_rejected():
    with pytest.raises(AgentLaunchError):
        _launcher("").launch("x")


def test_env_override_extends_allowlist(monkeypatch):
    monkeypatch.setenv("NEXUS_AGENT_COMMAND_ALLOWLIST", "my-custom-runner")
    assert "my-custom-runner" in _command_allowlist()
    assert "python" in _command_allowlist()  # defaults still present
