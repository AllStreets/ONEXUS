"""
Tool definitions and handlers for the ONEXUS MCP server.

Exposes kernel operations, module routing, memory, trust scoring,
and audit log queries as MCP tools that any compliant client can invoke.
"""
from __future__ import annotations

import json
from typing import Any

try:
    from mcp.types import Tool, TextContent
    HAS_MCP = True
except ImportError:
    HAS_MCP = False


# ---------------------------------------------------------------------------
# Tool catalogue
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "nexus_message",
        "description": (
            "Send a message through Cortex routing. "
            "Cortex selects the best module/agent based on keyword matching "
            "and returns the routed response."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "The message to route through Cortex.",
                },
            },
            "required": ["message"],
        },
    },
    {
        "name": "nexus_route",
        "description": (
            "Route a message to a specific module or agent by name, "
            "bypassing Cortex keyword matching."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "module": {
                    "type": "string",
                    "description": "Name of the target module or agent.",
                },
                "message": {
                    "type": "string",
                    "description": "The message to send to the module.",
                },
            },
            "required": ["module", "message"],
        },
    },
    {
        "name": "nexus_memory_store",
        "description": (
            "Store content in Engram memory. "
            "Tier can be 'working' (key-value scratch), "
            "'episodic' (timestamped events), or "
            "'semantic' (categorised long-term knowledge)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The content to store.",
                },
                "tier": {
                    "type": "string",
                    "enum": ["working", "episodic", "semantic"],
                    "description": "Memory tier to store into.",
                },
                "key": {
                    "type": "string",
                    "description": "Key for working-memory storage (required when tier is 'working').",
                },
                "category": {
                    "type": "string",
                    "description": "Category tag for semantic memory (defaults to 'general').",
                },
            },
            "required": ["content", "tier"],
        },
    },
    {
        "name": "nexus_memory_query",
        "description": (
            "Query Engram memory. For episodic, performs full-text search. "
            "For semantic, performs similarity search. "
            "For working, retrieves a value by key."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (or key for working memory).",
                },
                "tier": {
                    "type": "string",
                    "enum": ["working", "episodic", "semantic"],
                    "description": "Memory tier to query.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results to return (default 10, ignored for working tier).",
                },
                "category": {
                    "type": "string",
                    "description": "Category filter for semantic queries.",
                },
            },
            "required": ["query", "tier"],
        },
    },
    {
        "name": "nexus_trust_check",
        "description": "Check the Aegis trust score (0.0-1.0) for a module.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "module": {
                    "type": "string",
                    "description": "Name of the module or agent.",
                },
            },
            "required": ["module"],
        },
    },
    {
        "name": "nexus_trust_record",
        "description": (
            "Record an outcome for a module. "
            "Success adds +0.12 trust, failure subtracts -0.22 (asymmetric)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "module": {
                    "type": "string",
                    "description": "Name of the module.",
                },
                "success": {
                    "type": "boolean",
                    "description": "Whether the module's response was correct/useful.",
                },
            },
            "required": ["module", "success"],
        },
    },
    {
        "name": "nexus_chronicle_query",
        "description": (
            "Query the Chronicle immutable audit log. "
            "Filter by source, event type, or both."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "Filter by source (e.g. 'cortex', module name).",
                },
                "event_type": {
                    "type": "string",
                    "description": "Filter by action/event type (e.g. 'route', 'permission_denied').",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results (default 50).",
                },
            },
            "required": [],
        },
    },
    {
        "name": "nexus_modules_list",
        "description": "List all registered modules and agents with their status and trust scores.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "nexus_module_allow",
        "description": "Enable a module or agent so Cortex can route messages to it.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "module": {
                    "type": "string",
                    "description": "Name of the module to enable.",
                },
                "network": {
                    "type": "boolean",
                    "description": "Also grant network access (default false).",
                },
            },
            "required": ["module"],
        },
    },
    {
        "name": "nexus_module_deny",
        "description": "Disable a module or agent, preventing Cortex from routing to it.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "module": {
                    "type": "string",
                    "description": "Name of the module to disable.",
                },
            },
            "required": ["module"],
        },
    },
    {
        "name": "nexus_status",
        "description": (
            "System status overview: loaded modules, active agents, "
            "memory stats, and trust summary."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "nexus_workflow_run",
        "description": (
            "Run a workflow pipeline -- a sequence of module invocations. "
            "Each step routes a message to a named module and passes the "
            "result to the next step."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "steps": {
                    "type": "array",
                    "description": "Ordered list of workflow steps.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "module": {
                                "type": "string",
                                "description": "Target module name.",
                            },
                            "message": {
                                "type": "string",
                                "description": (
                                    "Message to send. Use '{prev}' to inject "
                                    "the previous step's output."
                                ),
                            },
                        },
                        "required": ["module", "message"],
                    },
                },
            },
            "required": ["steps"],
        },
    },
    {
        "name": "nexus_agents_browse",
        "description": (
            "Browse the ONEXUS-Agents catalog. "
            "Lists available open-source agents by category and composite score. "
            "Requires NEXUS_AGENTS_CATALOG to be set."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Filter by category slug (e.g. 'coding', 'browser-automation').",
                },
                "runnable_only": {
                    "type": "boolean",
                    "description": "Only show agents with MCP adapters (default false).",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results (default 20).",
                },
            },
            "required": [],
        },
    },
    {
        "name": "nexus_agents_search",
        "description": (
            "Search the ONEXUS-Agents catalog by keyword. "
            "Matches against name, tagline, tags, and category."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results (default 20).",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "nexus_agents_info",
        "description": (
            "Get detailed info about a specific agent from the catalog, "
            "including its MCP adapter descriptor if runnable."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "slug": {
                    "type": "string",
                    "description": "Agent slug (e.g. 'aider', 'browser-use').",
                },
            },
            "required": ["slug"],
        },
    },
]


def get_tool_definitions() -> list[dict[str, Any]]:
    """Return the raw tool definitions as dicts (always available)."""
    return TOOL_DEFINITIONS


def get_mcp_tools() -> list[Any]:
    """Return Tool objects when the MCP SDK is available."""
    if not HAS_MCP:
        raise RuntimeError("mcp package is not installed")
    tools = []
    for defn in TOOL_DEFINITIONS:
        tools.append(Tool(
            name=defn["name"],
            description=defn["description"],
            inputSchema=defn["inputSchema"],
        ))
    return tools


# ---------------------------------------------------------------------------
# Handler dispatch
# ---------------------------------------------------------------------------

class ToolHandlers:
    """Dispatches MCP tool calls to kernel operations.

    Requires a kernel_context dict containing live instances of:
        cortex, engram, chronicle, aegis, pulse, config
    """

    def __init__(self, kernel_context: dict[str, Any]) -> None:
        self._ctx = kernel_context
        self._dispatch = {
            "nexus_message": self._handle_message,
            "nexus_route": self._handle_route,
            "nexus_memory_store": self._handle_memory_store,
            "nexus_memory_query": self._handle_memory_query,
            "nexus_trust_check": self._handle_trust_check,
            "nexus_trust_record": self._handle_trust_record,
            "nexus_chronicle_query": self._handle_chronicle_query,
            "nexus_modules_list": self._handle_modules_list,
            "nexus_module_allow": self._handle_module_allow,
            "nexus_module_deny": self._handle_module_deny,
            "nexus_status": self._handle_status,
            "nexus_workflow_run": self._handle_workflow_run,
            "nexus_agents_browse": self._handle_agents_browse,
            "nexus_agents_search": self._handle_agents_search,
            "nexus_agents_info": self._handle_agents_info,
        }

    async def call(self, tool_name: str, arguments: dict[str, Any]) -> list[dict[str, Any]]:
        """Execute a tool by name and return a list of content blocks."""
        handler = self._dispatch.get(tool_name)
        if handler is None:
            return [{"type": "text", "text": f"Unknown tool: {tool_name}"}]
        try:
            result = await handler(arguments)
            return [{"type": "text", "text": result}]
        except Exception as exc:
            return [{"type": "text", "text": f"Error in {tool_name}: {exc}"}]

    # ------------------------------------------------------------------
    # Individual handlers
    # ------------------------------------------------------------------

    async def _handle_message(self, args: dict[str, Any]) -> str:
        message = args.get("message")
        if not message:
            return "Error: 'message' is required."
        cortex = self._ctx.get("cortex")
        if cortex is None:
            return "Error: Cortex is not initialised."
        response = await cortex.process(message)
        return response

    async def _handle_route(self, args: dict[str, Any]) -> str:
        module_name = args.get("module")
        message = args.get("message")
        if not module_name:
            return "Error: 'module' is required."
        if not message:
            return "Error: 'message' is required."

        cortex = self._ctx.get("cortex")
        if cortex is None:
            return "Error: Cortex is not initialised."

        if module_name not in cortex._modules:
            available = ", ".join(sorted(cortex._modules.keys()))
            return f"Error: Module '{module_name}' not found. Available: {available}"

        # Bypass keyword matching -- directly invoke the module
        from nexus.kernel.aegis import PermissionDenied
        aegis = self._ctx.get("aegis")
        if aegis:
            try:
                aegis.check(module_name, "handle")
            except PermissionDenied:
                return f"Error: Module '{module_name}' is not allowed. Enable it first with nexus_module_allow."

        module = cortex._modules[module_name]
        context = cortex._build_context()
        try:
            response = await module.handle(message, context)
        except Exception as exc:
            return f"Error: Module '{module_name}' raised an exception: {exc}"

        # Log in chronicle
        chronicle = self._ctx.get("chronicle")
        if chronicle:
            chronicle.log("mcp", "direct_route", {
                "module": module_name,
                "message_preview": message[:100],
            })

        return response

    async def _handle_memory_store(self, args: dict[str, Any]) -> str:
        content = args.get("content")
        tier = args.get("tier")
        if not content:
            return "Error: 'content' is required."
        if tier not in ("working", "episodic", "semantic"):
            return "Error: 'tier' must be 'working', 'episodic', or 'semantic'."

        engram = self._ctx.get("engram")
        if engram is None:
            return "Error: Engram is not initialised."

        if tier == "working":
            key = args.get("key")
            if not key:
                return "Error: 'key' is required for working memory."
            engram.working.set(key, content)
            return json.dumps({"stored": True, "tier": "working", "key": key})

        if tier == "episodic":
            entry_id = engram.episodic.store(content, source="mcp")
            return json.dumps({"stored": True, "tier": "episodic", "id": entry_id})

        # semantic
        category = args.get("category", "general")
        entry_id = engram.semantic.store(content, category=category)
        return json.dumps({"stored": True, "tier": "semantic", "id": entry_id, "category": category})

    async def _handle_memory_query(self, args: dict[str, Any]) -> str:
        query = args.get("query")
        tier = args.get("tier")
        if not query:
            return "Error: 'query' is required."
        if tier not in ("working", "episodic", "semantic"):
            return "Error: 'tier' must be 'working', 'episodic', or 'semantic'."

        engram = self._ctx.get("engram")
        if engram is None:
            return "Error: Engram is not initialised."

        if tier == "working":
            value = engram.working.get(query)
            if value is None:
                return json.dumps({"found": False, "key": query})
            return json.dumps({"found": True, "key": query, "value": value})

        limit = args.get("limit", 10)

        if tier == "episodic":
            try:
                results = engram.episodic.recall(query, limit=limit)
            except Exception:
                # FTS match can fail on empty tables or invalid query syntax
                results = []
            return json.dumps({"tier": "episodic", "count": len(results), "results": results})

        # semantic
        category = args.get("category")
        results = engram.semantic.search(query, category=category, limit=limit)
        return json.dumps({"tier": "semantic", "count": len(results), "results": results})

    async def _handle_trust_check(self, args: dict[str, Any]) -> str:
        module_name = args.get("module")
        if not module_name:
            return "Error: 'module' is required."
        aegis = self._ctx.get("aegis")
        if aegis is None:
            return "Error: Aegis is not initialised."
        trust = aegis.get_trust(module_name)
        tier = aegis.get_tier(module_name)
        network = aegis.is_network_allowed(module_name)

        # Check if allowed via policy
        from nexus.kernel.aegis import PermissionDenied
        try:
            aegis.check(module_name, "handle")
            allowed = True
        except PermissionDenied:
            allowed = False

        return json.dumps({
            "module": module_name,
            "trust": trust,
            "tier": tier,
            "allowed": allowed,
            "network_allowed": network,
        })

    async def _handle_trust_record(self, args: dict[str, Any]) -> str:
        module_name = args.get("module")
        success = args.get("success")
        if not module_name:
            return "Error: 'module' is required."
        if success is None:
            return "Error: 'success' is required."

        aegis = self._ctx.get("aegis")
        if aegis is None:
            return "Error: Aegis is not initialised."
        new_trust = aegis.record_outcome(module_name, bool(success))
        tier = aegis.get_tier(module_name)
        delta = 0.12 if success else -0.22

        # Log the adjustment
        chronicle = self._ctx.get("chronicle")
        if chronicle:
            chronicle.log("mcp", "trust_record", {
                "module": module_name,
                "success": success,
                "delta": delta,
                "new_trust": new_trust,
            })

        return json.dumps({
            "module": module_name,
            "success": success,
            "delta": delta,
            "new_trust": new_trust,
            "tier": tier,
        })

    async def _handle_chronicle_query(self, args: dict[str, Any]) -> str:
        chronicle = self._ctx.get("chronicle")
        if chronicle is None:
            return "Error: Chronicle is not initialised."
        source = args.get("source")
        event_type = args.get("event_type")
        limit = args.get("limit", 50)
        results = chronicle.query(source=source, action=event_type, limit=limit)
        return json.dumps({"count": len(results), "events": results})

    async def _handle_modules_list(self, _args: dict[str, Any]) -> str:
        cortex = self._ctx.get("cortex")
        aegis = self._ctx.get("aegis")
        if cortex is None:
            return "Error: Cortex is not initialised."

        modules = []
        for name, mod in sorted(cortex._modules.items()):
            entry: dict[str, Any] = {
                "name": name,
                "description": mod.description,
                "version": mod.version,
                "type": "agent" if hasattr(mod, "analyze") else "module",
                "requires_network": getattr(mod, "requires_network", False),
            }
            if aegis:
                from nexus.kernel.aegis import PermissionDenied as _PD
                entry["trust"] = aegis.get_trust(name)
                entry["tier"] = aegis.get_tier(name)
                try:
                    aegis.check(name, "handle")
                    entry["allowed"] = True
                except _PD:
                    entry["allowed"] = False
                entry["network_allowed"] = aegis.is_network_allowed(name)
            modules.append(entry)
        return json.dumps({"count": len(modules), "modules": modules})

    async def _handle_module_allow(self, args: dict[str, Any]) -> str:
        module_name = args.get("module")
        if not module_name:
            return "Error: 'module' is required."
        network = args.get("network", False)
        aegis = self._ctx.get("aegis")
        if aegis is None:
            return "Error: Aegis is not initialised."
        aegis.set_policy(module_name, allowed=True, network=bool(network))

        chronicle = self._ctx.get("chronicle")
        if chronicle:
            chronicle.log("mcp", "module_allow", {
                "module": module_name,
                "network": network,
            })

        return json.dumps({"module": module_name, "allowed": True, "network_allowed": bool(network)})

    async def _handle_module_deny(self, args: dict[str, Any]) -> str:
        module_name = args.get("module")
        if not module_name:
            return "Error: 'module' is required."
        aegis = self._ctx.get("aegis")
        if aegis is None:
            return "Error: Aegis is not initialised."
        aegis.set_policy(module_name, allowed=False)

        chronicle = self._ctx.get("chronicle")
        if chronicle:
            chronicle.log("mcp", "module_deny", {"module": module_name})

        return json.dumps({"module": module_name, "allowed": False})

    async def _handle_status(self, _args: dict[str, Any]) -> str:
        cortex = self._ctx.get("cortex")
        aegis = self._ctx.get("aegis")
        engram = self._ctx.get("engram")

        status: dict[str, Any] = {"system": "nexus", "status": "running"}

        if cortex:
            module_names = sorted(cortex._modules.keys())
            agents = [n for n in module_names if hasattr(cortex._modules[n], "analyze")]
            modules = [n for n in module_names if not hasattr(cortex._modules[n], "analyze")]
            status["modules_loaded"] = len(modules)
            status["agents_loaded"] = len(agents)
            status["module_names"] = modules
            status["agent_names"] = agents
        else:
            status["modules_loaded"] = 0
            status["agents_loaded"] = 0

        if aegis:
            policies = aegis.list_policies()
            allowed_count = sum(1 for p in policies if p["allowed"])
            status["policies_total"] = len(policies)
            status["policies_allowed"] = allowed_count

        if engram:
            wm_keys = list(engram.working._store.keys())
            status["working_memory_keys"] = len(wm_keys)

        return json.dumps(status)

    async def _handle_workflow_run(self, args: dict[str, Any]) -> str:
        steps = args.get("steps")
        if not steps or not isinstance(steps, list):
            return "Error: 'steps' must be a non-empty array of {module, message} objects."

        cortex = self._ctx.get("cortex")
        if cortex is None:
            return "Error: Cortex is not initialised."

        results: list[dict[str, Any]] = []
        prev_output = ""

        for i, step in enumerate(steps):
            module_name = step.get("module")
            message = step.get("message", "")
            if not module_name:
                results.append({"step": i, "error": "Missing 'module' in step."})
                break

            # Inject previous output
            message = message.replace("{prev}", prev_output)

            if module_name not in cortex._modules:
                results.append({
                    "step": i,
                    "module": module_name,
                    "error": f"Module '{module_name}' not found.",
                })
                break

            # Check permission
            aegis = self._ctx.get("aegis")
            if aegis:
                from nexus.kernel.aegis import PermissionDenied
                try:
                    aegis.check(module_name, "handle")
                except PermissionDenied:
                    results.append({
                        "step": i,
                        "module": module_name,
                        "error": f"Module '{module_name}' is not allowed.",
                    })
                    break

            mod = cortex._modules[module_name]
            context = cortex._build_context()
            try:
                output = await mod.handle(message, context)
            except Exception as exc:
                results.append({
                    "step": i,
                    "module": module_name,
                    "error": str(exc),
                })
                break

            prev_output = output
            results.append({
                "step": i,
                "module": module_name,
                "output": output,
            })

        # Log workflow execution
        chronicle = self._ctx.get("chronicle")
        if chronicle:
            chronicle.log("mcp", "workflow_run", {
                "steps_requested": len(steps),
                "steps_completed": len(results),
            })

        return json.dumps({"steps_completed": len(results), "results": results})

    # ------------------------------------------------------------------
    # Agent catalog handlers
    # ------------------------------------------------------------------

    def _get_catalog(self):
        """Lazily load the AgentCatalog if configured."""
        if not hasattr(self, "_catalog"):
            config = self._ctx.get("config")
            catalog_path = getattr(config, "agents_catalog_path", None) if config else None
            if not catalog_path:
                self._catalog = None
            else:
                try:
                    from nexus.agents.catalog import AgentCatalog
                    self._catalog = AgentCatalog(catalog_path)
                except Exception:
                    self._catalog = None
        return self._catalog

    async def _handle_agents_browse(self, args: dict[str, Any]) -> str:
        catalog = self._get_catalog()
        if catalog is None:
            return json.dumps({
                "error": "Agent catalog not configured. Set NEXUS_AGENTS_CATALOG to the path of a cloned ONEXUS-Agents repo."
            })
        category = args.get("category")
        runnable_only = args.get("runnable_only", False)
        limit = args.get("limit", 20)
        agents = catalog.list_agents(category=category, runnable_only=runnable_only)[:limit]
        return json.dumps({
            "count": len(agents),
            "categories": catalog.categories() if not category else [category],
            "agents": [
                {
                    "slug": a.slug,
                    "name": a.name,
                    "tagline": a.tagline,
                    "category": a.category,
                    "composite_score": a.composite_score,
                    "rank": a.rank_in_category,
                    "runnable": a.runnable,
                    "stars": a.stars,
                    "license": a.license,
                }
                for a in agents
            ],
        })

    async def _handle_agents_search(self, args: dict[str, Any]) -> str:
        catalog = self._get_catalog()
        if catalog is None:
            return json.dumps({
                "error": "Agent catalog not configured. Set NEXUS_AGENTS_CATALOG to the path of a cloned ONEXUS-Agents repo."
            })
        query = args.get("query", "")
        if not query:
            return json.dumps({"error": "'query' is required."})
        limit = args.get("limit", 20)
        results = catalog.search(query, limit=limit)
        return json.dumps({
            "query": query,
            "count": len(results),
            "results": [
                {
                    "slug": a.slug,
                    "name": a.name,
                    "tagline": a.tagline,
                    "category": a.category,
                    "composite_score": a.composite_score,
                    "runnable": a.runnable,
                    "stars": a.stars,
                }
                for a in results
            ],
        })

    async def _handle_agents_info(self, args: dict[str, Any]) -> str:
        catalog = self._get_catalog()
        if catalog is None:
            return json.dumps({
                "error": "Agent catalog not configured. Set NEXUS_AGENTS_CATALOG to the path of a cloned ONEXUS-Agents repo."
            })
        slug = args.get("slug", "")
        if not slug:
            return json.dumps({"error": "'slug' is required."})
        agent = catalog.get_agent(slug)
        if agent is None:
            return json.dumps({"error": f"Agent '{slug}' not found in catalog."})

        info: dict[str, Any] = {
            "slug": agent.slug,
            "name": agent.name,
            "tagline": agent.tagline,
            "category": agent.category,
            "tags": agent.tags,
            "license": agent.license,
            "runnable": agent.runnable,
            "composite_score": agent.composite_score,
            "rank_in_category": agent.rank_in_category,
            "source_github": agent.source_github,
            "source_huggingface": agent.source_huggingface,
            "homepage": agent.homepage,
            "stars": agent.stars,
            "downloads_30d": agent.downloads_30d,
        }

        if agent.runnable:
            adapter = catalog.load_adapter(agent)
            if adapter:
                info["adapter"] = {
                    "transport": adapter.transport,
                    "command": adapter.command,
                    "args": adapter.args,
                    "env_keys": list(adapter.env.keys()),
                    "capabilities": adapter.capabilities,
                    "trust_floor": adapter.trust_floor,
                    "default_tier": adapter.default_tier,
                }

        return json.dumps(info)
