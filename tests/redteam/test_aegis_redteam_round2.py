"""Red-team round 2: the boundary around Aegis, not the arbiter inside it.

Round 1 (test_aegis_redteam.py) attacked Aegis's decisions and they held. Its threat
model (docs/REDTEAM-AEGIS.md) named what sits outside them. This file attacks two of
those gaps directly, with real child processes:

  R2-1  a launched catalog agent reads a secret from the parent's environment
  R2-2  ONEXUS hands an agent provider API keys it never declared
  R2-3  an MCP manifest agent reads the parent's environment too
  R2-4  an edit made straight to the Chronicle file goes unnoticed

These landed first as FOUND tests asserting the broken behaviour (commit f2059f9), so the
history shows each gap was real before it was fixed. They are now FIXED regression tests.
The container sandbox and an egress proxy, which would stop an agent that reads ~ or opens
its own socket, are round 3; nothing here claims them.
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

def test_FIXED_R2_1_launched_agent_no_longer_reads_an_undeclared_parent_secret(monkeypatch):
    """launcher.py used to start the agent with env=dict(os.environ), so anything in the
    operator's shell reached it without its manifest asking. Now it gets a baseline plus
    what it declared."""
    monkeypatch.setenv(CANARY, SECRET)
    assert _child_sees(CANARY) == "<none>"


def test_HOLDS_R2_1_a_declared_variable_still_reaches_the_agent(monkeypatch):
    monkeypatch.setenv(CANARY, SECRET)
    assert _child_sees(CANARY, declared={CANARY: {"required": False}}) == SECRET


def test_HOLDS_R2_1_the_baseline_still_lets_an_agent_find_programs():
    assert _child_sees("PATH") not in ("", "<none>")


def test_HOLDS_R2_1_the_operator_can_pass_a_variable_through_explicitly(monkeypatch):
    monkeypatch.setenv(CANARY, SECRET)
    monkeypatch.setenv("NEXUS_AGENT_ENV_PASSTHROUGH", f"SOMETHING_ELSE, {CANARY}")
    assert _child_sees(CANARY) == SECRET


# ─────────────────────────────────────────────────────────────────────────────
# R2-2. ONEXUS injects provider keys the agent never declared
# ─────────────────────────────────────────────────────────────────────────────

def test_FIXED_R2_2_launcher_no_longer_injects_an_undeclared_provider_key(monkeypatch):
    """With a provider router configured, the launcher used to add ANTHROPIC_API_KEY to
    every agent's environment. Now only an agent that declares the variable gets it."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert _child_sees("ANTHROPIC_API_KEY", declared={}, router=_Router()) == "<none>"


def test_HOLDS_R2_2_an_agent_that_declares_the_key_still_gets_it(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    declared = {"ANTHROPIC_API_KEY": {"required": False}}
    assert _child_sees("ANTHROPIC_API_KEY", declared=declared, router=_Router()) == FAKE_KEY


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
async def test_FIXED_R2_3_mcp_agent_no_longer_reads_an_undeclared_parent_secret(monkeypatch, env_server):
    """mcp_agent.py used to spread **os.environ into the child, so declaring no env_keys
    still handed it everything."""
    monkeypatch.setenv(CANARY, SECRET)
    agent = MCPAgent(_env_manifest(env_server))
    await agent.start()
    try:
        result = await agent.call_tool("env", {"name": CANARY})
    finally:
        await agent.stop()
    assert "saw:<none>" in str(result)


# ─────────────────────────────────────────────────────────────────────────────
# R2-4. An edit to the Chronicle file goes unnoticed
# ─────────────────────────────────────────────────────────────────────────────

def _chronicle(tmp_path) -> tuple[Chronicle, str]:
    db = str(tmp_path / "chronicle.db")
    c = Chronicle(db)
    c.init_db()
    c.log("aegis", "deny", {"agent": "rt2", "capability": "network.outbound.evil.example"})
    c.log("aegis", "allow", {"agent": "rt2", "capability": "fs.read"})
    c.log("aegis", "allow", {"agent": "rt2", "capability": "fs.list"})
    return c, db


def test_FIXED_R2_4_editing_a_chronicle_row_is_caught(tmp_path):
    """Rewriting a deny to an allow straight in the file used to go unnoticed. Each row
    now chains to the one before it, and verify() names the row that was changed."""
    c, db = _chronicle(tmp_path)
    assert c.verify()["ok"] is True
    deny_id = next(e["event_id"] for e in c.query() if e["action"] == "deny")
    with sqlite3.connect(db) as raw:
        raw.execute("UPDATE chronicle SET action = 'allow' WHERE action = 'deny'")
    report = c.verify()
    assert report["ok"] is False and report["broken_at"] == deny_id


def test_FIXED_R2_4_deleting_a_chronicle_row_is_caught(tmp_path):
    c, db = _chronicle(tmp_path)
    with sqlite3.connect(db) as raw:
        raw.execute("DELETE FROM chronicle WHERE action = 'deny'")
    assert c.verify()["ok"] is False


def test_HOLDS_R2_4_rows_from_before_chaining_are_legacy_not_tampering(tmp_path):
    db = str(tmp_path / "old.db")
    with sqlite3.connect(db) as raw:  # a ledger written by the old code: no chain column
        raw.execute("CREATE TABLE chronicle (event_id TEXT PRIMARY KEY, timestamp TEXT NOT NULL, "
                    "source TEXT NOT NULL, action TEXT NOT NULL, payload TEXT NOT NULL DEFAULT '{}')")
        raw.execute("INSERT INTO chronicle VALUES ('old1', '2026-01-01T00:00:00+00:00', 'aegis', 'allow', '{}')")
    c = Chronicle(db)
    c.init_db()
    c.log("aegis", "allow", {"agent": "rt2"})
    report = c.verify()
    assert report == {"ok": True, "checked": 1, "legacy": 1, "broken_at": None, "reason": None}
    assert c.head()["rows"] == 1 and c.head()["chain"]
