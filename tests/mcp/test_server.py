"""Tests for NEXUS MCP server initialisation and wiring."""
from __future__ import annotations

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from nexus.config import NexusConfig
from nexus.mcp.server import _build_kernel, _register_modules
from nexus.mcp.tools import get_tool_definitions
from nexus.mcp.resources import get_resource_definitions
from nexus.mcp.prompts import get_prompt_definitions, PromptHandlers


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_config(tmp_path):
    return NexusConfig(data_dir=tmp_path / "nexus_data")


# ---------------------------------------------------------------------------
# Kernel bootstrap
# ---------------------------------------------------------------------------

class TestBuildKernel:
    def test_returns_all_components(self, tmp_config):
        ctx = _build_kernel(tmp_config)
        assert "cortex" in ctx
        assert "engram" in ctx
        assert "chronicle" in ctx
        assert "aegis" in ctx
        assert "pulse" in ctx
        assert "config" in ctx

    def test_cortex_has_modules(self, tmp_config):
        ctx = _build_kernel(tmp_config)
        cortex = ctx["cortex"]
        # Should have registered at least some modules
        # (some may fail to import but general should always work)
        modules = cortex.list_modules()
        assert len(modules) > 0

    def test_general_module_registered(self, tmp_config):
        ctx = _build_kernel(tmp_config)
        assert "general" in ctx["cortex"].list_modules()

    def test_chronicle_logs_init(self, tmp_config):
        ctx = _build_kernel(tmp_config)
        events = ctx["chronicle"].query(source="mcp", action="kernel_init")
        assert len(events) >= 1

    def test_default_config_used_when_none(self, tmp_path):
        # Patch the default data dir to use tmp_path
        with patch("nexus.config._default_data_dir", return_value=tmp_path / "nexus"):
            ctx = _build_kernel(None)
            assert ctx["config"] is not None


# ---------------------------------------------------------------------------
# Module registration
# ---------------------------------------------------------------------------

class TestRegisterModules:
    def test_registers_general(self, tmp_config):
        ctx = _build_kernel(tmp_config)
        cortex = ctx["cortex"]
        aegis = ctx["aegis"]
        assert "general" in cortex.list_modules()
        assert aegis.is_allowed("general", "handle")

    def test_failed_imports_dont_crash(self, tmp_config):
        """Even if a module import fails, the server should still start."""
        from nexus.kernel.cortex import Cortex
        from nexus.kernel.aegis import Aegis
        from nexus.kernel.chronicle import Chronicle
        from nexus.kernel.engram import Engram
        from nexus.kernel.pulse import Pulse

        db = str(tmp_config.db_path)
        aegis = Aegis(db_path=db)
        aegis.init_db()
        cortex = Cortex(
            engram=Engram(db_path=Path(db)),
            chronicle=Chronicle(db_path=db),
            aegis=aegis, pulse=Pulse(), config=tmp_config,
        )
        # This should not raise even if some modules fail to import
        _register_modules(cortex, aegis)


# ---------------------------------------------------------------------------
# Tool / resource / prompt catalogue completeness
# ---------------------------------------------------------------------------

class TestCatalogueCompleteness:
    def test_twelve_tools_defined(self):
        assert len(get_tool_definitions()) == 12

    def test_four_resources_defined(self):
        assert len(get_resource_definitions()) == 4

    def test_three_prompts_defined(self):
        assert len(get_prompt_definitions()) == 3

    def test_tool_names_match_handlers(self, tmp_config):
        from nexus.mcp.tools import ToolHandlers
        ctx = _build_kernel(tmp_config)
        handlers = ToolHandlers(ctx)
        tool_names = {d["name"] for d in get_tool_definitions()}
        handler_names = set(handlers._dispatch.keys())
        assert tool_names == handler_names


# ---------------------------------------------------------------------------
# Prompt handlers
# ---------------------------------------------------------------------------

class TestPromptHandlers:
    @pytest.fixture
    def prompt_handlers(self, tmp_config):
        ctx = _build_kernel(tmp_config)
        return PromptHandlers(ctx)

    @pytest.mark.asyncio
    async def test_analyze_code(self, prompt_handlers):
        messages = await prompt_handlers.get_prompt("analyze_code", {
            "code": "print('hello')",
            "language": "python",
        })
        assert len(messages) == 3  # vex + arbiter + carve
        texts = [m["content"]["text"] for m in messages]
        assert any("vex" in t.lower() for t in texts)
        assert any("arbiter" in t.lower() for t in texts)
        assert any("carve" in t.lower() for t in texts)

    @pytest.mark.asyncio
    async def test_analyze_code_security_only(self, prompt_handlers):
        messages = await prompt_handlers.get_prompt("analyze_code", {
            "code": "x = eval(input())",
            "focus": "security",
        })
        assert len(messages) == 1
        assert "vex" in messages[0]["content"]["text"].lower()

    @pytest.mark.asyncio
    async def test_analyze_code_missing_code(self, prompt_handlers):
        messages = await prompt_handlers.get_prompt("analyze_code", {})
        assert "Error" in messages[0]["content"]["text"]

    @pytest.mark.asyncio
    async def test_security_scan(self, prompt_handlers):
        messages = await prompt_handlers.get_prompt("security_scan", {
            "target": "GET /api/users?id=1",
        })
        assert len(messages) == 2  # vex + bastion
        texts = [m["content"]["text"] for m in messages]
        assert any("vex" in t.lower() for t in texts)
        assert any("bastion" in t.lower() for t in texts)

    @pytest.mark.asyncio
    async def test_security_scan_code_only(self, prompt_handlers):
        messages = await prompt_handlers.get_prompt("security_scan", {
            "target": "some code",
            "scan_type": "code",
        })
        assert len(messages) == 1
        assert "vex" in messages[0]["content"]["text"].lower()

    @pytest.mark.asyncio
    async def test_summarize_default(self, prompt_handlers):
        messages = await prompt_handlers.get_prompt("summarize", {
            "content": "Long text here...",
        })
        assert len(messages) == 1
        assert "scribe" in messages[0]["content"]["text"].lower()

    @pytest.mark.asyncio
    async def test_summarize_expand(self, prompt_handlers):
        messages = await prompt_handlers.get_prompt("summarize", {
            "content": "Brief notes",
            "mode": "expand",
        })
        assert "kindle" in messages[0]["content"]["text"].lower()

    @pytest.mark.asyncio
    async def test_summarize_polish(self, prompt_handlers):
        messages = await prompt_handlers.get_prompt("summarize", {
            "content": "Draft text",
            "mode": "polish",
        })
        assert "kindle" in messages[0]["content"]["text"].lower()

    @pytest.mark.asyncio
    async def test_unknown_prompt(self, prompt_handlers):
        messages = await prompt_handlers.get_prompt("nonexistent", {})
        assert "Unknown" in messages[0]["content"]["text"]


# ---------------------------------------------------------------------------
# Server creation (only if mcp is installed)
# ---------------------------------------------------------------------------

class TestCreateServer:
    def test_create_server_without_mcp(self, tmp_config):
        """If mcp is not installed, create_server should raise."""
        from nexus.mcp.server import HAS_MCP
        if HAS_MCP:
            pytest.skip("mcp package is installed")
        from nexus.mcp.server import create_server
        with pytest.raises(RuntimeError, match="mcp"):
            create_server(tmp_config)
