"""Tests for ONEXUS-Agents catalog integration via MCP tools."""
from __future__ import annotations

import json
import pytest
from pathlib import Path

from nexus.agents.catalog import AgentCatalog, AgentEntry, AdapterDescriptor
from nexus.config import NexusConfig
from nexus.kernel.aegis import Aegis
from nexus.kernel.chronicle import Chronicle
from nexus.kernel.engram import Engram
from nexus.kernel.pulse import Pulse
from nexus.mcp.tools import ToolHandlers


# ---------------------------------------------------------------------------
# Catalog fixtures
# ---------------------------------------------------------------------------

SAMPLE_AGENT = {
    "slug": "test-agent",
    "name": "Test Agent",
    "tagline": "A test agent for unit tests.",
    "category": "coding",
    "tags": ["testing", "cli"],
    "author": {"type": "user", "handle": "tester", "url": "https://github.com/tester"},
    "source": {
        "primary": "github",
        "github": "tester/test-agent",
        "huggingface": None,
        "homepage": None,
    },
    "license": "MIT",
    "metrics": {
        "stars": 1500,
        "downloads_30d": None,
        "last_commit_at": "2026-04-01T00:00:00Z",
        "first_commit_at": "2025-01-01T00:00:00Z",
    },
    "benchmarks": [],
    "runnable": True,
    "adapter_ref": "adapters/test-agent/mcp.json",
    "composite_score": 0.75,
    "rank_in_category": 1,
    "discovered_via": "seed",
    "first_seen_at": "2026-01-01T00:00:00Z",
    "last_refreshed_at": "2026-04-29T00:00:00Z",
}

SAMPLE_ADAPTER = {
    "name": "test-agent",
    "version": "0.1.0",
    "agent_slug": "test-agent",
    "category": "coding",
    "transport": "stdio",
    "command": "test-agent-mcp",
    "args": [],
    "env": {"API_KEY": {"required": True, "description": "API key"}},
    "capabilities": {"tools": ["run_code"], "resources": ["repo"]},
    "trust_floor": 0.50,
    "default_tier": "ADVISOR",
}

SAMPLE_AGENT_2 = {
    **SAMPLE_AGENT,
    "slug": "browser-bot",
    "name": "Browser Bot",
    "tagline": "Automated browser testing.",
    "category": "browser-automation",
    "tags": ["browser", "testing"],
    "runnable": False,
    "adapter_ref": None,
    "composite_score": 0.60,
    "rank_in_category": 2,
}


@pytest.fixture
def catalog_dir(tmp_path):
    """Create a mock catalog directory structure."""
    catalog = tmp_path / "catalog"

    # coding category
    coding_dir = catalog / "coding"
    coding_dir.mkdir(parents=True)
    (coding_dir / "test-agent.json").write_text(json.dumps(SAMPLE_AGENT))

    # browser-automation category
    browser_dir = catalog / "browser-automation"
    browser_dir.mkdir(parents=True)
    (browser_dir / "browser-bot.json").write_text(json.dumps(SAMPLE_AGENT_2))

    # _categories.json (skipped by loader)
    (catalog / "_categories.json").write_text(json.dumps({"version": 1}))

    # Adapter
    adapter_dir = tmp_path / "adapters" / "test-agent"
    adapter_dir.mkdir(parents=True)
    (adapter_dir / "mcp.json").write_text(json.dumps(SAMPLE_ADAPTER))

    return tmp_path


@pytest.fixture
def catalog(catalog_dir):
    return AgentCatalog(catalog_dir)


@pytest.fixture
def kernel_ctx_with_catalog(tmp_path, catalog_dir):
    """Build a kernel context with catalog configured."""
    config = NexusConfig(
        data_dir=tmp_path / "nexus_data",
        agents_catalog_path=str(catalog_dir),
    )
    db = str(config.db_path)
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
        aegis=aegis, pulse=pulse, config=config,
    )
    return {
        "cortex": cortex,
        "engram": engram,
        "chronicle": chronicle,
        "aegis": aegis,
        "pulse": pulse,
        "config": config,
    }


@pytest.fixture
def handlers_with_catalog(kernel_ctx_with_catalog):
    return ToolHandlers(kernel_ctx_with_catalog)


# ---------------------------------------------------------------------------
# AgentCatalog unit tests
# ---------------------------------------------------------------------------

class TestAgentCatalog:
    def test_load_count(self, catalog):
        assert catalog.count == 2

    def test_list_all(self, catalog):
        agents = catalog.list_agents()
        assert len(agents) == 2
        # Sorted by composite_score descending
        assert agents[0].slug == "test-agent"
        assert agents[1].slug == "browser-bot"

    def test_list_by_category(self, catalog):
        coding = catalog.list_agents(category="coding")
        assert len(coding) == 1
        assert coding[0].slug == "test-agent"

    def test_list_runnable_only(self, catalog):
        runnable = catalog.list_agents(runnable_only=True)
        assert len(runnable) == 1
        assert runnable[0].runnable is True

    def test_get_agent(self, catalog):
        agent = catalog.get_agent("test-agent")
        assert agent is not None
        assert agent.name == "Test Agent"
        assert agent.stars == 1500

    def test_get_agent_not_found(self, catalog):
        assert catalog.get_agent("nonexistent") is None

    def test_search(self, catalog):
        results = catalog.search("browser")
        assert len(results) == 1
        assert results[0].slug == "browser-bot"

    def test_search_by_tag(self, catalog):
        results = catalog.search("cli")
        assert len(results) >= 1

    def test_categories(self, catalog):
        cats = catalog.categories()
        assert "coding" in cats
        assert "browser-automation" in cats

    def test_load_adapter(self, catalog):
        agent = catalog.get_agent("test-agent")
        adapter = catalog.load_adapter(agent)
        assert adapter is not None
        assert adapter.command == "test-agent-mcp"
        assert adapter.transport == "stdio"
        assert adapter.trust_floor == 0.50
        assert "API_KEY" in adapter.env

    def test_load_adapter_not_runnable(self, catalog):
        agent = catalog.get_agent("browser-bot")
        adapter = catalog.load_adapter(agent)
        assert adapter is None

    def test_reload(self, catalog, catalog_dir):
        assert catalog.count == 2
        # Add a third agent
        new_agent = {**SAMPLE_AGENT, "slug": "new-agent", "name": "New Agent"}
        (catalog_dir / "catalog" / "coding" / "new-agent.json").write_text(
            json.dumps(new_agent)
        )
        catalog.reload()
        assert catalog.count == 3


class TestAgentEntry:
    def test_from_json(self):
        entry = AgentEntry.from_json(SAMPLE_AGENT)
        assert entry.slug == "test-agent"
        assert entry.source_github == "tester/test-agent"
        assert entry.stars == 1500


class TestAdapterDescriptor:
    def test_from_json(self):
        desc = AdapterDescriptor.from_json(SAMPLE_ADAPTER)
        assert desc.name == "test-agent"
        assert desc.transport == "stdio"
        assert desc.trust_floor == 0.50


# ---------------------------------------------------------------------------
# MCP tool handler tests
# ---------------------------------------------------------------------------

class TestAgentsBrowseTool:
    @pytest.mark.asyncio
    async def test_browse_all(self, handlers_with_catalog):
        result = await handlers_with_catalog.call("nexus_agents_browse", {})
        data = json.loads(result[0]["text"])
        assert data["count"] == 2
        assert len(data["agents"]) == 2

    @pytest.mark.asyncio
    async def test_browse_by_category(self, handlers_with_catalog):
        result = await handlers_with_catalog.call("nexus_agents_browse", {
            "category": "coding",
        })
        data = json.loads(result[0]["text"])
        assert data["count"] == 1
        assert data["agents"][0]["slug"] == "test-agent"

    @pytest.mark.asyncio
    async def test_browse_runnable_only(self, handlers_with_catalog):
        result = await handlers_with_catalog.call("nexus_agents_browse", {
            "runnable_only": True,
        })
        data = json.loads(result[0]["text"])
        assert data["count"] == 1

    @pytest.mark.asyncio
    async def test_browse_no_catalog(self):
        h = ToolHandlers({"config": NexusConfig(data_dir=Path("/tmp/test_nexus_empty"))})
        result = await h.call("nexus_agents_browse", {})
        data = json.loads(result[0]["text"])
        assert "error" in data


class TestAgentsSearchTool:
    @pytest.mark.asyncio
    async def test_search(self, handlers_with_catalog):
        result = await handlers_with_catalog.call("nexus_agents_search", {
            "query": "browser",
        })
        data = json.loads(result[0]["text"])
        assert data["count"] >= 1
        assert data["results"][0]["slug"] == "browser-bot"

    @pytest.mark.asyncio
    async def test_search_missing_query(self, handlers_with_catalog):
        result = await handlers_with_catalog.call("nexus_agents_search", {})
        data = json.loads(result[0]["text"])
        assert "error" in data


class TestAgentsInfoTool:
    @pytest.mark.asyncio
    async def test_info_with_adapter(self, handlers_with_catalog):
        result = await handlers_with_catalog.call("nexus_agents_info", {
            "slug": "test-agent",
        })
        data = json.loads(result[0]["text"])
        assert data["slug"] == "test-agent"
        assert data["runnable"] is True
        assert "adapter" in data
        assert data["adapter"]["command"] == "test-agent-mcp"
        assert data["adapter"]["trust_floor"] == 0.50

    @pytest.mark.asyncio
    async def test_info_not_found(self, handlers_with_catalog):
        result = await handlers_with_catalog.call("nexus_agents_info", {
            "slug": "nonexistent",
        })
        data = json.loads(result[0]["text"])
        assert "error" in data

    @pytest.mark.asyncio
    async def test_info_no_adapter(self, handlers_with_catalog):
        result = await handlers_with_catalog.call("nexus_agents_info", {
            "slug": "browser-bot",
        })
        data = json.loads(result[0]["text"])
        assert data["runnable"] is False
        assert "adapter" not in data
