"""Tests for NEXUS MCP resource handlers."""
from __future__ import annotations

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

from nexus.config import NexusConfig
from nexus.kernel.aegis import Aegis
from nexus.kernel.chronicle import Chronicle
from nexus.kernel.engram import Engram
from nexus.kernel.pulse import Pulse
from nexus.mcp.resources import ResourceHandlers, get_resource_definitions


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_config(tmp_path):
    return NexusConfig(data_dir=tmp_path / "nexus_data")


@pytest.fixture
def kernel_ctx(tmp_config):
    db = str(tmp_config.db_path)
    engram = Engram(db_path=Path(db))
    engram.init_db()
    chronicle = Chronicle(db_path=db)
    chronicle.init_db()
    aegis = Aegis(db_path=db)
    aegis.init_db()
    pulse = Pulse()

    from nexus.kernel.cortex import Cortex
    cortex = Cortex(
        engram=engram, chronicle=chronicle,
        aegis=aegis, pulse=pulse, config=tmp_config,
    )
    return {
        "cortex": cortex,
        "engram": engram,
        "chronicle": chronicle,
        "aegis": aegis,
        "pulse": pulse,
        "config": tmp_config,
    }


@pytest.fixture
def resource_handlers(kernel_ctx):
    return ResourceHandlers(kernel_ctx)


@pytest.fixture
def _with_module(kernel_ctx):
    mod = MagicMock()
    mod.name = "test_mod"
    mod.description = "A test module"
    mod.version = "1.0.0"
    mod.requires_network = False
    if hasattr(mod, "analyze"):
        del mod.analyze
    kernel_ctx["cortex"].register_module(mod)
    kernel_ctx["aegis"].set_policy("test_mod", allowed=True)
    return mod


@pytest.fixture
def _with_agent(kernel_ctx):
    agent = MagicMock()
    agent.name = "test_agent"
    agent.description = "A test agent"
    agent.version = "2.0.0"
    agent.requires_network = True
    agent.analyze = AsyncMock()
    agent.watch_events = ["cortex.response"]
    agent.coordination_targets = ["other_agent"]
    kernel_ctx["cortex"].register_module(agent)
    kernel_ctx["aegis"].set_policy("test_agent", allowed=True, network=True)
    kernel_ctx["aegis"].adjust_trust("test_agent", 80, "test setup")
    return agent


# ---------------------------------------------------------------------------
# Definition tests
# ---------------------------------------------------------------------------

class TestResourceDefinitions:
    def test_definitions_count(self):
        defs = get_resource_definitions()
        assert len(defs) == 4

    def test_all_have_required_keys(self):
        for defn in get_resource_definitions():
            assert "uri" in defn
            assert "name" in defn
            assert "description" in defn
            assert "mimeType" in defn

    def test_all_uris_start_with_nexus(self):
        for defn in get_resource_definitions():
            assert defn["uri"].startswith("nexus://")


# ---------------------------------------------------------------------------
# nexus://modules
# ---------------------------------------------------------------------------

class TestModulesResource:
    @pytest.mark.asyncio
    async def test_empty(self, resource_handlers):
        result = json.loads(await resource_handlers.read("nexus://modules"))
        assert result["count"] == 0
        assert result["modules"] == []

    @pytest.mark.asyncio
    async def test_with_module(self, resource_handlers, _with_module):
        result = json.loads(await resource_handlers.read("nexus://modules"))
        assert result["count"] == 1
        assert result["modules"][0]["name"] == "test_mod"
        assert result["modules"][0]["version"] == "1.0.0"

    @pytest.mark.asyncio
    async def test_excludes_agents(self, resource_handlers, _with_module, _with_agent):
        result = json.loads(await resource_handlers.read("nexus://modules"))
        names = [m["name"] for m in result["modules"]]
        assert "test_mod" in names
        assert "test_agent" not in names


# ---------------------------------------------------------------------------
# nexus://agents
# ---------------------------------------------------------------------------

class TestAgentsResource:
    @pytest.mark.asyncio
    async def test_empty(self, resource_handlers):
        result = json.loads(await resource_handlers.read("nexus://agents"))
        assert result["agents"] == []

    @pytest.mark.asyncio
    async def test_with_agent(self, resource_handlers, _with_agent):
        result = json.loads(await resource_handlers.read("nexus://agents"))
        assert result["count"] == 1
        agent = result["agents"][0]
        assert agent["name"] == "test_agent"
        assert agent["trust"] == 80
        assert agent["tier"] == "autonomous"
        assert agent["watch_events"] == ["cortex.response"]
        assert agent["coordination_targets"] == ["other_agent"]

    @pytest.mark.asyncio
    async def test_excludes_modules(self, resource_handlers, _with_module, _with_agent):
        result = json.loads(await resource_handlers.read("nexus://agents"))
        names = [a["name"] for a in result["agents"]]
        assert "test_agent" in names
        assert "test_mod" not in names


# ---------------------------------------------------------------------------
# nexus://trust
# ---------------------------------------------------------------------------

class TestTrustResource:
    @pytest.mark.asyncio
    async def test_empty(self, resource_handlers):
        result = json.loads(await resource_handlers.read("nexus://trust"))
        assert "policies" in result

    @pytest.mark.asyncio
    async def test_with_policies(self, resource_handlers, _with_module, _with_agent):
        result = json.loads(await resource_handlers.read("nexus://trust"))
        assert result["count"] >= 2
        names = {p["module"] for p in result["policies"]}
        assert "test_mod" in names
        assert "test_agent" in names


# ---------------------------------------------------------------------------
# nexus://config
# ---------------------------------------------------------------------------

class TestConfigResource:
    @pytest.mark.asyncio
    async def test_config_values(self, resource_handlers, tmp_config):
        result = json.loads(await resource_handlers.read("nexus://config"))
        assert result["model_name"] == tmp_config.model_name
        assert result["llm_port"] == tmp_config.llm_port

    @pytest.mark.asyncio
    async def test_sensitive_fields_redacted(self, resource_handlers):
        result = json.loads(await resource_handlers.read("nexus://config"))
        # Should not contain raw API keys
        assert "openai_api_key" not in result
        assert "anthropic_api_key" not in result
        # Should have boolean indicators instead
        assert "openai_api_key_set" in result
        assert "anthropic_api_key_set" in result

    @pytest.mark.asyncio
    async def test_no_config(self):
        h = ResourceHandlers({})
        result = json.loads(await h.read("nexus://config"))
        assert "error" in result


# ---------------------------------------------------------------------------
# Unknown resource
# ---------------------------------------------------------------------------

class TestUnknownResource:
    @pytest.mark.asyncio
    async def test_unknown_uri(self, resource_handlers):
        result = json.loads(await resource_handlers.read("nexus://nonexistent"))
        assert "error" in result
