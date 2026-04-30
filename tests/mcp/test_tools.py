"""Tests for NEXUS MCP tool handlers."""
from __future__ import annotations

import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from nexus.config import NexusConfig
from nexus.kernel.aegis import Aegis, PermissionDenied
from nexus.kernel.chronicle import Chronicle
from nexus.kernel.engram import Engram
from nexus.kernel.pulse import Pulse
from nexus.mcp.tools import ToolHandlers, get_tool_definitions, TOOL_DEFINITIONS


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_config(tmp_path):
    return NexusConfig(data_dir=tmp_path / "nexus_data")


@pytest.fixture
def kernel_ctx(tmp_config):
    """Build a real kernel context with live SQLite-backed components."""
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
def handlers(kernel_ctx):
    return ToolHandlers(kernel_ctx)


@pytest.fixture
def _register_mock_module(kernel_ctx):
    """Register a simple mock module in cortex and allow it in Aegis."""
    mod = MagicMock()
    mod.name = "test_mod"
    mod.description = "A test module"
    mod.version = "0.0.1"
    mod.requires_network = False
    mod.handle = AsyncMock(return_value="mock response from test_mod")

    # Does not have analyze -> treated as a module, not agent
    if hasattr(mod, "analyze"):
        del mod.analyze

    cortex = kernel_ctx["cortex"]
    cortex.register_module(mod)

    aegis = kernel_ctx["aegis"]
    aegis.set_policy("test_mod", allowed=True)
    # Build trust to ~0.48 (4 successes: 4 * 0.12 = 0.48)
    for _ in range(4):
        aegis.record_outcome("test_mod", True)
    return mod


@pytest.fixture
def _register_mock_agent(kernel_ctx):
    """Register a mock agent (has analyze method) in cortex."""
    agent = MagicMock()
    agent.name = "test_agent"
    agent.description = "A test agent"
    agent.version = "0.0.1"
    agent.requires_network = False
    agent.handle = AsyncMock(return_value="agent analysis result")
    agent.analyze = AsyncMock(return_value="analysis result")
    agent.watch_events = []
    agent.coordination_targets = []

    cortex = kernel_ctx["cortex"]
    cortex.register_module(agent)

    aegis = kernel_ctx["aegis"]
    aegis.set_policy("test_agent", allowed=True)
    # Build trust to ~0.60 (5 successes: 5 * 0.12 = 0.60)
    for _ in range(5):
        aegis.record_outcome("test_agent", True)
    return agent


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

class TestToolDefinitions:
    def test_definitions_are_non_empty(self):
        defs = get_tool_definitions()
        assert len(defs) == 15

    def test_all_definitions_have_required_keys(self):
        for defn in get_tool_definitions():
            assert "name" in defn
            assert "description" in defn
            assert "inputSchema" in defn
            assert defn["inputSchema"]["type"] == "object"

    def test_all_names_are_unique(self):
        names = [d["name"] for d in get_tool_definitions()]
        assert len(names) == len(set(names))

    def test_all_names_start_with_nexus(self):
        for defn in get_tool_definitions():
            assert defn["name"].startswith("nexus_")


# ---------------------------------------------------------------------------
# nexus_message
# ---------------------------------------------------------------------------

class TestNexusMessage:
    @pytest.mark.asyncio
    async def test_missing_message(self, handlers):
        result = await handlers.call("nexus_message", {})
        assert "Error" in result[0]["text"]

    @pytest.mark.asyncio
    async def test_no_modules_loaded(self, handlers):
        result = await handlers.call("nexus_message", {"message": "hello"})
        text = result[0]["text"]
        assert "No modules loaded" in text

    @pytest.mark.asyncio
    async def test_routes_to_module(self, handlers, _register_mock_module):
        result = await handlers.call("nexus_message", {"message": "hello"})
        text = result[0]["text"]
        assert "mock response" in text

    @pytest.mark.asyncio
    async def test_no_cortex(self):
        h = ToolHandlers({})
        result = await h.call("nexus_message", {"message": "hello"})
        assert "Cortex" in result[0]["text"]


# ---------------------------------------------------------------------------
# nexus_route
# ---------------------------------------------------------------------------

class TestNexusRoute:
    @pytest.mark.asyncio
    async def test_missing_module(self, handlers):
        result = await handlers.call("nexus_route", {"message": "hi"})
        assert "Error" in result[0]["text"]

    @pytest.mark.asyncio
    async def test_missing_message(self, handlers):
        result = await handlers.call("nexus_route", {"module": "test_mod"})
        assert "Error" in result[0]["text"]

    @pytest.mark.asyncio
    async def test_module_not_found(self, handlers):
        result = await handlers.call("nexus_route", {"module": "nonexistent", "message": "hi"})
        assert "not found" in result[0]["text"]

    @pytest.mark.asyncio
    async def test_direct_route(self, handlers, _register_mock_module):
        result = await handlers.call("nexus_route", {
            "module": "test_mod",
            "message": "do something",
        })
        assert "mock response from test_mod" in result[0]["text"]

    @pytest.mark.asyncio
    async def test_denied_module(self, handlers, _register_mock_module, kernel_ctx):
        kernel_ctx["aegis"].set_policy("test_mod", allowed=False)
        result = await handlers.call("nexus_route", {
            "module": "test_mod",
            "message": "do something",
        })
        assert "not allowed" in result[0]["text"]

    @pytest.mark.asyncio
    async def test_module_exception(self, handlers, _register_mock_module):
        _register_mock_module.handle = AsyncMock(side_effect=RuntimeError("boom"))
        result = await handlers.call("nexus_route", {
            "module": "test_mod",
            "message": "crash",
        })
        assert "exception" in result[0]["text"].lower()


# ---------------------------------------------------------------------------
# nexus_memory_store / nexus_memory_query
# ---------------------------------------------------------------------------

class TestMemory:
    @pytest.mark.asyncio
    async def test_working_store_and_query(self, handlers):
        store_result = await handlers.call("nexus_memory_store", {
            "content": "value123",
            "tier": "working",
            "key": "mykey",
        })
        data = json.loads(store_result[0]["text"])
        assert data["stored"] is True
        assert data["tier"] == "working"

        query_result = await handlers.call("nexus_memory_query", {
            "query": "mykey",
            "tier": "working",
        })
        data = json.loads(query_result[0]["text"])
        assert data["found"] is True
        assert data["value"] == "value123"

    @pytest.mark.asyncio
    async def test_working_query_not_found(self, handlers):
        result = await handlers.call("nexus_memory_query", {
            "query": "missing",
            "tier": "working",
        })
        data = json.loads(result[0]["text"])
        assert data["found"] is False

    @pytest.mark.asyncio
    async def test_working_missing_key(self, handlers):
        result = await handlers.call("nexus_memory_store", {
            "content": "val",
            "tier": "working",
        })
        assert "Error" in result[0]["text"]

    @pytest.mark.asyncio
    async def test_episodic_store_and_query(self, handlers):
        store_result = await handlers.call("nexus_memory_store", {
            "content": "important event happened",
            "tier": "episodic",
        })
        data = json.loads(store_result[0]["text"])
        assert data["stored"] is True
        assert data["tier"] == "episodic"
        assert "id" in data

        query_result = await handlers.call("nexus_memory_query", {
            "query": "important",
            "tier": "episodic",
        })
        data = json.loads(query_result[0]["text"])
        assert data["tier"] == "episodic"
        assert data["count"] >= 1

    @pytest.mark.asyncio
    async def test_semantic_store_and_query(self, handlers):
        store_result = await handlers.call("nexus_memory_store", {
            "content": "Python is a programming language",
            "tier": "semantic",
            "category": "tech",
        })
        data = json.loads(store_result[0]["text"])
        assert data["stored"] is True
        assert data["category"] == "tech"

        query_result = await handlers.call("nexus_memory_query", {
            "query": "programming",
            "tier": "semantic",
            "category": "tech",
        })
        data = json.loads(query_result[0]["text"])
        assert data["tier"] == "semantic"
        assert data["count"] >= 1

    @pytest.mark.asyncio
    async def test_invalid_tier(self, handlers):
        result = await handlers.call("nexus_memory_store", {
            "content": "x",
            "tier": "invalid",
        })
        assert "Error" in result[0]["text"]

    @pytest.mark.asyncio
    async def test_missing_content(self, handlers):
        result = await handlers.call("nexus_memory_store", {
            "tier": "working",
            "key": "k",
        })
        assert "Error" in result[0]["text"]

    @pytest.mark.asyncio
    async def test_no_engram(self):
        h = ToolHandlers({})
        result = await h.call("nexus_memory_store", {
            "content": "x", "tier": "working", "key": "k",
        })
        assert "Engram" in result[0]["text"]


# ---------------------------------------------------------------------------
# nexus_trust_check / nexus_trust_adjust
# ---------------------------------------------------------------------------

class TestTrust:
    @pytest.mark.asyncio
    async def test_trust_check(self, handlers, kernel_ctx, _register_mock_module):
        result = await handlers.call("nexus_trust_check", {"module": "test_mod"})
        data = json.loads(result[0]["text"])
        assert data["module"] == "test_mod"
        assert 0.4 <= data["trust"] <= 0.5  # 4 successes * 0.12 = 0.48
        assert data["allowed"] is True
        assert data["tier"] == "ADVISOR"

    @pytest.mark.asyncio
    async def test_trust_check_missing_module(self, handlers):
        result = await handlers.call("nexus_trust_check", {})
        assert "Error" in result[0]["text"]

    @pytest.mark.asyncio
    async def test_trust_record_success(self, handlers, kernel_ctx, _register_mock_module):
        result = await handlers.call("nexus_trust_record", {
            "module": "test_mod",
            "success": True,
        })
        data = json.loads(result[0]["text"])
        assert data["delta"] == 0.12
        assert data["success"] is True
        assert data["new_trust"] > 0.48  # was ~0.48, now +0.12

    @pytest.mark.asyncio
    async def test_trust_record_failure(self, handlers, kernel_ctx, _register_mock_module):
        result = await handlers.call("nexus_trust_record", {
            "module": "test_mod",
            "success": False,
        })
        data = json.loads(result[0]["text"])
        assert data["delta"] == -0.22
        assert data["success"] is False

    @pytest.mark.asyncio
    async def test_trust_record_missing_fields(self, handlers):
        result = await handlers.call("nexus_trust_record", {"module": "x"})
        assert "Error" in result[0]["text"]

    @pytest.mark.asyncio
    async def test_trust_check_no_aegis(self):
        h = ToolHandlers({})
        result = await h.call("nexus_trust_check", {"module": "x"})
        assert "Aegis" in result[0]["text"]


# ---------------------------------------------------------------------------
# nexus_chronicle_query
# ---------------------------------------------------------------------------

class TestChronicle:
    @pytest.mark.asyncio
    async def test_chronicle_query_empty(self, handlers):
        result = await handlers.call("nexus_chronicle_query", {})
        data = json.loads(result[0]["text"])
        assert "events" in data

    @pytest.mark.asyncio
    async def test_chronicle_query_with_filter(self, handlers, kernel_ctx):
        kernel_ctx["chronicle"].log("test_source", "test_action", {"key": "val"})
        result = await handlers.call("nexus_chronicle_query", {
            "source": "test_source",
            "event_type": "test_action",
            "limit": 5,
        })
        data = json.loads(result[0]["text"])
        assert data["count"] >= 1
        assert data["events"][0]["source"] == "test_source"

    @pytest.mark.asyncio
    async def test_chronicle_no_instance(self):
        h = ToolHandlers({})
        result = await h.call("nexus_chronicle_query", {})
        assert "Chronicle" in result[0]["text"]


# ---------------------------------------------------------------------------
# nexus_modules_list
# ---------------------------------------------------------------------------

class TestModulesList:
    @pytest.mark.asyncio
    async def test_empty_list(self, handlers):
        result = await handlers.call("nexus_modules_list", {})
        data = json.loads(result[0]["text"])
        assert data["count"] == 0
        assert data["modules"] == []

    @pytest.mark.asyncio
    async def test_with_module_and_agent(
        self, handlers, _register_mock_module, _register_mock_agent,
    ):
        result = await handlers.call("nexus_modules_list", {})
        data = json.loads(result[0]["text"])
        assert data["count"] == 2
        names = {m["name"] for m in data["modules"]}
        assert "test_mod" in names
        assert "test_agent" in names

        # Verify type field
        for m in data["modules"]:
            if m["name"] == "test_agent":
                assert m["type"] == "agent"
            else:
                assert m["type"] == "module"


# ---------------------------------------------------------------------------
# nexus_module_allow / nexus_module_deny
# ---------------------------------------------------------------------------

class TestModuleAllowDeny:
    @pytest.mark.asyncio
    async def test_allow(self, handlers, kernel_ctx):
        result = await handlers.call("nexus_module_allow", {"module": "some_mod"})
        data = json.loads(result[0]["text"])
        assert data["allowed"] is True
        # Verify via check() -- no exception means allowed
        kernel_ctx["aegis"].check("some_mod", "handle")

    @pytest.mark.asyncio
    async def test_allow_with_network(self, handlers, kernel_ctx):
        result = await handlers.call("nexus_module_allow", {
            "module": "net_mod",
            "network": True,
        })
        data = json.loads(result[0]["text"])
        assert data["network_allowed"] is True
        assert kernel_ctx["aegis"].is_network_allowed("net_mod")

    @pytest.mark.asyncio
    async def test_deny(self, handlers, kernel_ctx):
        kernel_ctx["aegis"].set_policy("deny_mod", allowed=True)
        result = await handlers.call("nexus_module_deny", {"module": "deny_mod"})
        data = json.loads(result[0]["text"])
        assert data["allowed"] is False
        # Verify via check() -- should raise PermissionDenied
        with pytest.raises(PermissionDenied):
            kernel_ctx["aegis"].check("deny_mod", "handle")

    @pytest.mark.asyncio
    async def test_allow_missing_module(self, handlers):
        result = await handlers.call("nexus_module_allow", {})
        assert "Error" in result[0]["text"]


# ---------------------------------------------------------------------------
# nexus_status
# ---------------------------------------------------------------------------

class TestStatus:
    @pytest.mark.asyncio
    async def test_status_empty(self, handlers):
        result = await handlers.call("nexus_status", {})
        data = json.loads(result[0]["text"])
        assert data["system"] == "nexus"
        assert data["status"] == "running"
        assert data["modules_loaded"] == 0
        assert data["agents_loaded"] == 0

    @pytest.mark.asyncio
    async def test_status_with_modules(
        self, handlers, _register_mock_module, _register_mock_agent,
    ):
        result = await handlers.call("nexus_status", {})
        data = json.loads(result[0]["text"])
        assert data["modules_loaded"] == 1
        assert data["agents_loaded"] == 1
        assert "test_mod" in data["module_names"]
        assert "test_agent" in data["agent_names"]


# ---------------------------------------------------------------------------
# nexus_workflow_run
# ---------------------------------------------------------------------------

class TestWorkflowRun:
    @pytest.mark.asyncio
    async def test_missing_steps(self, handlers):
        result = await handlers.call("nexus_workflow_run", {})
        assert "Error" in result[0]["text"]

    @pytest.mark.asyncio
    async def test_empty_steps(self, handlers):
        result = await handlers.call("nexus_workflow_run", {"steps": []})
        assert "Error" in result[0]["text"]

    @pytest.mark.asyncio
    async def test_single_step(self, handlers, _register_mock_module):
        result = await handlers.call("nexus_workflow_run", {
            "steps": [{"module": "test_mod", "message": "do a thing"}],
        })
        data = json.loads(result[0]["text"])
        assert data["steps_completed"] == 1
        assert "mock response" in data["results"][0]["output"]

    @pytest.mark.asyncio
    async def test_chained_steps(self, handlers, _register_mock_module):
        _register_mock_module.handle = AsyncMock(
            side_effect=["step1 output", "step2 got: step1 output"],
        )
        result = await handlers.call("nexus_workflow_run", {
            "steps": [
                {"module": "test_mod", "message": "first"},
                {"module": "test_mod", "message": "process: {prev}"},
            ],
        })
        data = json.loads(result[0]["text"])
        assert data["steps_completed"] == 2
        # Second step should have received the message with {prev} replaced
        call_args = _register_mock_module.handle.call_args_list
        assert "step1 output" in call_args[1][0][0]

    @pytest.mark.asyncio
    async def test_workflow_module_not_found(self, handlers, _register_mock_module):
        result = await handlers.call("nexus_workflow_run", {
            "steps": [
                {"module": "test_mod", "message": "ok"},
                {"module": "nonexistent", "message": "fail"},
            ],
        })
        data = json.loads(result[0]["text"])
        assert data["steps_completed"] == 2
        assert "error" in data["results"][1]

    @pytest.mark.asyncio
    async def test_workflow_denied_module(self, handlers, _register_mock_module, kernel_ctx):
        kernel_ctx["aegis"].set_policy("test_mod", allowed=False)
        result = await handlers.call("nexus_workflow_run", {
            "steps": [{"module": "test_mod", "message": "blocked"}],
        })
        data = json.loads(result[0]["text"])
        assert "not allowed" in data["results"][0]["error"]


# ---------------------------------------------------------------------------
# Unknown tool
# ---------------------------------------------------------------------------

class TestUnknownTool:
    @pytest.mark.asyncio
    async def test_unknown_tool(self, handlers):
        result = await handlers.call("nonexistent_tool", {})
        assert "Unknown tool" in result[0]["text"]
