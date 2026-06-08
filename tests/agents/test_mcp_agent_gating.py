"""Tests that MCPAgent gates tool calls through Aegis.check_capability."""
from __future__ import annotations

import asyncio
import sys

import pytest

from nexus.agents.manifest import Manifest
from nexus.agents.mcp_agent import MCPAgent
from nexus.kernel.aegis import (
    Aegis,
    PermissionDenied,
    PermissionDecision,
    PermissionInbox,
)


def _echo_manifest(command: list[str], capability_class: str = "Routine",
                   scope: str | None = None) -> Manifest:
    tool = {"name": "echo", "class": capability_class}
    declared: dict[str, list[str]] = {"Routine": [], "Notable": [],
                                       "Sensitive": [], "Privileged": []}
    if scope is not None:
        tool["scope"] = scope
        declared[capability_class].append(scope)
    return Manifest.model_validate({
        "manifest_version": 1, "slug": "echoer", "name": "echoer",
        "version": "0.1.0", "system": False,
        "publisher": {"type": "org", "handle": "test"}, "category": "test",
        "identity": {"mark": {"kind": "svg", "gradient": ["#fff", "#000"]}},
        "intents": [],
        "capabilities": {"tools": [tool], "declared": declared},
        "runtime": {"transport": "stdio", "command": command[0], "args": command[1:]},
    })


@pytest.fixture
def fake_server_path(tmp_path):
    path = tmp_path / "echo_server.py"
    path.write_text(
        "import asyncio\n"
        "from mcp.server import Server\n"
        "from mcp.server.stdio import stdio_server\n"
        "from mcp.types import Tool, TextContent\n"
        "srv = Server('echoer')\n"
        "@srv.list_tools()\n"
        "async def list_tools():\n"
        "    return [Tool(name='echo', description='echo', inputSchema={'type':'object','properties':{'message':{'type':'string'}}})]\n"
        "@srv.call_tool()\n"
        "async def call_tool(name, arguments):\n"
        "    return [TextContent(type='text', text=f\"echo:{arguments.get('message','')}\")]\n"
        "async def main():\n"
        "    async with stdio_server() as (r, w):\n"
        "        await srv.run(r, w, srv.create_initialization_options())\n"
        "asyncio.run(main())\n"
    )
    return path


@pytest.mark.asyncio
async def test_routine_mcp_tool_passes_through(tmp_path, fake_server_path):
    aegis = Aegis(str(tmp_path / "a.db"))
    aegis.init_db()
    manifest = _echo_manifest([sys.executable, str(fake_server_path)])
    aegis.register_manifest(manifest)
    agent = MCPAgent(manifest, aegis=aegis)
    await agent.start()
    try:
        result = await agent.call_tool("echo", {"message": "hi"})
        assert "echo:hi" in str(result)
    finally:
        await agent.stop()


@pytest.mark.asyncio
async def test_notable_mcp_tool_without_grant_denied(tmp_path, fake_server_path):
    aegis = Aegis(str(tmp_path / "a.db"))
    aegis.init_db()
    manifest = _echo_manifest(
        [sys.executable, str(fake_server_path)],
        capability_class="Notable", scope="fs.write.workspace",
    )
    aegis.register_manifest(manifest)
    agent = MCPAgent(manifest, aegis=aegis)
    await agent.start()
    try:
        with pytest.raises(PermissionDenied):
            await agent.call_tool("echo", {"message": "hi"})
    finally:
        await agent.stop()


@pytest.mark.asyncio
async def test_notable_mcp_tool_with_inbox_allow_proceeds(tmp_path, fake_server_path):
    aegis = Aegis(str(tmp_path / "a.db"))
    aegis.init_db()
    inbox = PermissionInbox()
    manifest = _echo_manifest(
        [sys.executable, str(fake_server_path)],
        capability_class="Notable", scope="fs.write.workspace",
    )
    aegis.register_manifest(manifest)
    agent = MCPAgent(manifest, aegis=aegis, inbox=inbox)
    await agent.start()
    try:
        async def caller():
            return await agent.call_tool("echo", {"message": "hi"})
        task = asyncio.create_task(caller())
        await asyncio.sleep(0.05)
        ticket = inbox.pending()[0]
        inbox.answer(ticket.id, PermissionDecision.ALLOW_ONCE)
        result = await task
        assert "echo:hi" in str(result)
    finally:
        await agent.stop()
