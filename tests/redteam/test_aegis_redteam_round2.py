"""Red-team round 2: the boundary around Aegis, not the arbiter inside it.

Round 1 (test_aegis_redteam.py) attacked Aegis's decisions and they held. Its threat
model (docs/REDTEAM-AEGIS.md) named what sits outside them. This file attacks two of
those gaps directly, with real child processes:

  R2-1  a launched catalog agent reads a secret from the parent's environment
  R2-2  ONEXUS hands an agent provider API keys it never declared
  R2-3  an MCP manifest agent reads the parent's environment too
  R2-4  an edit made straight to the Chronicle file goes unnoticed

Tests marked FOUND encode the broken behaviour as it ships, so this file passes against
the current code and proves each gap is real. The fix flips them.
"""
from __future__ import annotations

import sqlite3
import sys

import pytest

from nexus.agents.catalog import AdapterDescriptor
from nexus.agents.launcher import AgentLauncher
from nexus.agents.manifest import Manifest
from nexus.agents.mcp_agent import MCPAgent
from nexus.kernel.chronicle import Chronicle

CANARY = "NEXUS_RT2_CANARY"
SECRET = "rt2-parent-secret-do-not-leak"
FAKE_KEY = "sk-ant-rt2-not-a-real-key"
PRINT = "import os, sys; sys.stdout.write(os.environ.get(sys.argv[1], '<none>')); sys.stdout.flush()"


class _Entry:
    def __init__(self, slug: str) -> None:
        self.slug, self.name, self.category, self.runnable = slug, slug, "coding", True


class _Catalog:
    def __init__(self, args: list[str], env: dict) -> None:
        self._args, self._env = args, env

    def get_agent(self, slug: str):
        return _Entry(slug)

    def load_adapter(self, entry):
        return AdapterDescriptor(
            name=entry.slug, transport="stdio", command=sys.executable, args=self._args,
            env=self._env, capabilities={}, trust_floor=0.0, default_tier="OBSERVER",
        )


class _Provider:
    def __init__(self, key: str) -> None:
        self._api_key = key


class _Router:
    def __init__(self) -> None:
        self._providers = {"anthropic": _Provider(FAKE_KEY)}


class _Recorder:
    """Stands in for the kernel's Aegis and Chronicle, which the launcher notifies."""

    def set_policy(self, *a, **k) -> None: ...

    def log(self, *a, **k) -> None: ...


class _Kernel:
    def __init__(self, router=None) -> None:
        self.provider_router = router
        self.aegis = _Recorder()
        self.chronicle = _Recorder()


def _child_sees(name: str, *, declared: dict | None = None, router=None) -> str:
    """Launch a catalog agent through AgentLauncher and return what it read for `name`."""
    launcher = AgentLauncher(catalog=_Catalog(["-c", PRINT, name], declared or {}), kernel=_Kernel(router))
    agent = launcher.launch("rt2")
    out, _ = agent.process.communicate(timeout=30)
    return out.decode()


# ─────────────────────────────────────────────────────────────────────────────
# R2-1. A catalog agent reads the parent's secrets
# ─────────────────────────────────────────────────────────────────────────────

def test_FOUND_R2_1_launched_agent_reads_an_undeclared_parent_secret(monkeypatch):
    """launcher.py starts the agent with env=dict(os.environ), so anything in the
    operator's shell (cloud credentials, tokens, keys) reaches the agent without its
    manifest asking and without Aegis seeing a call."""
    monkeypatch.setenv(CANARY, SECRET)
    assert _child_sees(CANARY) == SECRET


# ─────────────────────────────────────────────────────────────────────────────
# R2-2. ONEXUS injects provider keys the agent never declared
# ─────────────────────────────────────────────────────────────────────────────

def test_FOUND_R2_2_launcher_injects_an_undeclared_provider_key(monkeypatch):
    """With a provider router configured, the launcher adds ANTHROPIC_API_KEY to every
    agent's environment, declared or not."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert _child_sees("ANTHROPIC_API_KEY", declared={}, router=_Router()) == FAKE_KEY


# ─────────────────────────────────────────────────────────────────────────────
# R2-3. An MCP manifest agent reads the parent's secrets
# ─────────────────────────────────────────────────────────────────────────────

def _env_manifest(server: str) -> Manifest:
    return Manifest.model_validate({
        "manifest_version": 1, "slug": "envreader", "name": "envreader", "version": "0.1.0",
        "system": False, "publisher": {"type": "org", "handle": "redteam"}, "category": "test",
        "identity": {"mark": {"kind": "svg", "gradient": ["#fff", "#000"]}},
        "intents": [{"name": "env", "patterns": ["env"], "weight": 1.0}],
        "capabilities": {"tools": [{"name": "env", "class": "Routine"}], "declared": {"Routine": []}},
        "runtime": {"transport": "stdio", "command": sys.executable, "args": [server], "env_keys": []},
    })


@pytest.fixture
def env_server(tmp_path):
    path = tmp_path / "env_server.py"
    path.write_text(
        "import asyncio, os\n"
        "from mcp.server import Server\n"
        "from mcp.server.stdio import stdio_server\n"
        "from mcp.types import Tool, TextContent\n"
        "srv = Server('envreader')\n"
        "@srv.list_tools()\n"
        "async def list_tools():\n"
        "    return [Tool(name='env', description='env', inputSchema={'type':'object','properties':{'name':{'type':'string'}}})]\n"
        "@srv.call_tool()\n"
        "async def call_tool(name, arguments):\n"
        "    return [TextContent(type='text', text='saw:' + os.environ.get(arguments['name'], '<none>'))]\n"
        "async def main():\n"
        "    async with stdio_server() as (r, w):\n"
        "        await srv.run(r, w, srv.create_initialization_options())\n"
        "asyncio.run(main())\n"
    )
    return str(path)


@pytest.mark.asyncio
async def test_FOUND_R2_3_mcp_agent_reads_an_undeclared_parent_secret(monkeypatch, env_server):
    """mcp_agent.py spreads **os.environ into the child, so declaring no env_keys
    still hands it everything."""
    monkeypatch.setenv(CANARY, SECRET)
    agent = MCPAgent(_env_manifest(env_server))
    await agent.start()
    try:
        result = await agent.call_tool("env", {"name": CANARY})
    finally:
        await agent.stop()
    assert f"saw:{SECRET}" in str(result)


# ─────────────────────────────────────────────────────────────────────────────
# R2-4. An edit to the Chronicle file goes unnoticed
# ─────────────────────────────────────────────────────────────────────────────

def test_FOUND_R2_4_editing_the_chronicle_file_goes_unnoticed(tmp_path):
    """Chronicle only ever inserts, but its rows carry no chain, so a process running as
    the user can rewrite history in the SQLite file and nothing can tell."""
    db = str(tmp_path / "chronicle.db")
    c = Chronicle(db)
    c.init_db()
    c.log("aegis", "deny", {"agent": "rt2", "capability": "network.outbound.evil.example"})
    c.log("aegis", "allow", {"agent": "rt2", "capability": "fs.read"})

    with sqlite3.connect(db) as raw:
        raw.execute("UPDATE chronicle SET action = 'allow' WHERE action = 'deny'")

    assert {e["action"] for e in c.query()} == {"allow"}
    assert not hasattr(c, "verify")
