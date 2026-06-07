"""Tests for MCPAgent — the subprocess MCP-over-stdio adapter.

These tests run a tiny in-repo fake MCP server (Python script) so we
don't depend on any external agent being installed.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from nexus.agents.mcp_agent import MCPAgent
from nexus.agents.manifest import Manifest


def _echo_manifest(command: list[str]) -> Manifest:
    return Manifest.model_validate({
        "manifest_version": 1,
        "slug": "echoer", "name": "echoer", "version": "0.1.0",
        "system": False,
        "publisher": {"type": "org", "handle": "test"},
        "category": "test",
        "identity": {"mark": {"kind": "svg", "gradient": ["#fff", "#000"]}},
        "intents": [{"name": "echo", "patterns": ["echo"], "weight": 1.0}],
        "capabilities": {
            "tools": [{"name": "echo", "class": "Routine"}],
            "declared": {"Routine": []},
        },
        "runtime": {"transport": "stdio", "command": command[0], "args": command[1:]},
    })


@pytest.fixture
def fake_server_path(tmp_path):
    """Write a tiny MCP server stub that echoes."""
    path = tmp_path / "echo_server.py"
    path.write_text(
        "import asyncio, sys\n"
        "from mcp.server import Server\n"
        "from mcp.server.stdio import stdio_server\n"
        "from mcp.types import Tool, TextContent\n"
        "\n"
        "srv = Server('echoer')\n"
        "\n"
        "@srv.list_tools()\n"
        "async def list_tools():\n"
        "    return [Tool(name='echo', description='echo', inputSchema={'type':'object','properties':{'message':{'type':'string'}}})]\n"
        "\n"
        "@srv.call_tool()\n"
        "async def call_tool(name, arguments):\n"
        "    return [TextContent(type='text', text=f\"echo:{arguments.get('message','')}\")]\n"
        "\n"
        "async def main():\n"
        "    async with stdio_server() as (r, w):\n"
        "        await srv.run(r, w, srv.create_initialization_options())\n"
        "\n"
        "asyncio.run(main())\n"
    )
    return path


@pytest.mark.asyncio
async def test_launches_subprocess_and_calls_tool(fake_server_path):
    manifest = _echo_manifest([sys.executable, str(fake_server_path)])
    agent = MCPAgent(manifest)
    await agent.start()
    try:
        result = await agent.call_tool("echo", {"message": "hi"})
        assert "echo:hi" in str(result)
    finally:
        await agent.stop()


@pytest.mark.asyncio
async def test_pause_and_wake_preserve_state(fake_server_path):
    manifest = _echo_manifest([sys.executable, str(fake_server_path)])
    agent = MCPAgent(manifest)
    await agent.start()
    try:
        agent.pause()
        with pytest.raises(RuntimeError):
            await agent.call_tool("echo", {"message": "x"})
        agent.wake()
        result = await agent.call_tool("echo", {"message": "back"})
        assert "echo:back" in str(result)
    finally:
        await agent.stop()


@pytest.mark.asyncio
async def test_stop_kills_subprocess(fake_server_path):
    manifest = _echo_manifest([sys.executable, str(fake_server_path)])
    agent = MCPAgent(manifest)
    await agent.start()
    pid = agent.pid
    assert pid is not None
    await agent.stop()
    # After stop, the process should not exist
    import os
    # Allow a brief grace period for SIGTERM to take effect
    import time
    for _ in range(20):
        try:
            os.kill(pid, 0)
            time.sleep(0.05)
        except ProcessLookupError:
            return  # success
    pytest.fail(f"subprocess {pid} still alive after stop()")
